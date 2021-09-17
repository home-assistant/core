"""Schema migration helpers."""
import contextlib
import logging

import sqlalchemy
from sqlalchemy import ForeignKeyConstraint, MetaData, Table, text
from sqlalchemy.exc import (
    InternalError,
    OperationalError,
    ProgrammingError,
    SQLAlchemyError,
)
from sqlalchemy.schema import AddConstraint, DropConstraint

from .models import (
    SCHEMA_VERSION,
    TABLE_STATES,
    Base,
    SchemaChanges,
    Statistics,
    StatisticsMeta,
    StatisticsRuns,
)
from .statistics import get_start_time
from .util import session_scope

_LOGGER = logging.getLogger(__name__)


def raise_if_exception_missing_str(ex, match_substrs):
    """Raise an exception if the exception and cause do not contain the match substrs."""
    lower_ex_strs = [str(ex).lower(), str(ex.__cause__).lower()]
    for str_sub in match_substrs:
        for exc_str in lower_ex_strs:
            if exc_str and str_sub in exc_str:
                return

    raise ex


def get_schema_version(instance):
    """Get the schema version."""
    with session_scope(session=instance.get_session()) as session:
        res = (
            session.query(SchemaChanges)
            .order_by(SchemaChanges.change_id.desc())
            .first()
        )
        current_version = getattr(res, "schema_version", None)

        if current_version is None:
            current_version = _inspect_schema_version(instance.engine, session)
            _LOGGER.debug(
                "No schema version found. Inspected version: %s", current_version
            )

        return current_version


def schema_is_current(current_version):
    """Check if the schema is current."""
    return current_version == SCHEMA_VERSION


def migrate_schema(instance, current_version):
    """Check if the schema needs to be upgraded."""
    with session_scope(session=instance.get_session()) as session:
        _LOGGER.warning(
            "Database is about to upgrade. Schema version: %s", current_version
        )
        for version in range(current_version, SCHEMA_VERSION):
            new_version = version + 1
            _LOGGER.info("Upgrading recorder db schema to version %s", new_version)
            _apply_update(instance.engine, session, new_version, current_version)
            session.add(SchemaChanges(schema_version=new_version))

            _LOGGER.info("Upgrade to version %s done", new_version)


def _create_index(connection, table_name, index_name):
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
    try:
        index.create(connection)
    except (InternalError, ProgrammingError, OperationalError) as err:
        raise_if_exception_missing_str(err, ["already exists", "duplicate"])
        _LOGGER.warning(
            "Index %s already exists on %s, continuing", index_name, table_name
        )

    _LOGGER.debug("Finished creating %s", index_name)


def _drop_index(connection, table_name, index_name):
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
    try:
        connection.execute(text(f"DROP INDEX {index_name}"))
    except SQLAlchemyError:
        pass
    else:
        success = True

    # Engines like SQLite, SQL Server
    if not success:
        try:
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
        try:
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


def _add_columns(connection, table_name, columns_def):
    """Add columns to a table."""
    _LOGGER.warning(
        "Adding columns %s to table %s. Note: this can take several "
        "minutes on large databases and slow computers. Please "
        "be patient!",
        ", ".join(column.split(" ")[0] for column in columns_def),
        table_name,
    )

    columns_def = [f"ADD {col_def}" for col_def in columns_def]

    try:
        connection.execute(
            text(
                "ALTER TABLE {table} {columns_def}".format(
                    table=table_name, columns_def=", ".join(columns_def)
                )
            )
        )
        return
    except (InternalError, OperationalError):
        # Some engines support adding all columns at once,
        # this error is when they don't
        _LOGGER.info("Unable to use quick column add. Adding 1 by 1")

    for column_def in columns_def:
        try:
            connection.execute(
                text(
                    "ALTER TABLE {table} {column_def}".format(
                        table=table_name, column_def=column_def
                    )
                )
            )
        except (InternalError, OperationalError) as err:
            raise_if_exception_missing_str(err, ["duplicate"])
            _LOGGER.warning(
                "Column %s already exists on %s, continuing",
                column_def.split(" ")[1],
                table_name,
            )


