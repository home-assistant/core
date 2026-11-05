"""Report which entities and event types use space in the recorder database."""

import asyncio
from datetime import datetime, timedelta
import logging
from typing import TYPE_CHECKING, Any, Final, TypedDict

import probatio
from sqlalchemy import func, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm.session import Session

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import recorder as recorder_helper
from homeassistant.helpers.recorder import get_instance, session_scope
from homeassistant.util import dt as dt_util
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN, SupportedDialect
from .db_schema import (
    TABLE_EVENT_DATA,
    TABLE_EVENTS,
    TABLE_STATE_ATTRIBUTES,
    TABLE_STATES,
    TABLE_STATISTICS,
    TABLE_STATISTICS_SHORT_TERM,
    EventData,
    Events,
    EventTypes,
    StateAttributes,
    States,
    StatesMeta,
    Statistics,
    StatisticsMeta,
    StatisticsShortTerm,
)

if TYPE_CHECKING:
    from .core import Recorder

_LOGGER = logging.getLogger(__name__)

CACHE_TIME: Final = timedelta(minutes=5)

DATA_DATABASE_USAGE: HassKey[DatabaseUsageCache] = HassKey(f"{DOMAIN}_database_usage")

SQLITE_DBSTAT_QUERY: Final = (
    "SELECT m.tbl_name, SUM(d.pgsize) FROM dbstat AS d "
    "JOIN sqlite_master AS m ON m.name = d.name "
    "WHERE d.aggregate = TRUE GROUP BY m.tbl_name"
)

# Bytes per row including indexes, measured with dbstat on SQLite 3.53
SQLITE_ROW_BYTES: Final = {
    TABLE_STATES: 157,
    TABLE_STATISTICS: 90,
    TABLE_STATISTICS_SHORT_TERM: 90,
    TABLE_EVENTS: 125,
}
# Bytes per byte of JSON including row overhead and indexes
SQLITE_JSON_FACTOR: Final = 1.2


class TableUsage(TypedDict):
    """Space used by one table, including its indexes."""

    table: str
    bytes: int


class EntityUsage(TypedDict):
    """Estimated space used by one entity."""

    entity_id: str
    states: int
    statistics: int
    statistics_short_term: int
    bytes: int


class EventTypeUsage(TypedDict):
    """Estimated space used by one event type."""

    event_type: str
    events: int
    bytes: int


class DatabaseUsage(TypedDict):
    """Space used in the recorder database."""

    generated_at: datetime
    total_bytes: int
    tables: list[TableUsage]
    entities: list[EntityUsage]
    event_types: list[EventTypeUsage]


def _sqlite_table_bytes(
    session: Session, totals: dict[str, int]
) -> tuple[dict[str, int], int]:
    """Return bytes per table, indexes included, and the database size.

    Uses the dbstat virtual table, or an estimate from the row counts spread
    over the used pages when SQLite is built without dbstat.
    """
    page_count = session.execute(text("PRAGMA page_count")).scalar_one()
    page_size = session.execute(text("PRAGMA page_size")).scalar_one()
    try:
        rows = session.execute(text(SQLITE_DBSTAT_QUERY)).all()
    except OperationalError:
        _LOGGER.debug("dbstat is not available, estimating table sizes")
    else:
        return {table: int(size) for table, size in rows}, page_count * page_size
    estimates = {
        table: totals[table] * row_bytes
        for table, row_bytes in SQLITE_ROW_BYTES.items()
    } | {
        TABLE_STATE_ATTRIBUTES: round(
            totals[TABLE_STATE_ATTRIBUTES] * SQLITE_JSON_FACTOR
        ),
        TABLE_EVENT_DATA: round(totals[TABLE_EVENT_DATA] * SQLITE_JSON_FACTOR),
    }
    estimated = sum(estimates.values()) or 1
    free_pages = session.execute(text("PRAGMA freelist_count")).scalar_one()
    used = (page_count - free_pages) * page_size
    return (
        {table: round(used * size / estimated) for table, size in estimates.items()},
        page_count * page_size,
    )


