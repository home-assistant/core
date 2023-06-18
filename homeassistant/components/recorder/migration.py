"""Schema migration helpers."""
from __future__ import annotations

from collections.abc import Callable, Iterable
import contextlib
from dataclasses import dataclass, replace as dataclass_replace
from datetime import timedelta
import logging
from time import time
from typing import TYPE_CHECKING, cast
from uuid import UUID

import sqlalchemy
from sqlalchemy import ForeignKeyConstraint, MetaData, Table, func, text, update
from sqlalchemy.engine import CursorResult, Engine
from sqlalchemy.exc import (
    DatabaseError,
    IntegrityError,
    InternalError,
    OperationalError,
    ProgrammingError,
    SQLAlchemyError,
)
from sqlalchemy.orm.session import Session
from sqlalchemy.schema import AddConstraint, DropConstraint
from sqlalchemy.sql.expression import true

from homeassistant.core import HomeAssistant
from homeassistant.util.enum import try_parse_enum
from homeassistant.util.ulid import ulid_at_time, ulid_to_bytes

from .auto_repairs.events.schema import (
    correct_db_schema as events_correct_db_schema,
    validate_db_schema as events_validate_db_schema,
)
from .auto_repairs.states.schema import (
    correct_db_schema as states_correct_db_schema,
    validate_db_schema as states_validate_db_schema,
)
from .auto_repairs.statistics.duplicates import (
    delete_statistics_duplicates,
    delete_statistics_meta_duplicates,
)
from .auto_repairs.statistics.schema import (
    correct_db_schema as statistics_correct_db_schema,
    validate_db_schema as statistics_validate_db_schema,
)
from .const import SupportedDialect
from .db_schema import (
    CONTEXT_ID_BIN_MAX_LENGTH,
    DOUBLE_PRECISION_TYPE_SQL,
    LEGACY_STATES_ENTITY_ID_LAST_UPDATED_INDEX,
    LEGACY_STATES_EVENT_ID_INDEX,
    MYSQL_COLLATE,
    MYSQL_DEFAULT_CHARSET,
    SCHEMA_VERSION,
    STATISTICS_TABLES,
    TABLE_STATES,
    Base,
    Events,
    EventTypes,
    SchemaChanges,
    States,
    StatesMeta,
    Statistics,
    StatisticsMeta,
    StatisticsRuns,
    StatisticsShortTerm,
)
from .models import process_timestamp
from .queries import (
    batch_cleanup_entity_ids,
    find_entity_ids_to_migrate,
    find_event_type_to_migrate,
    find_events_context_ids_to_migrate,
    find_states_context_ids_to_migrate,
    has_used_states_event_ids,
)
from .statistics import get_start_time
from .tasks import (
    CommitTask,
    PostSchemaMigrationTask,
    StatisticsTimestampMigrationCleanupTask,
)
from .util import (
    database_job_retry_wrapper,
    get_index_by_name,
    retryable_database_job,
    session_scope,
)

if TYPE_CHECKING:
    from . import Recorder

LIVE_MIGRATION_MIN_SCHEMA_VERSION = 0
_EMPTY_ENTITY_ID = "missing.entity_id"
_EMPTY_EVENT_TYPE = "missing_event_type"

_LOGGER = logging.getLogger(__name__)


@dataclass
class _ColumnTypesForDialect:
    big_int_type: str
    timestamp_type: str
    context_bin_type: str


_MYSQL_COLUMN_TYPES = _ColumnTypesForDialect(
    big_int_type="INTEGER(20)",
    timestamp_type=DOUBLE_PRECISION_TYPE_SQL,
    context_bin_type=f"BLOB({CONTEXT_ID_BIN_MAX_LENGTH})",
)

_POSTGRESQL_COLUMN_TYPES = _ColumnTypesForDialect(
    big_int_type="INTEGER",
    timestamp_type=DOUBLE_PRECISION_TYPE_SQL,
    context_bin_type="BYTEA",
)

_SQLITE_COLUMN_TYPES = _ColumnTypesForDialect(
    big_int_type="INTEGER",
    timestamp_type="FLOAT",
    context_bin_type="BLOB",
)

_COLUMN_TYPES_FOR_DIALECT: dict[SupportedDialect | None, _ColumnTypesForDialect] = {
    SupportedDialect.MYSQL: _MYSQL_COLUMN_TYPES,
    SupportedDialect.POSTGRESQL: _POSTGRESQL_COLUMN_TYPES,
    SupportedDialect.SQLITE: _SQLITE_COLUMN_TYPES,
}


def raise_if_exception_missing_str(ex: Exception, match_substrs: Iterable[str]) -> None:
    """Raise if the exception and cause do not contain the match substrs."""
    lower_ex_strs = [str(ex).lower(), str(ex.__cause__).lower()]
    for str_sub in match_substrs:
        for exc_str in lower_ex_strs:
            if exc_str and str_sub in exc_str:
                return

    raise ex


def _get_schema_version(session: Session) -> int | None:
    """Get the schema version."""
    res = (
        session.query(SchemaChanges.schema_version)
        .order_by(SchemaChanges.change_id.desc())
        .first()
    )
    return getattr(res, "schema_version", None)


def get_schema_version(session_maker: Callable[[], Session]) -> int | None:
    """Get the schema version."""
    try:
        with session_scope(session=session_maker()) as session:
            return _get_schema_version(session)
    except Exception as err:  # pylint: disable=broad-except
        _LOGGER.exception("Error when determining DB schema version: %s", err)
        return None


@dataclass
class SchemaValidationStatus:
    """Store schema validation status."""

    current_version: int
    schema_errors: set[str]
    valid: bool


def _schema_is_current(current_version: int) -> bool:
    """Check if the schema is current."""
    return current_version == SCHEMA_VERSION


def validate_db_schema(
    hass: HomeAssistant, instance: Recorder, session_maker: Callable[[], Session]
) -> SchemaValidationStatus | None:
    """Check if the schema is valid.

    This checks that the schema is the current version as well as for some common schema
    errors caused by manual migration between database engines, for example importing an
    SQLite database to MariaDB.
    """
    schema_errors: set[str] = set()

    current_version = get_schema_version(session_maker)
    if current_version is None:
        return None

    if is_current := _schema_is_current(current_version):
        # We can only check for further errors if the schema is current, because
        # columns may otherwise not exist etc.
        schema_errors = _find_schema_errors(hass, instance, session_maker)

    valid = is_current and not schema_errors

    return SchemaValidationStatus(current_version, schema_errors, valid)


def _find_schema_errors(
    hass: HomeAssistant, instance: Recorder, session_maker: Callable[[], Session]
) -> set[str]:
    """Find schema errors."""
    schema_errors: set[str] = set()
    schema_errors |= statistics_validate_db_schema(instance)
    schema_errors |= states_validate_db_schema(instance)
    schema_errors |= events_validate_db_schema(instance)
    return schema_errors


def live_migration(schema_status: SchemaValidationStatus) -> bool:
    """Check if live migration is possible."""
    return schema_status.current_version >= LIVE_MIGRATION_MIN_SCHEMA_VERSION