def _modify_columns(connection, engine, table_name, columns_def):
    """Modify columns in a table."""
    if engine.dialect.name == "sqlite":
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

    if engine.dialect.name == "postgresql":
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

    try:
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
        try:
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


def _update_states_table_with_foreign_key_options(connection, engine):
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
        try:
            connection.execute(DropConstraint(alter["old_fk"]))
            for fkc in states_key_constraints:
                if fkc.column_keys == alter["columns"]:
                    connection.execute(AddConstraint(fkc))
        except (InternalError, OperationalError):
            _LOGGER.exception(
                "Could not update foreign options in %s table", TABLE_STATES
            )


def _drop_foreign_key_constraints(connection, engine, table, columns):
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
        try:
            connection.execute(DropConstraint(drop))
        except (InternalError, OperationalError):
            _LOGGER.exception(
                "Could not drop foreign constraints in %s table on %s",
                TABLE_STATES,
                columns,
            )


def _apply_update(engine, session, new_version, old_version):  # noqa: C901
    """Perform operations to bring schema up to date."""
    connection = session.connection()
    if new_version == 1:
        _create_index(connection, "events", "ix_events_time_fired")
    elif new_version == 2:
        # Create compound start/end index for recorder_runs
        _create_index(connection, "recorder_runs", "ix_recorder_runs_start_end")
        # Create indexes for states
        _create_index(connection, "states", "ix_states_last_updated")
    elif new_version == 3:
        # There used to be a new index here, but it was removed in version 4.
        pass
    elif new_version == 4:
        # Queries were rewritten in this schema release. Most indexes from
        # earlier versions of the schema are no longer needed.

        if old_version == 3:
            # Remove index that was added in version 3
            _drop_index(connection, "states", "ix_states_created_domain")
        if old_version == 2:
            # Remove index that was added in version 2
            _drop_index(connection, "states", "ix_states_entity_id_created")

        # Remove indexes that were added in version 0
        _drop_index(connection, "states", "states__state_changes")
        _drop_index(connection, "states", "states__significant_changes")
        _drop_index(connection, "states", "ix_states_entity_id_created")

        _create_index(connection, "states", "ix_states_entity_id_last_updated")
    elif new_version == 5:
        # Create supporting index for States.event_id foreign key
        _create_index(connection, "states", "ix_states_event_id")
    elif new_version == 6:
        _add_columns(
            session,
            "events",
            ["context_id CHARACTER(36)", "context_user_id CHARACTER(36)"],
        )
        _create_index(connection, "events", "ix_events_context_id")
        _create_index(connection, "events", "ix_events_context_user_id")
        _add_columns(
            connection,
            "states",
            ["context_id CHARACTER(36)", "context_user_id CHARACTER(36)"],
        )
        _create_index(connection, "states", "ix_states_context_id")
        _create_index(connection, "states", "ix_states_context_user_id")
    elif new_version == 7:
        _create_index(connection, "states", "ix_states_entity_id")
    elif new_version == 8:
        _add_columns(connection, "events", ["context_parent_id CHARACTER(36)"])
        _add_columns(connection, "states", ["old_state_id INTEGER"])
        _create_index(connection, "events", "ix_events_context_parent_id")
    elif new_version == 9:
        # We now get the context from events with a join
        # since its always there on state_changed events
        #
        # Ideally we would drop the columns from the states
        # table as well but sqlite doesn't support that
        # and we would have to move to something like
        # sqlalchemy alembic to make that work
        #
        _drop_index(connection, "states", "ix_states_context_id")
        _drop_index(connection, "states", "ix_states_context_user_id")
        # This index won't be there if they were not running
        # nightly but we don't treat that as a critical issue
        _drop_index(connection, "states", "ix_states_context_parent_id")
        # Redundant keys on composite index:
        # We already have ix_states_entity_id_last_updated
        _drop_index(connection, "states", "ix_states_entity_id")
        _create_index(connection, "events", "ix_events_event_type_time_fired")
        _drop_index(connection, "events", "ix_events_event_type")
    elif new_version == 10:
        # Now done in step 11
        pass
    elif new_version == 11:
        _create_index(connection, "states", "ix_states_old_state_id")
        _update_states_table_with_foreign_key_options(connection, engine)
    elif new_version == 12:
        if engine.dialect.name == "mysql":
            _modify_columns(connection, engine, "events", ["event_data LONGTEXT"])
            _modify_columns(connection, engine, "states", ["attributes LONGTEXT"])
    elif new_version == 13:
        if engine.dialect.name == "mysql":
            _modify_columns(
                connection,
                engine,
                "events",
                ["time_fired DATETIME(6)", "created DATETIME(6)"],
            )
            _modify_columns(
                connection,
                engine,
                "states",
                [
                    "last_changed DATETIME(6)",
                    "last_updated DATETIME(6)",
                    "created DATETIME(6)",
                ],
            )
    elif new_version == 14:
        _modify_columns(connection, engine, "events", ["event_type VARCHAR(64)"])
    elif new_version == 15:
        # This dropped the statistics table, done again in version 18.
        pass
    elif new_version == 16:
        _drop_foreign_key_constraints(
            connection, engine, TABLE_STATES, ["old_state_id"]
        )
    elif new_version == 17:
        # This dropped the statistics table, done again in version 18.
        pass
    elif new_version == 18:
        # Recreate the statistics and statistics meta tables.
        #
        # Order matters! Statistics has a relation with StatisticsMeta,
        # so statistics need to be deleted before meta (or in pair depending
        # on the SQL backend); and meta needs to be created before statistics.
        if sqlalchemy.inspect(engine).has_table(
            StatisticsMeta.__tablename__
        ) or sqlalchemy.inspect(engine).has_table(Statistics.__tablename__):
            Base.metadata.drop_all(
                bind=engine, tables=[Statistics.__table__, StatisticsMeta.__table__]
            )

        StatisticsMeta.__table__.create(engine)
        Statistics.__table__.create(engine)
    elif new_version == 19:
        # This adds the statistic runs table, insert a fake run to prevent duplicating
        # statistics.
        session.add(StatisticsRuns(start=get_start_time()))
    elif new_version == 20:
        # This changed the precision of statistics from float to double
        if engine.dialect.name in ["mysql", "oracle", "postgresql"]:
            _modify_columns(
                connection,
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
        _add_columns(
            connection,
            "statistics",
            ["sum_increase DOUBLE PRECISION"],
        )
        # Try to change the character set of the statistic_meta table
        if engine.dialect.name == "mysql":
            for table in ("events", "states", "statistics_meta"):
                with contextlib.suppress(SQLAlchemyError):
                    connection.execute(
                        text(
                            f"ALTER TABLE {table} CONVERT TO "
                            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                        )
                    )
    else:
        raise ValueError(f"No schema migration defined for version {new_version}")


def _inspect_schema_version(engine, session):
    """Determine the schema version by inspecting the db structure.

    When the schema version is not present in the db, either db was just
    created with the correct schema, or this is a db created before schema
    versions were tracked. For now, we'll test if the changes for schema
    version 1 are present to make the determination. Eventually this logic
    can be removed and we can assume a new db is being created.
    """
    inspector = sqlalchemy.inspect(engine)
    indexes = inspector.get_indexes("events")

    for index in indexes:
        if index["column_names"] == ["time_fired"]:
            # Schema addition from version 1 detected. New DB.
            session.add(StatisticsRuns(start=get_start_time()))
            session.add(SchemaChanges(schema_version=SCHEMA_VERSION))
            return SCHEMA_VERSION

    # Version 1 schema changes not found, this db needs to be migrated.
    current_version = SchemaChanges(schema_version=0)
    session.add(current_version)
    return current_version.schema_version