def _mysql_table_bytes(session: Session) -> tuple[dict[str, int], int]:
    """Return bytes per table, indexes included, and the database size."""
    table_bytes = {
        table: int(size or 0)
        for table, size in session.execute(
            text(
                "SELECT table_name, data_length + index_length "
                "FROM information_schema.tables WHERE table_schema = DATABASE()"
            )
        ).all()
    }
    return table_bytes, sum(table_bytes.values())


def _postgresql_table_bytes(session: Session) -> tuple[dict[str, int], int]:
    """Return bytes per table, indexes and TOAST included, and the database size."""
    table_bytes = {
        table: int(size)
        for table, size in session.execute(
            text(
                "SELECT c.relname, pg_total_relation_size(c.oid) FROM pg_class AS c "
                "JOIN pg_namespace AS n ON n.oid = c.relnamespace "
                "WHERE n.nspname = current_schema() AND c.relkind = 'r'"
            )
        ).all()
    }
    total = session.execute(
        text("SELECT pg_database_size(current_database())")
    ).scalar_one()
    return table_bytes, int(total)


def _counts(session: Session, column: Any) -> dict[int, int]:
    """Return the row count per value of an indexed column."""
    return dict(session.execute(select(column, func.count()).group_by(column)).all())


def _names(session: Session, key: Any, name: Any) -> dict[int, str]:
    """Return the name per id of a lookup table."""
    return {
        id_: value
        for id_, value in session.execute(select(key, name)).all()
        if value is not None
    }


def _first_owner_lengths(
    session: Session, owner: Any, owner_ref: Any, shared: Any, shared_id: Any
) -> dict[int, int]:
    """Return the shared data length per owner.

    Each shared row goes to the first owner found through the index on the
    referencing column, which is exact unless several owners share a row.
    Rows without an owner are left out.
    """
    first_owner = select(owner).where(owner_ref == shared_id).limit(1).scalar_subquery()
    sub = select(
        first_owner.label("owner"), func.length(shared).label("length")
    ).subquery()
    return {
        owner_id: int(length)
        for owner_id, length in session.execute(
            select(sub.c.owner, func.sum(sub.c.length))
            .where(sub.c.owner.is_not(None))
            .group_by(sub.c.owner)
        ).all()
    }


