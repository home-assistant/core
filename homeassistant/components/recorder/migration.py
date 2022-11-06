"""Schema migration helpers."""
from __future__ import annotations

from collections.abc import Callable, Iterable
import contextlib
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import TYPE_CHECKING

import sqlalchemy
from sqlalchemy import ForeignKeyConstraint, MetaData, Table, func, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import (
    DatabaseError,
    InternalError,
    OperationalError,
    ProgrammingError,
    SQLAlchemyError,
)
from sqlalchemy.orm.session import Session
from sqlalchemy.schema import AddConstraint, DropConstraint
from sqlalchemy.sql.expression import true

from homeassistant.core import HomeAssistant

from .const import SupportedDialect
from .db_schema import (
    SCHEMA_VERSION,
    TABLE_STATES,
    Base,
    SchemaChanges,
    Statistics,
    StatisticsMeta,
    StatisticsRuns,
    StatisticsShortTerm,
)
from .models import process_timestamp
from .statistics import (
    delete_statistics_duplicates,
    delete_statistics_meta_duplicates,
    get_start_time,
)
from .util import session_scope

if TYPE_CHECKING:
    from . import Recorder

LIVE_MIGRATION_MIN_SCHEMA_VERSION = 0

_LOGGER = logging.getLogger(__name__)


def raise_if_exception_missing_str(ex: Exception, match_substrs: Iterable[str]) -> None:
    """Raise an exception if the exception and cause do not contain the match substrs."""
    lower_ex_strs = [str(ex).lower(), str(ex.__cause__).lower()]
    for str_sub in match_substrs:
        for exc_str in lower_ex_strs:
            if exc_str and str_sub in exc_str:
                return

    raise ex


def _get_schema_version(session: Session) -> int | None:
    """Get the schema version."""
    res = session.query(SchemaChanges).order_by(SchemaChanges.change_id.desc()).first()
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


def _schema_is_current(current_version: int) -> bool:
    """Check if the schema is current."""
    return current_version == SCHEMA_VERSION


def schema_is_valid(schema_status: SchemaValidationStatus) -> bool:
    """Check if the schema is valid."""
    return _schema_is_current(schema_status.current_version)


def validate_db_schema(
    hass: HomeAssistant, session_maker: Callable[[], Session]
) -> SchemaValidationStatus | None:
    """Check if the schema is valid.

    This checks that the schema is the current version as well as for some common schema
    errors caused by manual migration between database engines, for example importing an
    SQLite database to MariaDB.
    """
    current_version = get_schema_version(session_maker)
    if current_version is None:
        return None

    return SchemaValidationStatus(current_version)


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
    _LOGGER.warning("Database is about to upgrade. Schema version: %s", current_version)
    db_ready = False
    for version in range(current_version, SCHEMA_VERSION):
        if live_migration(SchemaValidationStatus(version)) and not db_ready:
            db_ready = True
            instance.migration_is_live = True
            hass.add_job(instance.async_set_db_ready)
        new_version = version + 1
        _LOGGER.info("Upgrading recorder db schema to version %s", new_version)
        _apply_update(hass, engine, session_maker, new_version, current_version)
        with session_scope(session=session_maker()) as session:
            session.add(SchemaChanges(schema_version=new_version))

        _LOGGER.info("Upgrade to version %s done", new_version)


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
        "Adding index `%s` to database. Note: this can take several "
        "minutes on large databases and slow computers. Please "
        "be patient!",
        index_name,
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


def _drop_index(
    session_maker: Callable[[], Session], table_name: str, index_name: str
) -> None:
    """Drop an index from a specified table.

    There is no universal way to do something like `DROP INDEX IF EXISTS`
    so we will simply execute the DROP command and ignore any exceptions

    WARNING: Due to some engines (MySQL at least) being unable to use bind
    parameters in a DROP INDEX statement (at least via SQLAlchemy), the query
    string here is generated from the method parameters without sanitizing.
    DO NOT USE THIS FUNCTION IN ANY OPERATION THAT TAKES USER INPUT.
    """
    _LOGGER.debug("Dropping index %s from table %s", index_name, table_name)
    success = False

    # Engines like DB2/Oracle
    with session_scope(session=session_maker()) as session:
        try:
            connection = session.connection()
            connection.execute(text(f"DROP INDEX {index_name}"))
        except SQLAlchemyError:
            pass
        else:
            success = True

    # Engines like SQLite, SQL Server
    if not success:
        with session_scope(session=session_maker()) as session:
            try:
                connection = session.connection()
                connection.execute(
                    text(
                        "DROP INDEX {table}.{index}".format(
                            index=index_name, table=table_name
                        )
                    )
                )
            except SQLAlchemyError:
                pass
            else:
                success = True

    if not success:
        # Engines like MySQL, MS Access
        with session_scope(session=session_maker()) as session:
            try:
                connection = session.connection()
                connection.execute(
                    text(
                        "DROP INDEX {index} ON {table}".format(
                            index=index_name, table=table_name
                        )
                    )
                )
            except SQLAlchemyError:
                pass
            else:
                success = True

    if success:
        _LOGGER.debug(
            "Finished dropping index %s from table %s", index_name, table_name
        )
    else:
        if index_name == "ix_states_context_parent_id":
            # Was only there on nightly so we do not want
            # to generate log noise or issues about it.
            return

        _LOGGER.warning(
            "Failed to drop index %s from table %s. Schema "
            "Migration will continue; this is not a "
            "critical operation",
            index_name,
            table_name,
        )