def migrate_schema(
    instance: Recorder,
    hass: HomeAssistant,
    engine: Engine,
    session_maker: Callable[[], Session],
    schema_status: SchemaValidationStatus,
) -> None:
    """Check if the schema needs to be upgraded."""
    current_version = schema_status.current_version
    if current_version != SCHEMA_VERSION:
        _LOGGER.warning(
            "Database is about to upgrade from schema version: %s to: %s",
            current_version,
            SCHEMA_VERSION,
        )
    db_ready = False
    for version in range(current_version, SCHEMA_VERSION):
        if (
            live_migration(dataclass_replace(schema_status, current_version=version))
            and not db_ready
        ):
            db_ready = True
            instance.migration_is_live = True
            hass.add_job(instance.async_set_db_ready)
        new_version = version + 1
        _LOGGER.info("Upgrading recorder db schema to version %s", new_version)
        _apply_update(
            instance, hass, engine, session_maker, new_version, current_version
        )
        with session_scope(session=session_maker()) as session:
            session.add(SchemaChanges(schema_version=new_version))

        # Log at the same level as the long schema changes
        # so its clear that the upgrade is done
        _LOGGER.warning("Upgrade to version %s done", new_version)

    if schema_errors := schema_status.schema_errors:
        _LOGGER.warning(
            "Database is about to correct DB schema errors: %s",
            ", ".join(sorted(schema_errors)),
        )
        statistics_correct_db_schema(instance, schema_errors)
        states_correct_db_schema(instance, schema_errors)
        events_correct_db_schema(instance, schema_errors)

    if current_version != SCHEMA_VERSION:
        instance.queue_task(PostSchemaMigrationTask(current_version, SCHEMA_VERSION))
        # Make sure the post schema migration task is committed in case
        # the next task does not have commit_before = True
        instance.queue_task(CommitTask())


def _create_index(
    session_maker: Callable[[], Session], table_name: str, index_name: str
) -> None:
    """Create an index for the specified table.

    The index name should match the name given for the index
    within the table definition described in the models
    """
    table = Table(table_name, Base.metadata)
    _LOGGER.debug("Looking up index %s for table %s", index_name, table_name)
    # Look up the index object by name from the table is the models
    index_list = [idx for idx in table.indexes if idx.name == index_name]
    if not index_list:
        _LOGGER.debug("The index %s no longer exists", index_name)
        return
    index = index_list[0]
    _LOGGER.debug("Creating %s index", index_name)
    _LOGGER.warning(
        (
            "Adding index `%s` to table `%s`. Note: this can take several "
            "minutes on large databases and slow computers. Please "
            "be patient!"
        ),
        index_name,
        table_name,
    )
    with session_scope(session=session_maker()) as session:
        try:
            connection = session.connection()
            index.create(connection)
        except (InternalError, OperationalError, ProgrammingError) as err:
            raise_if_exception_missing_str(err, ["already exists", "duplicate"])
            _LOGGER.warning(
                "Index %s already exists on %s, continuing", index_name, table_name
            )

    _LOGGER.debug("Finished creating %s", index_name)


def _execute_or_collect_error(
    session_maker: Callable[[], Session], query: str, errors: list[str]
) -> bool:
    """Execute a query or collect an error."""
    with session_scope(session=session_maker()) as session:
        try:
            session.connection().execute(text(query))
            return True
        except SQLAlchemyError as err:
            errors.append(str(err))
    return False


def _drop_index(
    session_maker: Callable[[], Session],
    table_name: str,
    index_name: str,
    quiet: bool | None = None,
) -> None:
    """Drop an index from a specified table.

    There is no universal way to do something like `DROP INDEX IF EXISTS`
    so we will simply execute the DROP command and ignore any exceptions

    WARNING: Due to some engines (MySQL at least) being unable to use bind
    parameters in a DROP INDEX statement (at least via SQLAlchemy), the query
    string here is generated from the method parameters without sanitizing.
    DO NOT USE THIS FUNCTION IN ANY OPERATION THAT TAKES USER INPUT.
    """
    _LOGGER.warning(
        (
            "Dropping index `%s` from table `%s`. Note: this can take several "
            "minutes on large databases and slow computers. Please "
            "be patient!"
        ),
        index_name,
        table_name,
    )
    index_to_drop: str | None = None
    with session_scope(session=session_maker()) as session:
        index_to_drop = get_index_by_name(session, table_name, index_name)

    if index_to_drop is None:
        _LOGGER.debug(
            "The index %s on table %s no longer exists", index_name, table_name
        )
        return

    errors: list[str] = []
    for query in (
        # Engines like DB2/Oracle
        f"DROP INDEX {index_name}",
        # Engines like SQLite, SQL Server
        f"DROP INDEX {table_name}.{index_name}",
        # Engines like MySQL, MS Access
        f"DROP INDEX {index_name} ON {table_name}",
        # Engines like postgresql may have a prefix
        # ex idx_16532_ix_events_event_type_time_fired
        f"DROP INDEX {index_to_drop}",
    ):
        if _execute_or_collect_error(session_maker, query, errors):
            _LOGGER.debug(
                "Finished dropping index %s from table %s", index_name, table_name
            )
            return

    if not quiet:
        _LOGGER.warning(
            (
                "Failed to drop index `%s` from table `%s`. Schema "
                "Migration will continue; this is not a "
                "critical operation: %s"
            ),
            index_name,
            table_name,
            errors,
        )


def _add_columns(
    session_maker: Callable[[], Session], table_name: str, columns_def: list[str]
) -> None:
    """Add columns to a table."""
    _LOGGER.warning(
        (
            "Adding columns %s to table %s. Note: this can take several "
            "minutes on large databases and slow computers. Please "
            "be patient!"
        ),
        ", ".join(column.split(" ")[0] for column in columns_def),
        table_name,
    )

    columns_def = [f"ADD {col_def}" for col_def in columns_def]

    with session_scope(session=session_maker()) as session:
        try:
            connection = session.connection()
            connection.execute(
                text(
                    "ALTER TABLE {table} {columns_def}".format(
                        table=table_name, columns_def=", ".join(columns_def)
                    )
                )
            )
            return
        except (InternalError, OperationalError, ProgrammingError):
            # Some engines support adding all columns at once,
            # this error is when they don't
            _LOGGER.info("Unable to use quick column add. Adding 1 by 1")

    for column_def in columns_def:
        with session_scope(session=session_maker()) as session:
            try:
                connection = session.connection()
                connection.execute(
                    text(
                        "ALTER TABLE {table} {column_def}".format(
                            table=table_name, column_def=column_def
                        )
                    )
                )
            except (InternalError, OperationalError, ProgrammingError) as err:
                raise_if_exception_missing_str(err, ["already exists", "duplicate"])
                _LOGGER.warning(
                    "Column %s already exists on %s, continuing",
                    column_def.split(" ")[1],
                    table_name,
                )


def _modify_columns(
    session_maker: Callable[[], Session],
    engine: Engine,
    table_name: str,
    columns_def: list[str],
) -> None:
    """Modify columns in a table."""
    if engine.dialect.name == SupportedDialect.SQLITE:
        _LOGGER.debug(
            (
                "Skipping to modify columns %s in table %s; "
                "Modifying column length in SQLite is unnecessary, "
                "it does not impose any length restrictions"
            ),
            ", ".join(column.split(" ")[0] for column in columns_def),
            table_name,
        )
        return

    _LOGGER.warning(
        (
            "Modifying columns %s in table %s. Note: this can take several "
            "minutes on large databases and slow computers. Please "
            "be patient!"
        ),
        ", ".join(column.split(" ")[0] for column in columns_def),
        table_name,
    )

    if engine.dialect.name == SupportedDialect.POSTGRESQL:
        columns_def = [
            "ALTER {column} TYPE {type}".format(
                **dict(zip(["column", "type"], col_def.split(" ", 1)))
            )
            for col_def in columns_def
        ]
    elif engine.dialect.name == "mssql":
        columns_def = [f"ALTER COLUMN {col_def}" for col_def in columns_def]
    else:
        columns_def = [f"MODIFY {col_def}" for col_def in columns_def]

    with session_scope(session=session_maker()) as session:
        try:
            connection = session.connection()
            connection.execute(
                text(
                    "ALTER TABLE {table} {columns_def}".format(
                        table=table_name, columns_def=", ".join(columns_def)
                    )
                )
            )
            return
        except (InternalError, OperationalError):
            _LOGGER.info("Unable to use quick column modify. Modifying 1 by 1")

    for column_def in columns_def:
        with session_scope(session=session_maker()) as session:
            try:
                connection = session.connection()
                connection.execute(
                    text(
                        "ALTER TABLE {table} {column_def}".format(
                            table=table_name, column_def=column_def
                        )
                    )
                )
            except (InternalError, OperationalError):
                _LOGGER.exception(
                    "Could not modify column %s in table %s", column_def, table_name
                )