def get_database_usage(instance: Recorder) -> DatabaseUsage:
    """Return the space entities and event types use in the database.

    Table sizes come from the database engine; a table's bytes are spread over
    its rows evenly, except for attributes and event data, which are spread by
    the length of the JSON each entity or event type owns.
    """
    generated_at = dt_util.utcnow()
    with session_scope(session=instance.get_session(), read_only=True) as session:
        states = _counts(session, States.metadata_id)
        attributes = _first_owner_lengths(
            session,
            States.metadata_id,
            States.attributes_id,
            StateAttributes.shared_attrs,
            StateAttributes.attributes_id,
        )
        statistics = _counts(session, Statistics.metadata_id)
        short_term = _counts(session, StatisticsShortTerm.metadata_id)
        events = _counts(session, Events.event_type_id)
        event_data = _first_owner_lengths(
            session,
            Events.event_type_id,
            Events.data_id,
            EventData.shared_data,
            EventData.data_id,
        )
        totals = {
            TABLE_STATES: sum(states.values()),
            TABLE_STATE_ATTRIBUTES: sum(attributes.values()),
            TABLE_STATISTICS: sum(statistics.values()),
            TABLE_STATISTICS_SHORT_TERM: sum(short_term.values()),
            TABLE_EVENTS: sum(events.values()),
            TABLE_EVENT_DATA: sum(event_data.values()),
        }
        match instance.dialect_name:
            case SupportedDialect.MYSQL:
                table_bytes, total_bytes = _mysql_table_bytes(session)
            case SupportedDialect.POSTGRESQL:
                table_bytes, total_bytes = _postgresql_table_bytes(session)
            case _:
                table_bytes, total_bytes = _sqlite_table_bytes(session, totals)
        entity_ids = _names(session, StatesMeta.metadata_id, StatesMeta.entity_id)
        statistic_ids = _names(session, StatisticsMeta.id, StatisticsMeta.statistic_id)
        event_types = _names(session, EventTypes.event_type_id, EventTypes.event_type)

    def share(table: str, part: int) -> float:
        """Return the bytes of a table that part of its rows or JSON takes."""
        if not part:
            return 0.0
        return table_bytes.get(table, 0) * part / totals[table]

    entity_usage: dict[str, EntityUsage] = {
        entity_id: {
            "entity_id": entity_id,
            "states": states.get(metadata_id, 0),
            "statistics": 0,
            "statistics_short_term": 0,
            "bytes": round(
                share(TABLE_STATES, states.get(metadata_id, 0))
                + share(TABLE_STATE_ATTRIBUTES, attributes.get(metadata_id, 0))
            ),
        }
        for metadata_id, entity_id in entity_ids.items()
    }
    for metadata_id, statistic_id in statistic_ids.items():
        usage = entity_usage.setdefault(
            statistic_id,
            {
                "entity_id": statistic_id,
                "states": 0,
                "statistics": 0,
                "statistics_short_term": 0,
                "bytes": 0,
            },
        )
        usage["statistics"] = statistics.get(metadata_id, 0)
        usage["statistics_short_term"] = short_term.get(metadata_id, 0)
        usage["bytes"] += round(
            share(TABLE_STATISTICS, usage["statistics"])
            + share(TABLE_STATISTICS_SHORT_TERM, usage["statistics_short_term"])
        )

    return {
        "generated_at": generated_at,
        "total_bytes": total_bytes,
        "tables": sorted(
            ({"table": table, "bytes": size} for table, size in table_bytes.items()),
            key=lambda usage: (-usage["bytes"], usage["table"]),
        ),
        "entities": sorted(
            entity_usage.values(),
            key=lambda usage: (-usage["bytes"], -usage["states"], usage["entity_id"]),
        ),
        "event_types": sorted(
            (
                {
                    "event_type": event_type,
                    "events": events.get(event_type_id, 0),
                    "bytes": round(
                        share(TABLE_EVENTS, events.get(event_type_id, 0))
                        + share(TABLE_EVENT_DATA, event_data.get(event_type_id, 0))
                    ),
                }
                for event_type_id, event_type in event_types.items()
            ),
            key=lambda usage: (-usage["bytes"], -usage["events"], usage["event_type"]),
        ),
    }


class DatabaseUsageCache:
    """Run one database usage report at a time and keep the last result."""

    def __init__(self) -> None:
        """Initialize the cache."""
        self._usage: DatabaseUsage | None = None
        self._pending: asyncio.Future[DatabaseUsage] | None = None

    async def async_get(self, instance: Recorder, refresh: bool) -> DatabaseUsage:
        """Return the cached report, or wait for a new or running one."""
        if self._pending is None:
            if (
                not refresh
                and self._usage is not None
                and dt_util.utcnow() - self._usage["generated_at"] < CACHE_TIME
            ):
                return self._usage
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
        if not future.cancelled() and future.exception() is None:
            self._usage = future.result()


@callback
def async_setup(hass: HomeAssistant) -> None:
    """Set up the database usage websocket API."""
    hass.data[DATA_DATABASE_USAGE] = DatabaseUsageCache()
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
    """Return the space entities and event types use in the database."""
    await hass.data[recorder_helper.DATA_RECORDER].db_connected
    connection.send_result(
        msg["id"],
        await hass.data[DATA_DATABASE_USAGE].async_get(
            get_instance(hass), msg["refresh"]
        ),
    )