def _add_columns(
    session_maker: Callable[[], Session], table_name: str, columns_def: list[str]
) -> None:
    """Add columns to a table."""
    _LOGGER.warning(
        "Adding columns %s to table %s. Note: this can take several "
        "minutes on large databases and slow computers. Please "
        "be patient!",
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
            "Skipping to modify columns %s in table %s; "
            "Modifying column length in SQLite is unnecessary, "
            "it does not impose any length restrictions",
            ", ".join(column.split(" ")[0] for column in columns_def),
            table_name,
        )
        return

    _LOGGER.warning(
        "Modifying columns %s in table %s. Note: this can take several "
        "minutes on large databases and slow computers. Please "
        "be patient!",
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
        TABLE_STATES, MetaData(), *(alter["old_fk"] for alter in alters)
    )

    for alter in alters:
        with session_scope(session=session_maker()) as session:
            try:
                connection = session.connection()
                connection.execute(DropConstraint(alter["old_fk"]))
                for fkc in states_key_constraints:
                    if fkc.column_keys == alter["columns"]:
                        connection.execute(AddConstraint(fkc))
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
        if (
            foreign_key["name"]
            and foreign_key.get("options", {}).get("ondelete")
            and foreign_key["constrained_columns"] == columns
        ):
            drops.append(ForeignKeyConstraint((), (), name=foreign_key["name"]))

    # Bind the ForeignKeyConstraints to the table
    old_table = Table(  # noqa: F841 pylint: disable=unused-variable
        table, MetaData(), *drops
    )

    for drop in drops:
        with session_scope(session=session_maker()) as session:
            try:
                connection = session.connection()
                connection.execute(DropConstraint(drop))
            except (InternalError, OperationalError):
                _LOGGER.exception(
                    "Could not drop foreign constraints in %s table on %s",
                    TABLE_STATES,
                    columns,
                )