def _update_states_table_with_foreign_key_options(
    session_maker: Callable[[], Session], engine: Engine
) -> None:
    """Add the options to foreign key constraints."""
    inspector = sqlalchemy.inspect(engine)
    alters = []
    for foreign_key in inspector.get_foreign_keys(TABLE_STATES):
        if foreign_key["name"] and (
            # MySQL/MariaDB will have empty options
            not foreign_key.get("options")
            or
            # Postgres will have ondelete set to None
            foreign_key.get("options", {}).get("ondelete") is None
        ):
            alters.append(
                {
                    "old_fk": ForeignKeyConstraint((), (), name=foreign_key["name"]),
                    "columns": foreign_key["constrained_columns"],
                }
            )

    if not alters:
        return

    states_key_constraints = Base.metadata.tables[TABLE_STATES].foreign_key_constraints
    old_states_table = Table(  # noqa: F841 pylint: disable=unused-variable
        TABLE_STATES, MetaData(), *(alter["old_fk"] for alter in alters)  # type: ignore[arg-type]
    )

    for alter in alters:
        with session_scope(session=session_maker()) as session:
            try:
                connection = session.connection()
                connection.execute(DropConstraint(alter["old_fk"]))  # type: ignore[no-untyped-call]
                for fkc in states_key_constraints:
                    if fkc.column_keys == alter["columns"]:
                        connection.execute(AddConstraint(fkc))  # type: ignore[no-untyped-call]
            except (InternalError, OperationalError):
                _LOGGER.exception(
                    "Could not update foreign options in %s table", TABLE_STATES
                )


def _drop_foreign_key_constraints(
    session_maker: Callable[[], Session], engine: Engine, table: str, columns: list[str]
) -> None:
    """Drop foreign key constraints for a table on specific columns."""
    inspector = sqlalchemy.inspect(engine)
    drops = []
    for foreign_key in inspector.get_foreign_keys(table):
        if foreign_key["name"] and foreign_key["constrained_columns"] == columns:
            drops.append(ForeignKeyConstraint((), (), name=foreign_key["name"]))

    # Bind the ForeignKeyConstraints to the table
    old_table = Table(  # noqa: F841 pylint: disable=unused-variable
        table, MetaData(), *drops
    )

    for drop in drops:
        with session_scope(session=session_maker()) as session:
            try:
                connection = session.connection()
                connection.execute(DropConstraint(drop))  # type: ignore[no-untyped-call]
            except (InternalError, OperationalError):
                _LOGGER.exception(
                    "Could not drop foreign constraints in %s table on %s",
                    TABLE_STATES,
                    columns,
                )


