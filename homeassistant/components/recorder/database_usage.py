"""Report which entities and statistics use space in the recorder database."""

import asyncio
from collections import defaultdict
from collections.abc import Callable, Mapping
from contextlib import suppress
from datetime import datetime, timedelta
import os
from typing import TYPE_CHECKING, Any, Final, TypedDict

import probatio
from sqlalchemy import LargeBinary, cast, func, literal_column, make_url, select, text
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm.session import Session

from homeassistant.components import websocket_api
from homeassistant.core import HassJob, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.recorder import get_instance, session_scope
from homeassistant.util import dt as dt_util
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN, SupportedDialect
from .db_schema import (
    TABLE_STATE_ATTRIBUTES,
    TABLE_STATES,
    TABLE_STATISTICS,
    TABLE_STATISTICS_SHORT_TERM,
    StateAttributes,
    States,
    StatesMeta,
    Statistics,
    StatisticsMeta,
    StatisticsShortTerm,
)
from .util import is_file_sqlite_url

if TYPE_CHECKING:
    from sqlalchemy.dialects.mysql.base import MySQLDialect

    from .core import Recorder

CACHE_TIME: Final = timedelta(hours=1)
REFRESH_INTERVAL: Final = timedelta(minutes=1)

DATA_DATABASE_USAGE: HassKey[DatabaseUsageCache] = HassKey(f"{DOMAIN}_database_usage")

SQLITE_DBSTAT_QUERY: Final = (
    "SELECT m.tbl_name, SUM(d.pgsize) FROM dbstat AS d "
    "JOIN sqlite_master AS m ON m.name = d.name "
    "WHERE d.aggregate = TRUE GROUP BY m.tbl_name"
)
INNODB_TABLES_QUERY: Final = (
    "SELECT name, space FROM information_schema.INNODB_TABLES "
    "WHERE name LIKE CONCAT(DATABASE(), '/%')"
)
MARIADB_INNODB_TABLES_QUERY: Final = (
    "SELECT name, space FROM information_schema.INNODB_SYS_TABLES "
    "WHERE name LIKE CONCAT(DATABASE(), '/%')"
)


class TableUsage(TypedDict):
    """Space used by one table, including its indexes."""

    table: str
    bytes: int


class EntityUsage(TypedDict):
    """Estimated space the states of one entity use.

    An entity_id of None collects rows without a known entity.
    """

    entity_id: str | None
    states: int
    states_bytes: int | None
    attributes_bytes: int | None


class StatisticUsage(TypedDict):
    """Estimated space one statistic uses.

    A statistic_id of None collects rows without a known statistic.
    """

    statistic_id: str | None
    source: str | None
    statistics: int
    statistics_short_term: int
    statistics_bytes: int | None
    statistics_short_term_bytes: int | None


class DatabaseUsage(TypedDict):
    """Space used in the recorder database.

    total_bytes is the size of the database, free_bytes included, without the
    SQLite write-ahead log, whose files wal_bytes holds. Byte figures per table
    and row are None when the engine cannot report table sizes.
    """

    generated_at: datetime
    duration: float
    total_bytes: int
    free_bytes: int | None
    wal_bytes: int | None
    tables: list[TableUsage] | None
    entities: list[EntityUsage]
    statistics: list[StatisticUsage]


def _sqlite_table_bytes(session: Session) -> tuple[dict[str, int] | None, int, int]:
    """Return bytes per table, the database size and its free space."""
    page_count = session.execute(text("PRAGMA page_count")).scalar_one()
    page_size = session.execute(text("PRAGMA page_size")).scalar_one()
    free_pages = session.execute(text("PRAGMA freelist_count")).scalar_one()
    try:
        rows = session.execute(text(SQLITE_DBSTAT_QUERY)).all()
    except OperationalError as err:
        # Only dbstat can be missing, when built without SQLITE_ENABLE_DBSTAT_VTAB
        if "no such table" not in str(err.orig):
            raise
        table_bytes = None
    else:
        table_bytes = {table: int(size) for table, size in rows}
    return table_bytes, page_count * page_size, free_pages * page_size