def _apply_update(  # noqa: C901
    hass: HomeAssistant,
    engine: Engine,
    session_maker: Callable[[], Session],
    new_version: int,
    old_version: int,
) -> None:
    """Perform operations to bring schema up to date."""
    dialect = engine.dialect.name
    big_int = "INTEGER(20)" if dialect == SupportedDialect.MYSQL else "INTEGER"

    if new_version == 1:
        _create_index(session_maker, "events", "ix_events_time_fired")
    elif new_version == 2:
        # Create compound start/end index for recorder_runs
        _create_index(session_maker, "recorder_runs", "ix_recorder_runs_start_end")
        # Create indexes for states
        _create_index(session_maker, "states", "ix_states_last_updated")
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

        _create_index(session_maker, "states", "ix_states_entity_id_last_updated")
    elif new_version == 5:
        # Create supporting index for States.event_id foreign key
        _create_index(session_maker, "states", "ix_states_event_id")
    elif new_version == 6:
        _add_columns(
            session_maker,
            "events",
            ["context_id CHARACTER(36)", "context_user_id CHARACTER(36)"],
        )
        _create_index(session_maker, "events", "ix_events_context_id")
        _create_index(session_maker, "events", "ix_events_context_user_id")
        _add_columns(
            session_maker,
            "states",
            ["context_id CHARACTER(36)", "context_user_id CHARACTER(36)"],
        )
        _create_index(session_maker, "states", "ix_states_context_id")
        _create_index(session_maker, "states", "ix_states_context_user_id")
    elif new_version == 7:
        _create_index(session_maker, "states", "ix_states_entity_id")
    elif new_version == 8:
        _add_columns(session_maker, "events", ["context_parent_id CHARACTER(36)"])
        _add_columns(session_maker, "states", ["old_state_id INTEGER"])
        _create_index(session_maker, "events", "ix_events_context_parent_id")
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
        _create_index(session_maker, "events", "ix_events_event_type_time_fired")
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
        Base.metadata.drop_all(
            bind=engine,
            tables=[
                StatisticsShortTerm.__table__,
                Statistics.__table__,
                StatisticsMeta.__table__,
            ],
        )

        StatisticsMeta.__table__.create(engine)
        StatisticsShortTerm.__table__.create(engine)
        Statistics.__table__.create(engine)
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
                    "mean DOUBLE PRECISION",
                    "min DOUBLE PRECISION",
                    "max DOUBLE PRECISION",
                    "state DOUBLE PRECISION",
                    "sum DOUBLE PRECISION",
                ],
            )
    elif new_version == 21:
        # Try to change the character set of the statistic_meta table
        if engine.dialect.name == SupportedDialect.MYSQL:
            for table in ("events", "states", "statistics_meta"):
                _LOGGER.warning(
                    "Updating character set and collation of table %s to utf8mb4. "
                    "Note: this can take several minutes on large databases and slow "
                    "computers. Please be patient!",
                    table,
                )
                with contextlib.suppress(SQLAlchemyError):
                    with session_scope(session=session_maker()) as session:
                        connection = session.connection()
                        connection.execute(
                            # Using LOCK=EXCLUSIVE to prevent the database from corrupting
                            # https://github.com/home-assistant/core/issues/56104
                            text(
                                f"ALTER TABLE {table} CONVERT TO "
                                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci, LOCK=EXCLUSIVE"
                            )
                        )
    elif new_version == 22:
        # Recreate the all statistics tables for Oracle DB with Identity columns
        #
        # Order matters! Statistics has a relation with StatisticsMeta,
        # so statistics need to be deleted before meta (or in pair depending
        # on the SQL backend); and meta needs to be created before statistics.
        if engine.dialect.name == "oracle":
            Base.metadata.drop_all(
                bind=engine,
                tables=[
                    StatisticsShortTerm.__table__,
                    Statistics.__table__,
                    StatisticsMeta.__table__,
                    StatisticsRuns.__table__,
                ],
            )

            StatisticsRuns.__table__.create(engine)
            StatisticsMeta.__table__.create(engine)
            StatisticsShortTerm.__table__.create(engine)
            Statistics.__table__.create(engine)

        # Block 5-minute statistics for one hour from the last run, or it will overlap
        # with existing hourly statistics. Don't block on a database with no existing
        # statistics.
        with session_scope(session=session_maker()) as session:
            if session.query(Statistics.id).count() and (
                last_run_string := session.query(
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
        # Recreate statistics indices to block duplicated statistics
        _drop_index(session_maker, "statistics", "ix_statistics_statistic_id_start")
        _drop_index(
            session_maker,
            "statistics_short_term",
            "ix_statistics_short_term_statistic_id_start",
        )
        try:
            _create_index(
                session_maker, "statistics", "ix_statistics_statistic_id_start"
            )
            _create_index(
                session_maker,
                "statistics_short_term",
                "ix_statistics_short_term_statistic_id_start",
            )
        except DatabaseError:
            # There may be duplicated statistics entries, delete duplicated statistics
            # and try again
            with session_scope(session=session_maker()) as session:
                delete_statistics_duplicates(hass, session)
            _create_index(
                session_maker, "statistics", "ix_statistics_statistic_id_start"
            )
            _create_index(
                session_maker,
                "statistics_short_term",
                "ix_statistics_short_term_statistic_id_start",
            )
    elif new_version == 25:
        _add_columns(session_maker, "states", [f"attributes_id {big_int}"])
        _create_index(session_maker, "states", "ix_states_attributes_id")
    elif new_version == 26:
        _create_index(session_maker, "statistics_runs", "ix_statistics_runs_start")
    elif new_version == 27:
        _add_columns(session_maker, "events", [f"data_id {big_int}"])
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
            with contextlib.suppress(SQLAlchemyError):
                with session_scope(session=session_maker()) as session:
                    connection = session.connection()
                    # This is safe to run multiple times and fast since the table is small
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
                delete_statistics_meta_duplicates(session)
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
    else:
        raise ValueError(f"No schema migration defined for version {new_version}")


def _initialize_database(session: Session) -> bool:
    """Initialize a new database, or a database created before introducing schema changes.

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
        if index["column_names"] == ["time_fired"]:
            # Schema addition from version 1 detected. New DB.
            session.add(StatisticsRuns(start=get_start_time()))
            session.add(SchemaChanges(schema_version=SCHEMA_VERSION))
            return True

    # Version 1 schema changes not found, this db needs to be migrated.
    current_version = SchemaChanges(schema_version=0)
    session.add(current_version)
    return True


def initialize_database(session_maker: Callable[[], Session]) -> bool:
    """Initialize a new database, or a database created before introducing schema changes."""
    try:
        with session_scope(session=session_maker()) as session:
            if _get_schema_version(session) is not None:
                return True
            return _initialize_database(session)

    except Exception as err:  # pylint: disable=broad-except
        _LOGGER.exception("Error when initialise database: %s", err)
        return False