@database_job_retry_wrapper("Apply migration update", 10)
def _apply_update(  # noqa: C901
    instance: Recorder,
    hass: HomeAssistant,
    engine: Engine,
    session_maker: Callable[[], Session],
    new_version: int,
    old_version: int,
) -> None:
    """Perform operations to bring schema up to date."""
    assert engine.dialect.name is not None, "Dialect name must be set"
    dialect = try_parse_enum(SupportedDialect, engine.dialect.name)
    _column_types = _COLUMN_TYPES_FOR_DIALECT.get(dialect, _SQLITE_COLUMN_TYPES)
    if new_version == 1:
        # This used to create ix_events_time_fired, but it was removed in version 32
        pass
    elif new_version == 2:
        # Create compound start/end index for recorder_runs
        _create_index(session_maker, "recorder_runs", "ix_recorder_runs_start_end")
        # This used to create ix_states_last_updated bit it was removed in version 32
    elif new_version == 3:
        # There used to be a new index here, but it was removed in version 4.
        pass
    elif new_version == 4:
        # Queries were rewritten in this schema release. Most indexes from
        # earlier versions of the schema are no longer needed.

        if old_version == 3:
            # Remove index that was added in version 3
            _drop_index(session_maker, "states", "ix_states_created_domain")
        if old_version == 2:
            # Remove index that was added in version 2
            _drop_index(session_maker, "states", "ix_states_entity_id_created")

        # Remove indexes that were added in version 0
        _drop_index(session_maker, "states", "states__state_changes")
        _drop_index(session_maker, "states", "states__significant_changes")
        _drop_index(session_maker, "states", "ix_states_entity_id_created")
        # This used to create ix_states_entity_id_last_updated,
        # but it was removed in version 32
    elif new_version == 5:
        # Create supporting index for States.event_id foreign key
        _create_index(session_maker, "states", LEGACY_STATES_EVENT_ID_INDEX)
    elif new_version == 6:
        _add_columns(
            session_maker,
            "events",
            ["context_id CHARACTER(36)", "context_user_id CHARACTER(36)"],
        )
        _create_index(session_maker, "events", "ix_events_context_id")
        # This used to create ix_events_context_user_id,
        # but it was removed in version 28
        _add_columns(
            session_maker,
            "states",
            ["context_id CHARACTER(36)", "context_user_id CHARACTER(36)"],
        )
        _create_index(session_maker, "states", "ix_states_context_id")
        # This used to create ix_states_context_user_id,
        # but it was removed in version 28
    elif new_version == 7:
        # There used to be a ix_states_entity_id index here,
        # but it was removed in later schema
        pass
    elif new_version == 8:
        _add_columns(session_maker, "events", ["context_parent_id CHARACTER(36)"])
        _add_columns(session_maker, "states", ["old_state_id INTEGER"])
        # This used to create ix_events_context_parent_id,
        # but it was removed in version 28
    elif new_version == 9:
        # We now get the context from events with a join
        # since its always there on state_changed events
        #
        # Ideally we would drop the columns from the states
        # table as well but sqlite doesn't support that
        # and we would have to move to something like
        # sqlalchemy alembic to make that work
        #
        # no longer dropping ix_states_context_id since its recreated in 28
        _drop_index(session_maker, "states", "ix_states_context_user_id")
        # This index won't be there if they were not running
        # nightly but we don't treat that as a critical issue
        _drop_index(session_maker, "states", "ix_states_context_parent_id")
        # Redundant keys on composite index:
        # We already have ix_states_entity_id_last_updated
        _drop_index(session_maker, "states", "ix_states_entity_id")
        # This used to create ix_events_event_type_time_fired,
        # but it was removed in version 32
        _drop_index(session_maker, "events", "ix_events_event_type")
    elif new_version == 10:
        # Now done in step 11
        pass
    elif new_version == 11:
        _create_index(session_maker, "states", "ix_states_old_state_id")
        _update_states_table_with_foreign_key_options(session_maker, engine)
    elif new_version == 12:
        if engine.dialect.name == SupportedDialect.MYSQL:
            _modify_columns(session_maker, engine, "events", ["event_data LONGTEXT"])
            _modify_columns(session_maker, engine, "states", ["attributes LONGTEXT"])
    elif new_version == 13:
        if engine.dialect.name == SupportedDialect.MYSQL:
            _modify_columns(
                session_maker,
                engine,
                "events",
                ["time_fired DATETIME(6)", "created DATETIME(6)"],
            )
            _modify_columns(
                session_maker,
                engine,
                "states",
                [
                    "last_changed DATETIME(6)",
                    "last_updated DATETIME(6)",
                    "created DATETIME(6)",
                ],
            )
    elif new_version == 14:
        _modify_columns(session_maker, engine, "events", ["event_type VARCHAR(64)"])
    elif new_version == 15:
        # This dropped the statistics table, done again in version 18.
        pass
    elif new_version == 16:
        _drop_foreign_key_constraints(
            session_maker, engine, TABLE_STATES, ["old_state_id"]
        )
    elif new_version == 17:
        # This dropped the statistics table, done again in version 18.
        pass
    elif new_version == 18:
        # Recreate the statistics and statistics meta tables.
        #
        # Order matters! Statistics and StatisticsShortTerm have a relation with
        # StatisticsMeta, so statistics need to be deleted before meta (or in pair
        # depending on the SQL backend); and meta needs to be created before statistics.

        # We need to cast __table__ to Table, explanation in
        # https://github.com/sqlalchemy/sqlalchemy/issues/9130
        Base.metadata.drop_all(
            bind=engine,
            tables=[
                cast(Table, StatisticsShortTerm.__table__),
                cast(Table, Statistics.__table__),
                cast(Table, StatisticsMeta.__table__),
            ],
        )

        cast(Table, StatisticsMeta.__table__).create(engine)
        cast(Table, StatisticsShortTerm.__table__).create(engine)
        cast(Table, Statistics.__table__).create(engine)
    elif new_version == 19:
        # This adds the statistic runs table, insert a fake run to prevent duplicating
        # statistics.
        with session_scope(session=session_maker()) as session:
            session.add(StatisticsRuns(start=get_start_time()))
    elif new_version == 20:
        # This changed the precision of statistics from float to double
        if engine.dialect.name in [SupportedDialect.MYSQL, SupportedDialect.POSTGRESQL]:
            _modify_columns(
                session_maker,
                engine,
                "statistics",
                [
                    f"{column} {DOUBLE_PRECISION_TYPE_SQL}"
                    for column in ("max", "mean", "min", "state", "sum")
                ],
            )
    elif new_version == 21:
        # Try to change the character set of the statistic_meta table
        if engine.dialect.name == SupportedDialect.MYSQL:
            for table in ("events", "states", "statistics_meta"):
                _correct_table_character_set_and_collation(table, session_maker)
    elif new_version == 22:
        # Recreate the all statistics tables for Oracle DB with Identity columns
        #
        # Order matters! Statistics has a relation with StatisticsMeta,
        # so statistics need to be deleted before meta (or in pair depending
        # on the SQL backend); and meta needs to be created before statistics.
        if engine.dialect.name == "oracle":
            # We need to cast __table__ to Table, explanation in
            # https://github.com/sqlalchemy/sqlalchemy/issues/9130
            Base.metadata.drop_all(
                bind=engine,
                tables=[
                    cast(Table, StatisticsShortTerm.__table__),
                    cast(Table, Statistics.__table__),
                    cast(Table, StatisticsMeta.__table__),
                    cast(Table, StatisticsRuns.__table__),
                ],
            )

            cast(Table, StatisticsRuns.__table__).create(engine)
            cast(Table, StatisticsMeta.__table__).create(engine)
            cast(Table, StatisticsShortTerm.__table__).create(engine)
            cast(Table, Statistics.__table__).create(engine)

        # Block 5-minute statistics for one hour from the last run, or it will overlap
        # with existing hourly statistics. Don't block on a database with no existing
        # statistics.
        with session_scope(session=session_maker()) as session:
            if session.query(Statistics.id).count() and (
                last_run_string := session.query(
                    # https://github.com/sqlalchemy/sqlalchemy/issues/9189
                    # pylint: disable-next=not-callable
                    func.max(StatisticsRuns.start)
                ).scalar()
            ):
                last_run_start_time = process_timestamp(last_run_string)
                if last_run_start_time:
                    fake_start_time = last_run_start_time + timedelta(minutes=5)
                    while fake_start_time < last_run_start_time + timedelta(hours=1):
                        session.add(StatisticsRuns(start=fake_start_time))
                        fake_start_time += timedelta(minutes=5)

        # When querying the database, be careful to only explicitly query for columns
        # which were present in schema version 22. If querying the table, SQLAlchemy
        # will refer to future columns.
        with session_scope(session=session_maker()) as session:
            for sum_statistic in session.query(StatisticsMeta.id).filter_by(
                has_sum=true()
            ):
                last_statistic = (
                    session.query(
                        Statistics.start,
                        Statistics.last_reset,
                        Statistics.state,
                        Statistics.sum,
                    )
                    .filter_by(metadata_id=sum_statistic.id)
                    .order_by(Statistics.start.desc())
                    .first()
                )
                if last_statistic:
                    session.add(
                        StatisticsShortTerm(
                            metadata_id=sum_statistic.id,
                            start=last_statistic.start,
                            last_reset=last_statistic.last_reset,
                            state=last_statistic.state,
                            sum=last_statistic.sum,
                        )
                    )
    elif new_version == 23:
        # Add name column to StatisticsMeta
        _add_columns(session_maker, "statistics_meta", ["name VARCHAR(255)"])
    elif new_version == 24:
        # This used to create the unique indices for start and statistic_id
        # but we changed the format in schema 34 which will now take care
        # of removing any duplicate if they still exist.
        pass
    elif new_version == 25:
        _add_columns(
            session_maker, "states", [f"attributes_id {_column_types.big_int_type}"]
        )
        _create_index(session_maker, "states", "ix_states_attributes_id")
    elif new_version == 26:
        _create_index(session_maker, "statistics_runs", "ix_statistics_runs_start")
    elif new_version == 27:
        _add_columns(session_maker, "events", [f"data_id {_column_types.big_int_type}"])
        _create_index(session_maker, "events", "ix_events_data_id")
    elif new_version == 28:
        _add_columns(session_maker, "events", ["origin_idx INTEGER"])
        # We never use the user_id or parent_id index
        _drop_index(session_maker, "events", "ix_events_context_user_id")
        _drop_index(session_maker, "events", "ix_events_context_parent_id")
        _add_columns(
            session_maker,
            "states",
            [
                "origin_idx INTEGER",
                "context_id VARCHAR(36)",
                "context_user_id VARCHAR(36)",
                "context_parent_id VARCHAR(36)",
            ],
        )
        _create_index(session_maker, "states", "ix_states_context_id")
        # Once there are no longer any state_changed events
        # in the events table we can drop the index on states.event_id
    elif new_version == 29:
        # Recreate statistics_meta index to block duplicated statistic_id
        _drop_index(session_maker, "statistics_meta", "ix_statistics_meta_statistic_id")
        if engine.dialect.name == SupportedDialect.MYSQL:
            # Ensure the row format is dynamic or the index
            # unique will be too large
            with contextlib.suppress(SQLAlchemyError), session_scope(
                session=session_maker()
            ) as session:
                connection = session.connection()
                # This is safe to run multiple times and fast
                # since the table is small.
                connection.execute(
                    text("ALTER TABLE statistics_meta ROW_FORMAT=DYNAMIC")
                )
        try:
            _create_index(
                session_maker, "statistics_meta", "ix_statistics_meta_statistic_id"
            )
        except DatabaseError:
            # There may be duplicated statistics_meta entries, delete duplicates
            # and try again
            with session_scope(session=session_maker()) as session:
                delete_statistics_meta_duplicates(instance, session)
            _create_index(
                session_maker, "statistics_meta", "ix_statistics_meta_statistic_id"
            )
    elif new_version == 30:
        # This added a column to the statistics_meta table, removed again before
        # release of HA Core 2022.10.0
        # SQLite 3.31.0 does not support dropping columns.
        # Once we require SQLite >= 3.35.5, we should drop the column:
        # ALTER TABLE statistics_meta DROP COLUMN state_unit_of_measurement
        pass
    elif new_version == 31:
        # Once we require SQLite >= 3.35.5, we should drop the column:
        # ALTER TABLE events DROP COLUMN time_fired
        # ALTER TABLE states DROP COLUMN last_updated
        # ALTER TABLE states DROP COLUMN last_changed
        _add_columns(
            session_maker, "events", [f"time_fired_ts {_column_types.timestamp_type}"]
        )
        _add_columns(
            session_maker,
            "states",
            [
                f"last_updated_ts {_column_types.timestamp_type}",
                f"last_changed_ts {_column_types.timestamp_type}",
            ],
        )
        _create_index(session_maker, "events", "ix_events_time_fired_ts")
        _create_index(session_maker, "events", "ix_events_event_type_time_fired_ts")
        _create_index(session_maker, "states", "ix_states_entity_id_last_updated_ts")
        _create_index(session_maker, "states", "ix_states_last_updated_ts")
        _migrate_columns_to_timestamp(instance, session_maker, engine)
    elif new_version == 32:
        # Migration is done in two steps to ensure we can start using
        # the new columns before we wipe the old ones.
        _drop_index(session_maker, "states", "ix_states_entity_id_last_updated")
        _drop_index(session_maker, "events", "ix_events_event_type_time_fired")
        _drop_index(session_maker, "states", "ix_states_last_updated")
        _drop_index(session_maker, "events", "ix_events_time_fired")
    elif new_version == 33:
        # This index is no longer used and can cause MySQL to use the wrong index
        # when querying the states table.
        # https://github.com/home-assistant/core/issues/83787
        # There was an index cleanup here but its now done in schema 39
        pass
    elif new_version == 34:
        # Once we require SQLite >= 3.35.5, we should drop the columns:
        # ALTER TABLE statistics DROP COLUMN created
        # ALTER TABLE statistics DROP COLUMN start
        # ALTER TABLE statistics DROP COLUMN last_reset
        # ALTER TABLE statistics_short_term DROP COLUMN created
        # ALTER TABLE statistics_short_term DROP COLUMN start
        # ALTER TABLE statistics_short_term DROP COLUMN last_reset
        _add_columns(
            session_maker,
            "statistics",
            [
                f"created_ts {_column_types.timestamp_type}",
                f"start_ts {_column_types.timestamp_type}",
                f"last_reset_ts {_column_types.timestamp_type}",
            ],
        )
        _add_columns(
            session_maker,
            "statistics_short_term",
            [
                f"created_ts {_column_types.timestamp_type}",
                f"start_ts {_column_types.timestamp_type}",
                f"last_reset_ts {_column_types.timestamp_type}",
            ],
        )
        _create_index(session_maker, "statistics", "ix_statistics_start_ts")
        _create_index(
            session_maker, "statistics", "ix_statistics_statistic_id_start_ts"
        )
        _create_index(
            session_maker, "statistics_short_term", "ix_statistics_short_term_start_ts"
        )
        _create_index(
            session_maker,
            "statistics_short_term",
            "ix_statistics_short_term_statistic_id_start_ts",
        )
        try:
            _migrate_statistics_columns_to_timestamp(instance, session_maker, engine)
        except IntegrityError as ex:
            _LOGGER.error(
                "Statistics table contains duplicate entries: %s; "
                "Cleaning up duplicates and trying again; "
                "This will take a while; "
                "Please be patient!",
                ex,
            )
            # There may be duplicated statistics entries, delete duplicates
            # and try again
            with session_scope(session=session_maker()) as session:
                delete_statistics_duplicates(instance, hass, session)
            _migrate_statistics_columns_to_timestamp(instance, session_maker, engine)
            # Log at error level to ensure the user sees this message in the log
            # since we logged the error above.
            _LOGGER.error(
                "Statistics migration successfully recovered after statistics table duplicate cleanup"
            )
    elif new_version == 35:
        # Migration is done in two steps to ensure we can start using
        # the new columns before we wipe the old ones.
        _drop_index(
            session_maker, "statistics", "ix_statistics_statistic_id_start", quiet=True
        )
        _drop_index(
            session_maker,
            "statistics_short_term",
            "ix_statistics_short_term_statistic_id_start",
            quiet=True,
        )
        # ix_statistics_start and ix_statistics_statistic_id_start are still used
        # for the post migration cleanup and can be removed in a future version.
    elif new_version == 36:
        for table in ("states", "events"):
            _add_columns(
                session_maker,
                table,
                [
                    f"context_id_bin {_column_types.context_bin_type}",
                    f"context_user_id_bin {_column_types.context_bin_type}",
                    f"context_parent_id_bin {_column_types.context_bin_type}",
                ],
            )
        _create_index(session_maker, "events", "ix_events_context_id_bin")
        _create_index(session_maker, "states", "ix_states_context_id_bin")
    elif new_version == 37:
        _add_columns(
            session_maker, "events", [f"event_type_id {_column_types.big_int_type}"]
        )
        _create_index(session_maker, "events", "ix_events_event_type_id")
        _drop_index(session_maker, "events", "ix_events_event_type_time_fired_ts")
        _create_index(session_maker, "events", "ix_events_event_type_id_time_fired_ts")
    elif new_version == 38:
        _add_columns(
            session_maker, "states", [f"metadata_id {_column_types.big_int_type}"]
        )
        _create_index(session_maker, "states", "ix_states_metadata_id")
        _create_index(session_maker, "states", "ix_states_metadata_id_last_updated_ts")
    elif new_version == 39:
        # Dropping indexes with PostgreSQL never worked correctly if there was a prefix
        # so we need to cleanup leftover indexes.
        _drop_index(
            session_maker, "events", "ix_events_event_type_time_fired_ts", quiet=True
        )
        _drop_index(session_maker, "events", "ix_events_event_type", quiet=True)
        _drop_index(
            session_maker, "events", "ix_events_event_type_time_fired", quiet=True
        )
        _drop_index(session_maker, "events", "ix_events_time_fired", quiet=True)
        _drop_index(session_maker, "events", "ix_events_context_user_id", quiet=True)
        _drop_index(session_maker, "events", "ix_events_context_parent_id", quiet=True)
        _drop_index(
            session_maker, "states", "ix_states_entity_id_last_updated", quiet=True
        )
        _drop_index(session_maker, "states", "ix_states_last_updated", quiet=True)
        _drop_index(session_maker, "states", "ix_states_entity_id", quiet=True)
        _drop_index(session_maker, "states", "ix_states_context_user_id", quiet=True)
        _drop_index(session_maker, "states", "ix_states_context_parent_id", quiet=True)
        _drop_index(session_maker, "states", "ix_states_created_domain", quiet=True)
        _drop_index(session_maker, "states", "ix_states_entity_id_created", quiet=True)
        _drop_index(session_maker, "states", "states__state_changes", quiet=True)
        _drop_index(session_maker, "states", "states__significant_changes", quiet=True)
        _drop_index(session_maker, "states", "ix_states_entity_id_created", quiet=True)
        _drop_index(
            session_maker, "statistics", "ix_statistics_statistic_id_start", quiet=True
        )
        _drop_index(
            session_maker,
            "statistics_short_term",
            "ix_statistics_short_term_statistic_id_start",
            quiet=True,
        )
    elif new_version == 40:
        # ix_events_event_type_id is a left-prefix of ix_events_event_type_id_time_fired_ts
        _drop_index(session_maker, "events", "ix_events_event_type_id")
        # ix_states_metadata_id is a left-prefix of ix_states_metadata_id_last_updated_ts
        _drop_index(session_maker, "states", "ix_states_metadata_id")
        # ix_statistics_metadata_id is a left-prefix of ix_statistics_statistic_id_start_ts
        _drop_index(session_maker, "statistics", "ix_statistics_metadata_id")
        # ix_statistics_short_term_metadata_id is a left-prefix of ix_statistics_short_term_statistic_id_start_ts
        _drop_index(
            session_maker,
            "statistics_short_term",
            "ix_statistics_short_term_metadata_id",
        )
    elif new_version == 41:
        _create_index(session_maker, "event_types", "ix_event_types_event_type")
        _create_index(session_maker, "states_meta", "ix_states_meta_entity_id")
    else:
        raise ValueError(f"No schema migration defined for version {new_version}")