def _sqlite_wal_bytes(db_url: str) -> int | None:
    """Return the size of the write-ahead log and its index, None in memory."""
    url = make_url(db_url)
    if not is_file_sqlite_url(url):
        return None
    size = 0
    for postfix in ("-wal", "-shm"):
        with suppress(FileNotFoundError):
            size += os.path.getsize(f"{url.database}{postfix}")
    return size


def _mysql_tablespaces(session: Session, is_mariadb: bool) -> dict[str, int] | None:
    """Return the InnoDB tablespace per table, None when it cannot be read.

    Reading InnoDB metadata needs the PROCESS privilege.
    """
    try:
        rows = session.execute(
            text(MARIADB_INNODB_TABLES_QUERY if is_mariadb else INNODB_TABLES_QUERY)
        ).all()
    except OperationalError, ProgrammingError:
        return None
    return {name.partition("/")[2]: int(space) for name, space in rows}


def _mysql_table_bytes(session: Session) -> tuple[dict[str, int], int, int]:
    """Return bytes per table, the database size and its free space."""
    dialect = session.get_bind().dialect
    if TYPE_CHECKING:
        assert isinstance(dialect, MySQLDialect)
    stats_expiry = None
    if not dialect.is_mariadb:
        # MySQL caches these sizes for a day by default, MariaDB does not
        stats_expiry = session.execute(
            text("SELECT @@SESSION.information_schema_stats_expiry")
        ).scalar_one()
        session.execute(text("SET SESSION information_schema_stats_expiry = 0"))
    try:
        rows = session.execute(
            text(
                "SELECT table_name, data_length + index_length, data_free "
                "FROM information_schema.tables WHERE table_schema = DATABASE()"
            )
        ).all()
    finally:
        # The session setting would otherwise stay on the pooled connection
        if stats_expiry is not None:
            session.execute(
                text("SET SESSION information_schema_stats_expiry = :expiry"),
                {"expiry": stats_expiry},
            )
    table_bytes = {table: int(size or 0) for table, size, _ in rows}
    table_free = {table: int(free or 0) for table, _, free in rows}
    # Tables in a shared tablespace each report the free space of that tablespace,
    # so it is counted once per tablespace
    spaces = _mysql_tablespaces(session, dialect.is_mariadb)
    if spaces is not None and table_free.keys() <= spaces.keys():
        free_bytes = sum(
            {spaces[table]: free for table, free in table_free.items()}.values()
        )
    elif session.execute(text("SELECT @@innodb_file_per_table")).scalar_one():
        free_bytes = sum(table_free.values())
    else:
        free_bytes = max(table_free.values(), default=0)
    return table_bytes, sum(table_bytes.values()) + free_bytes, free_bytes


def _postgresql_table_bytes(session: Session) -> tuple[dict[str, int], int, None]:
    """Return bytes per table and the database size, catalogs included.

    Tables are those unqualified names resolve to through the search_path.
    """
    table_bytes = {
        table: int(size)
        for table, size in session.execute(
            text(
                "SELECT c.relname, pg_total_relation_size(c.oid) FROM pg_class AS c "
                "JOIN pg_namespace AS n ON n.oid = c.relnamespace "
                "WHERE c.relkind = 'r' AND pg_table_is_visible(c.oid) "
                "AND n.nspname NOT IN ('pg_catalog', 'information_schema')"
            )
        ).all()
    }
    total = session.execute(
        text("SELECT pg_database_size(current_database())")
    ).scalar_one()
    return table_bytes, int(total), None


def _counts(session: Session, column: Any) -> dict[int | None, int]:
    """Return the row count per value of an indexed column."""
    return dict(session.execute(select(column, func.count()).group_by(column)).all())


def _byte_length(dialect: SupportedDialect | None, column: Any) -> Any:
    """Return the length of a text column in bytes, not characters."""
    match dialect:
        case SupportedDialect.MYSQL:
            return func.length(column)
        case SupportedDialect.POSTGRESQL:
            return func.octet_length(column)
        case _:
            return func.length(cast(column, LargeBinary))