def _correct_table_character_set_and_collation(
    table: str,
    session_maker: Callable[[], Session],
) -> None:
    """Correct issues detected by validate_db_schema."""
    # Attempt to convert the table to utf8mb4
    _LOGGER.warning(
        "Updating character set and collation of table %s to utf8mb4. "
        "Note: this can take several minutes on large databases and slow "
        "computers. Please be patient!",
        table,
    )
    with contextlib.suppress(SQLAlchemyError), session_scope(
        session=session_maker()
    ) as session:
        connection = session.connection()
        connection.execute(
            # Using LOCK=EXCLUSIVE to prevent the database from corrupting
            # https://github.com/home-assistant/core/issues/56104
            text(
                f"ALTER TABLE {table} CONVERT TO CHARACTER SET "
                f"{MYSQL_DEFAULT_CHARSET} "
                f"COLLATE {MYSQL_COLLATE}, LOCK=EXCLUSIVE"
            )
        )


def post_schema_migration(
    instance: Recorder,
    old_version: int,
    new_version: int,
) -> None:
    """Post schema migration.

    Run any housekeeping tasks after the schema migration has completed.

    Post schema migration is run after the schema migration has completed
    and the queue has been processed to ensure that we reduce the memory
    pressure since events are held in memory until the queue is processed
    which is blocked from being processed until the schema migration is
    complete.
    """
    if old_version < 32 <= new_version:
        # In version 31 we migrated all the time_fired, last_updated, and last_changed
        # columns to be timestamps. In version 32 we need to wipe the old columns
        # since they are no longer used and take up a significant amount of space.
        assert instance.event_session is not None
        assert instance.engine is not None
        _wipe_old_string_time_columns(instance, instance.engine, instance.event_session)
    if old_version < 35 <= new_version:
        # In version 34 we migrated all the created, start, and last_reset
        # columns to be timestamps. In version 34 we need to wipe the old columns
        # since they are no longer used and take up a significant amount of space.
        _wipe_old_string_statistics_columns(instance)


def _wipe_old_string_statistics_columns(instance: Recorder) -> None:
    """Wipe old string statistics columns to save space."""
    instance.queue_task(StatisticsTimestampMigrationCleanupTask())


@database_job_retry_wrapper("Wipe old string time columns", 3)
def _wipe_old_string_time_columns(
    instance: Recorder, engine: Engine, session: Session
) -> None:
    """Wipe old string time columns to save space."""
    # Wipe Events.time_fired since its been replaced by Events.time_fired_ts
    # Wipe States.last_updated since its been replaced by States.last_updated_ts
    # Wipe States.last_changed since its been replaced by States.last_changed_ts
    #
    if engine.dialect.name == SupportedDialect.SQLITE:
        session.execute(text("UPDATE events set time_fired=NULL;"))
        session.commit()
        session.execute(text("UPDATE states set last_updated=NULL, last_changed=NULL;"))
        session.commit()
    elif engine.dialect.name == SupportedDialect.MYSQL:
        #
        # Since this is only to save space we limit the number of rows we update
        # to 100,000 per table since we do not want to block the database for too long
        # or run out of innodb_buffer_pool_size on MySQL. The old data will eventually
        # be cleaned up by the recorder purge if we do not do it now.
        #
        session.execute(text("UPDATE events set time_fired=NULL LIMIT 100000;"))
        session.commit()
        session.execute(
            text(
                "UPDATE states set last_updated=NULL, last_changed=NULL "
                " LIMIT 100000;"
            )
        )
        session.commit()
    elif engine.dialect.name == SupportedDialect.POSTGRESQL:
        #
        # Since this is only to save space we limit the number of rows we update
        # to 100,000 per table since we do not want to block the database for too long
        # or run out ram with postgresql. The old data will eventually
        # be cleaned up by the recorder purge if we do not do it now.
        #
        session.execute(
            text(
                "UPDATE events set time_fired=NULL "
                "where event_id in "
                "(select event_id from events where time_fired_ts is NOT NULL LIMIT 100000);"
            )
        )
        session.commit()
        session.execute(
            text(
                "UPDATE states set last_updated=NULL, last_changed=NULL "
                "where state_id in "
                "(select state_id from states where last_updated_ts is NOT NULL LIMIT 100000);"
            )
        )
        session.commit()


@database_job_retry_wrapper("Migrate columns to timestamp", 3)
def _migrate_columns_to_timestamp(
    instance: Recorder, session_maker: Callable[[], Session], engine: Engine
) -> None:
    """Migrate columns to use timestamp."""
    # Migrate all data in Events.time_fired to Events.time_fired_ts
    # Migrate all data in States.last_updated to States.last_updated_ts
    # Migrate all data in States.last_changed to States.last_changed_ts
    result: CursorResult | None = None
    if engine.dialect.name == SupportedDialect.SQLITE:
        # With SQLite we do this in one go since it is faster
        with session_scope(session=session_maker()) as session:
            connection = session.connection()
            connection.execute(
                text(
                    'UPDATE events set time_fired_ts=strftime("%s",time_fired) + '
                    "cast(substr(time_fired,-7) AS FLOAT);"
                )
            )
            connection.execute(
                text(
                    'UPDATE states set last_updated_ts=strftime("%s",last_updated) + '
                    "cast(substr(last_updated,-7) AS FLOAT), "
                    'last_changed_ts=strftime("%s",last_changed) + '
                    "cast(substr(last_changed,-7) AS FLOAT);"
                )
            )
    elif engine.dialect.name == SupportedDialect.MYSQL:
        # With MySQL we do this in chunks to avoid hitting the `innodb_buffer_pool_size` limit
        # We also need to do this in a loop since we can't be sure that we have
        # updated all rows in the table until the rowcount is 0
        while result is None or result.rowcount > 0:
            with session_scope(session=session_maker()) as session:
                result = session.connection().execute(
                    text(
                        "UPDATE events set time_fired_ts="
                        "IF(time_fired is NULL or UNIX_TIMESTAMP(time_fired) is NULL,0,"
                        "UNIX_TIMESTAMP(time_fired)"
                        ") "
                        "where time_fired_ts is NULL "
                        "LIMIT 100000;"
                    )
                )
        result = None
        while result is None or result.rowcount > 0:  # type: ignore[unreachable]
            with session_scope(session=session_maker()) as session:
                result = session.connection().execute(
                    text(
                        "UPDATE states set last_updated_ts="
                        "IF(last_updated is NULL or UNIX_TIMESTAMP(last_updated) is NULL,0,"
                        "UNIX_TIMESTAMP(last_updated) "
                        "), "
                        "last_changed_ts="
                        "UNIX_TIMESTAMP(last_changed) "
                        "where last_updated_ts is NULL "
                        "LIMIT 100000;"
                    )
                )
    elif engine.dialect.name == SupportedDialect.POSTGRESQL:
        # With Postgresql we do this in chunks to avoid using too much memory
        # We also need to do this in a loop since we can't be sure that we have
        # updated all rows in the table until the rowcount is 0
        while result is None or result.rowcount > 0:
            with session_scope(session=session_maker()) as session:
                result = session.connection().execute(
                    text(
                        "UPDATE events SET "
                        "time_fired_ts= "
                        "(case when time_fired is NULL then 0 else EXTRACT(EPOCH FROM time_fired::timestamptz) end) "
                        "WHERE event_id IN ( "
                        "SELECT event_id FROM events where time_fired_ts is NULL LIMIT 100000 "
                        " );"
                    )
                )
        result = None
        while result is None or result.rowcount > 0:  # type: ignore[unreachable]
            with session_scope(session=session_maker()) as session:
                result = session.connection().execute(
                    text(
                        "UPDATE states set last_updated_ts="
                        "(case when last_updated is NULL then 0 else EXTRACT(EPOCH FROM last_updated::timestamptz) end), "
                        "last_changed_ts=EXTRACT(EPOCH FROM last_changed::timestamptz) "
                        "where state_id IN ( "
                        "SELECT state_id FROM states where last_updated_ts is NULL LIMIT 100000 "
                        " );"
                    )
                )