def _attribute_lengths(
    session: Session, dialect: SupportedDialect | None
) -> dict[int | None, float]:
    """Return the attributes length in bytes per metadata_id.

    An attributes row shared by several entities is split over them by how
    many of their states use it. Rows without a state go to None.
    """
    # + 0 makes SQLite scan the table instead of reading it through an index
    owner = States.metadata_id + literal_column("0")
    refs = (
        select(
            owner.label("metadata_id"),
            States.attributes_id,
            func.count().label("rows"),
        )
        .group_by(owner, States.attributes_id)
        .subquery()
    )
    weighted = select(
        refs.c.metadata_id,
        refs.c.attributes_id,
        refs.c.rows,
        func.sum(refs.c.rows).over(partition_by=refs.c.attributes_id).label("total"),
    ).subquery()
    length = _byte_length(dialect, StateAttributes.shared_attrs)
    sub = (
        select(
            weighted.c.metadata_id.label("owner"),
            func.coalesce(length * weighted.c.rows / weighted.c.total, length).label(
                "length"
            ),
        )
        .select_from(StateAttributes)
        .outerjoin(weighted, weighted.c.attributes_id == StateAttributes.attributes_id)
        .subquery()
    )
    return {
        metadata_id: float(length or 0)
        for metadata_id, length in session.execute(
            select(sub.c.owner, func.sum(sub.c.length)).group_by(sub.c.owner)
        ).all()
    }


def _group[KeyT, ValueT: (int, float)](
    values: dict[int | None, ValueT], keys: Mapping[int | None, KeyT]
) -> dict[KeyT | None, ValueT]:
    """Return the values per key, with unknown ids under None."""
    grouped: dict[KeyT | None, ValueT] = defaultdict(int)
    for id_, value in values.items():
        grouped[keys.get(id_)] += value
    return grouped


def _begin_snapshot(session: Session, dialect: SupportedDialect | None) -> None:
    """Begin a transaction that reads one snapshot of the database."""
    match dialect:
        case SupportedDialect.MYSQL:
            session.connection(execution_options={"isolation_level": "REPEATABLE READ"})
        case SupportedDialect.POSTGRESQL:
            session.connection(
                execution_options={
                    "isolation_level": "REPEATABLE READ",
                    "postgresql_readonly": True,
                }
            )
        case _:
            # pysqlite only begins a transaction for writes; in WAL mode the read
            # transaction does not block the recorder, but holds back checkpoints
            # until the report is done
            session.execute(text("BEGIN"))


def get_database_usage(instance: Recorder) -> DatabaseUsage:
    """Return the space entities and statistics use in the database.

    Table sizes come from the database engine; a table's bytes are spread over
    its rows evenly, except for attributes, which are spread by the length of
    the JSON each entity owns. All queries read one snapshot of the database.
    """
    started = dt_util.utcnow()
    dialect = instance.dialect_name
    wal_bytes: int | None = None
    with session_scope(session=instance.get_session(), read_only=True) as session:
        _begin_snapshot(session, dialect)
        states = _counts(session, States.metadata_id)
        attributes = _attribute_lengths(session, dialect)
        statistics = _counts(session, Statistics.metadata_id)
        short_term = _counts(session, StatisticsShortTerm.metadata_id)
        table_bytes: dict[str, int] | None
        free_bytes: int | None
        match dialect:
            case SupportedDialect.MYSQL:
                table_bytes, total_bytes, free_bytes = _mysql_table_bytes(session)
            case SupportedDialect.POSTGRESQL:
                table_bytes, total_bytes, free_bytes = _postgresql_table_bytes(session)
            case _:
                table_bytes, total_bytes, free_bytes = _sqlite_table_bytes(session)
                wal_bytes = _sqlite_wal_bytes(instance.db_url)
        entity_ids: dict[int | None, str | None] = dict(
            session.execute(select(StatesMeta.metadata_id, StatesMeta.entity_id)).all()
        )
        statistic_ids: dict[int | None, tuple[str | None, str | None]] = {
            id_: (statistic_id, source)
            for id_, statistic_id, source in session.execute(
                select(
                    StatisticsMeta.id,
                    StatisticsMeta.statistic_id,
                    StatisticsMeta.source,
                )
            ).all()
        }

    totals = {
        TABLE_STATES: sum(states.values()),
        TABLE_STATE_ATTRIBUTES: sum(attributes.values()),
        TABLE_STATISTICS: sum(statistics.values()),
        TABLE_STATISTICS_SHORT_TERM: sum(short_term.values()),
    }

    def share(table: str, part: float) -> int | None:
        """Return the bytes of a table that part of its rows or JSON takes."""
        if table_bytes is None:
            return None
        if not part:
            return 0
        return round(table_bytes.get(table, 0) * part / totals[table])

    entity_states = _group(states, entity_ids)
    entity_attributes = _group(attributes, entity_ids)
    statistic_rows = _group(statistics, statistic_ids)
    statistic_short_term = _group(short_term, statistic_ids)
    generated_at = dt_util.utcnow()
    return {
        "generated_at": generated_at,
        "duration": (generated_at - started).total_seconds(),
        "total_bytes": total_bytes,
        "free_bytes": free_bytes,
        "wal_bytes": wal_bytes,
        "tables": None
        if table_bytes is None
        else [{"table": table, "bytes": size} for table, size in table_bytes.items()],
        "entities": [
            {
                "entity_id": entity_id,
                "states": entity_states.get(entity_id, 0),
                "states_bytes": share(TABLE_STATES, entity_states.get(entity_id, 0)),
                "attributes_bytes": share(
                    TABLE_STATE_ATTRIBUTES, entity_attributes.get(entity_id, 0)
                ),
            }
            for entity_id in entity_states | entity_attributes
        ],
        "statistics": [
            {
                "statistic_id": key[0] if key else None,
                "source": key[1] if key else None,
                "statistics": statistic_rows.get(key, 0),
                "statistics_short_term": statistic_short_term.get(key, 0),
                "statistics_bytes": share(TABLE_STATISTICS, statistic_rows.get(key, 0)),
                "statistics_short_term_bytes": share(
                    TABLE_STATISTICS_SHORT_TERM, statistic_short_term.get(key, 0)
                ),
            }
            for key in statistic_rows | statistic_short_term
        ],
    }