@database_job_retry_wrapper("Migrate statistics columns to timestamp", 3)
def _migrate_statistics_columns_to_timestamp(
    instance: Recorder, session_maker: Callable[[], Session], engine: Engine
) -> None:
    """Migrate statistics columns to use timestamp."""
    # Migrate all data in statistics.start to statistics.start_ts
    # Migrate all data in statistics.created to statistics.created_ts
    # Migrate all data in statistics.last_reset to statistics.last_reset_ts
    # Migrate all data in statistics_short_term.start to statistics_short_term.start_ts
    # Migrate all data in statistics_short_term.created to statistics_short_term.created_ts
    # Migrate all data in statistics_short_term.last_reset to statistics_short_term.last_reset_ts
    result: CursorResult | None = None
    if engine.dialect.name == SupportedDialect.SQLITE:
        # With SQLite we do this in one go since it is faster
        for table in STATISTICS_TABLES:
            with session_scope(session=session_maker()) as session:
                session.connection().execute(
                    text(
                        f"UPDATE {table} set start_ts=strftime('%s',start) + "  # noqa: S608
                        "cast(substr(start,-7) AS FLOAT), "
                        f"created_ts=strftime('%s',created) + "
                        "cast(substr(created,-7) AS FLOAT), "
                        f"last_reset_ts=strftime('%s',last_reset) + "
                        "cast(substr(last_reset,-7) AS FLOAT);"
                    )
                )
    elif engine.dialect.name == SupportedDialect.MYSQL:
        # With MySQL we do this in chunks to avoid hitting the `innodb_buffer_pool_size` limit
        # We also need to do this in a loop since we can't be sure that we have
        # updated all rows in the table until the rowcount is 0
        for table in STATISTICS_TABLES:
            result = None
            while result is None or result.rowcount > 0:  # type: ignore[unreachable]
                with session_scope(session=session_maker()) as session:
                    result = session.connection().execute(
                        text(
                            f"UPDATE {table} set start_ts="  # noqa: S608
                            "IF(start is NULL or UNIX_TIMESTAMP(start) is NULL,0,"
                            "UNIX_TIMESTAMP(start) "
                            "), "
                            "created_ts="
                            "UNIX_TIMESTAMP(created), "
                            "last_reset_ts="
                            "UNIX_TIMESTAMP(last_reset) "
                            "where start_ts is NULL "
                            "LIMIT 100000;"
                        )
                    )
    elif engine.dialect.name == SupportedDialect.POSTGRESQL:
        # With Postgresql we do this in chunks to avoid using too much memory
        # We also need to do this in a loop since we can't be sure that we have
        # updated all rows in the table until the rowcount is 0
        for table in STATISTICS_TABLES:
            result = None
            while result is None or result.rowcount > 0:  # type: ignore[unreachable]
                with session_scope(session=session_maker()) as session:
                    result = session.connection().execute(
                        text(
                            f"UPDATE {table} set start_ts="  # noqa: S608
                            "(case when start is NULL then 0 else EXTRACT(EPOCH FROM start::timestamptz) end), "
                            "created_ts=EXTRACT(EPOCH FROM created::timestamptz), "
                            "last_reset_ts=EXTRACT(EPOCH FROM last_reset::timestamptz) "
                            "where id IN ("
                            f"SELECT id FROM {table} where start_ts is NULL LIMIT 100000"
                            ");"
                        )
                    )


def _context_id_to_bytes(context_id: str | None) -> bytes | None:
    """Convert a context_id to bytes."""
    if context_id is None:
        return None
    with contextlib.suppress(ValueError):
        # There may be garbage in the context_id column
        # from custom integrations that are not UUIDs or
        # ULIDs that filled the column to the max length
        # so we need to catch the ValueError and return
        # None if it happens
        if len(context_id) == 26:
            return ulid_to_bytes(context_id)
        return UUID(context_id).bytes
    return None


def _generate_ulid_bytes_at_time(timestamp: float | None) -> bytes:
    """Generate a ulid with a specific timestamp."""
    return ulid_to_bytes(ulid_at_time(timestamp or time()))


@retryable_database_job("migrate states context_ids to binary format")
def migrate_states_context_ids(instance: Recorder) -> bool:
    """Migrate states context_ids to use binary format."""
    _to_bytes = _context_id_to_bytes
    session_maker = instance.get_session
    _LOGGER.debug("Migrating states context_ids to binary format")
    with session_scope(session=session_maker()) as session:
        if states := session.execute(find_states_context_ids_to_migrate()).all():
            session.execute(
                update(States),
                [
                    {
                        "state_id": state_id,
                        "context_id": None,
                        "context_id_bin": _to_bytes(context_id)
                        or _generate_ulid_bytes_at_time(last_updated_ts),
                        "context_user_id": None,
                        "context_user_id_bin": _to_bytes(context_user_id),
                        "context_parent_id": None,
                        "context_parent_id_bin": _to_bytes(context_parent_id),
                    }
                    for state_id, last_updated_ts, context_id, context_user_id, context_parent_id in states
                ],
            )
        # If there is more work to do return False
        # so that we can be called again
        is_done = not states

    if is_done:
        _drop_index(session_maker, "states", "ix_states_context_id")

    _LOGGER.debug("Migrating states context_ids to binary format: done=%s", is_done)
    return is_done


@retryable_database_job("migrate events context_ids to binary format")
def migrate_events_context_ids(instance: Recorder) -> bool:
    """Migrate events context_ids to use binary format."""
    _to_bytes = _context_id_to_bytes
    session_maker = instance.get_session
    _LOGGER.debug("Migrating context_ids to binary format")
    with session_scope(session=session_maker()) as session:
        if events := session.execute(find_events_context_ids_to_migrate()).all():
            session.execute(
                update(Events),
                [
                    {
                        "event_id": event_id,
                        "context_id": None,
                        "context_id_bin": _to_bytes(context_id)
                        or _generate_ulid_bytes_at_time(time_fired_ts),
                        "context_user_id": None,
                        "context_user_id_bin": _to_bytes(context_user_id),
                        "context_parent_id": None,
                        "context_parent_id_bin": _to_bytes(context_parent_id),
                    }
                    for event_id, time_fired_ts, context_id, context_user_id, context_parent_id in events
                ],
            )
        # If there is more work to do return False
        # so that we can be called again
        is_done = not events

    if is_done:
        _drop_index(session_maker, "events", "ix_events_context_id")

    _LOGGER.debug("Migrating events context_ids to binary format: done=%s", is_done)
    return is_done


@retryable_database_job("migrate events event_types to event_type_ids")
def migrate_event_type_ids(instance: Recorder) -> bool:
    """Migrate event_type to event_type_ids."""
    session_maker = instance.get_session
    _LOGGER.debug("Migrating event_types")
    event_type_manager = instance.event_type_manager
    with session_scope(session=session_maker()) as session:
        if events := session.execute(find_event_type_to_migrate()).all():
            event_types = {event_type for _, event_type in events}
            if None in event_types:
                # event_type should never be None but we need to be defensive
                # so we don't fail the migration because of a bad state
                event_types.remove(None)
                event_types.add(_EMPTY_EVENT_TYPE)

            event_type_to_id = event_type_manager.get_many(event_types, session)
            if missing_event_types := {
                event_type
                for event_type, event_id in event_type_to_id.items()
                if event_id is None
            }:
                missing_db_event_types = [
                    EventTypes(event_type=event_type)
                    for event_type in missing_event_types
                ]
                session.add_all(missing_db_event_types)
                session.flush()  # Assign ids
                for db_event_type in missing_db_event_types:
                    # We cannot add the assigned ids to the event_type_manager
                    # because the commit could get rolled back
                    assert (
                        db_event_type.event_type is not None
                    ), "event_type should never be None"
                    event_type_to_id[
                        db_event_type.event_type
                    ] = db_event_type.event_type_id
                    event_type_manager.clear_non_existent(db_event_type.event_type)

            session.execute(
                update(Events),
                [
                    {
                        "event_id": event_id,
                        "event_type": None,
                        "event_type_id": event_type_to_id[
                            _EMPTY_EVENT_TYPE if event_type is None else event_type
                        ],
                    }
                    for event_id, event_type in events
                ],
            )

        # If there is more work to do return False
        # so that we can be called again
        is_done = not events

    if is_done:
        instance.event_type_manager.active = True

    _LOGGER.debug("Migrating event_types done=%s", is_done)
    return is_done


@retryable_database_job("migrate states entity_ids to states_meta")
def migrate_entity_ids(instance: Recorder) -> bool:
    """Migrate entity_ids to states_meta.

    We do this in two steps because we need the history queries to work
    while we are migrating.

    1. Link the states to the states_meta table
    2. Remove the entity_id column from the states table (in post_migrate_entity_ids)
    """
    _LOGGER.debug("Migrating entity_ids")
    states_meta_manager = instance.states_meta_manager
    with session_scope(session=instance.get_session()) as session:
        if states := session.execute(find_entity_ids_to_migrate()).all():
            entity_ids = {entity_id for _, entity_id in states}
            if None in entity_ids:
                # entity_id should never be None but we need to be defensive
                # so we don't fail the migration because of a bad state
                entity_ids.remove(None)
                entity_ids.add(_EMPTY_ENTITY_ID)

            entity_id_to_metadata_id = states_meta_manager.get_many(
                entity_ids, session, True
            )
            if missing_entity_ids := {
                entity_id
                for entity_id, metadata_id in entity_id_to_metadata_id.items()
                if metadata_id is None
            }:
                missing_states_metadata = [
                    StatesMeta(entity_id=entity_id) for entity_id in missing_entity_ids
                ]
                session.add_all(missing_states_metadata)
                session.flush()  # Assign ids
                for db_states_metadata in missing_states_metadata:
                    # We cannot add the assigned ids to the event_type_manager
                    # because the commit could get rolled back
                    assert (
                        db_states_metadata.entity_id is not None
                    ), "entity_id should never be None"
                    entity_id_to_metadata_id[
                        db_states_metadata.entity_id
                    ] = db_states_metadata.metadata_id

            session.execute(
                update(States),
                [
                    {
                        "state_id": state_id,
                        # We cannot set "entity_id": None yet since
                        # the history queries still need to work while the
                        # migration is in progress and we will do this in
                        # post_migrate_entity_ids
                        "metadata_id": entity_id_to_metadata_id[
                            _EMPTY_ENTITY_ID if entity_id is None else entity_id
                        ],
                    }
                    for state_id, entity_id in states
                ],
            )

        # If there is more work to do return False
        # so that we can be called again
        is_done = not states

    _LOGGER.debug("Migrating entity_ids done=%s", is_done)
    return is_done


@retryable_database_job("post migrate states entity_ids to states_meta")
def post_migrate_entity_ids(instance: Recorder) -> bool:
    """Remove old entity_id strings from states.

    We cannot do this in migrate_entity_ids since the history queries
    still need to work while the migration is in progress.
    """
    session_maker = instance.get_session
    _LOGGER.debug("Cleanup legacy entity_ids")
    with session_scope(session=session_maker()) as session:
        cursor_result = session.connection().execute(batch_cleanup_entity_ids())
        is_done = not cursor_result or cursor_result.rowcount == 0
        # If there is more work to do return False
        # so that we can be called again

    if is_done:
        # Drop the old indexes since they are no longer needed
        _drop_index(session_maker, "states", LEGACY_STATES_ENTITY_ID_LAST_UPDATED_INDEX)

    _LOGGER.debug("Cleanup legacy entity_ids done=%s", is_done)
    return is_done


@retryable_database_job("cleanup_legacy_event_ids")
def cleanup_legacy_states_event_ids(instance: Recorder) -> bool:
    """Remove old event_id index from states.

    We used to link states to events using the event_id column but we no
    longer store state changed events in the events table.

    If all old states have been purged and existing states are in the new
    format we can drop the index since it can take up ~10MB per 1M rows.
    """
    session_maker = instance.get_session
    _LOGGER.debug("Cleanup legacy entity_ids")
    with session_scope(session=session_maker()) as session:
        result = session.execute(has_used_states_event_ids()).scalar()
        # In the future we may migrate existing states to the new format
        # but in practice very few of these still exist in production and
        # removing the index is the likely all that needs to happen.
        all_gone = not result

    if all_gone:
        # Only drop the index if there are no more event_ids in the states table
        # ex all NULL
        assert instance.engine is not None, "engine should never be None"
        if instance.dialect_name != SupportedDialect.SQLITE:
            # SQLite does not support dropping foreign key constraints
            # so we can't drop the index at this time but we can avoid
            # looking for legacy rows during purge
            _drop_foreign_key_constraints(
                session_maker, instance.engine, TABLE_STATES, ["event_id"]
            )
            _drop_index(session_maker, "states", LEGACY_STATES_EVENT_ID_INDEX)
        instance.use_legacy_events_index = False

    return True


def _initialize_database(session: Session) -> bool:
    """Initialize a new database.

    The function determines the schema version by inspecting the db structure.

    When the schema version is not present in the db, either db was just
    created with the correct schema, or this is a db created before schema
    versions were tracked. For now, we'll test if the changes for schema
    version 1 are present to make the determination. Eventually this logic
    can be removed and we can assume a new db is being created.
    """
    inspector = sqlalchemy.inspect(session.connection())
    indexes = inspector.get_indexes("events")

    for index in indexes:
        if index["column_names"] in (["time_fired"], ["time_fired_ts"]):
            # Schema addition from version 1 detected. New DB.
            session.add(StatisticsRuns(start=get_start_time()))
            session.add(SchemaChanges(schema_version=SCHEMA_VERSION))
            return True

    # Version 1 schema changes not found, this db needs to be migrated.
    current_version = SchemaChanges(schema_version=0)
    session.add(current_version)
    return True


def initialize_database(session_maker: Callable[[], Session]) -> bool:
    """Initialize a new database."""
    try:
        with session_scope(session=session_maker()) as session:
            if _get_schema_version(session) is not None:
                return True
            return _initialize_database(session)

    except Exception as err:  # pylint: disable=broad-except
        _LOGGER.exception("Error when initialise database: %s", err)
        return False