class DatabaseUsageCache:
    """Run one database usage report at a time and keep the last result."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the cache."""
        self._hass = hass
        self.usage: DatabaseUsage | None = None
        self._pending: asyncio.Future[DatabaseUsage] | None = None
        self._expire_job = HassJob(self._async_expire, cancel_on_shutdown=True)
        self._cancel_expire: Callable[[], None] | None = None

    async def async_refresh(self, instance: Recorder) -> DatabaseUsage:
        """Return a new report, or the last one if it is still recent."""
        if self._pending is None:
            if (
                self.usage is not None
                and dt_util.utcnow() - self.usage["generated_at"] < REFRESH_INTERVAL
            ):
                return self.usage
            self._pending = instance.async_add_executor_job(
                get_database_usage, instance
            )
            self._pending.add_done_callback(self._async_finished)
        # A closed connection must not cancel the run other requests wait for
        return await asyncio.shield(self._pending)

    @callback
    def _async_finished(self, future: asyncio.Future[DatabaseUsage]) -> None:
        """Store the result of a finished run."""
        self._pending = None
        if future.cancelled() or future.exception() is not None:
            return
        if self._cancel_expire is not None:
            self._cancel_expire()
        self.usage = future.result()
        self._cancel_expire = async_call_later(self._hass, CACHE_TIME, self._expire_job)

    @callback
    def _async_expire(self, _now: datetime) -> None:
        """Release the cached report."""
        self._cancel_expire = None
        self.usage = None


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up the database usage websocket API."""
    hass.data[DATA_DATABASE_USAGE] = DatabaseUsageCache(hass)
    websocket_api.async_register_command(hass, ws_database_usage)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        probatio.Required("type"): "recorder/database_usage",
        probatio.Optional("refresh", default=False): bool,
    }
)
@websocket_api.async_response
async def ws_database_usage(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return the last report, or analyze the database when refresh is set."""
    cache = hass.data[DATA_DATABASE_USAGE]
    if not msg["refresh"]:
        connection.send_result(msg["id"], cache.usage)
        return
    instance = get_instance(hass)
    # Offline migrations finish and the recorder executor starts once ready
    if not await instance.async_db_ready:
        connection.send_error(
            msg["id"], "recorder_not_ready", "The recorder database is not available"
        )
        return
    if instance.migration_in_progress:
        connection.send_error(
            msg["id"],
            "migration_in_progress",
            "The recorder database is being migrated",
        )
        return
    connection.send_result(msg["id"], await cache.async_refresh(instance))
