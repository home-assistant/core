"""Schema migration helpers."""
import logging

from .util import session_scope

_LOGGER = logging.getLogger(__name__)


def migrate_schema(instance):
    """Check if the schema needs to be upgraded."""
    from .models import SchemaChanges, SCHEMA_VERSION

    with session_scope(session=instance.get_session()) as session:
        res = session.query(SchemaChanges).order_by(
            SchemaChanges.change_id.desc()).first()
        current_version = getattr(res, 'schema_version', None)

        if current_version == SCHEMA_VERSION:
            return

        _LOGGER.debug("Database requires upgrade. Schema version: %s",
                      current_version)

        if current_version is None:
            current_version = _inspect_schema_version(instance.engine, session)
            _LOGGER.debug("No schema version found. Inspected version: %s",
                          current_version)

        for version in range(current_version, SCHEMA_VERSION):
            new_version = version + 1
            _LOGGER.info("Upgrading recorder db schema to version %s",
                         new_version)
            _apply_update(instance.engine, new_version, current_version)
            session.add(SchemaChanges(schema_version=new_version))

            _LOGGER.info("Upgrade to version %s done", new_version)


def _create_index(engine, table_name, index_name):
    """Create an index for the specified table.

    The index name should match the name given for the index
    within the table definition described in the models
    """
    from sqlalchemy import Table
    from . import models

    table = Table(table_name, models.Base.metadata)
    _LOGGER.debug("Looking up index for table %s", table_name)
    # Look up the index object by name from the table is the models
    index = next(idx for idx in table.indexes if idx.name == index_name)
    _LOGGER.debug("Creating %s index", index_name)
    _LOGGER.info("Adding index `%s` to database. Note: this can take several "
                 "minutes on large databases and slow computers. Please "
                 "be patient!", index_name)
    index.create(engine)
    _LOGGER.debug("Finished creating %s", index_name)


def _drop_index(engine, table_name, index_name):
    """Drop an index from a specified table.

    There is no universal way to do something like `DROP INDEX IF EXISTS`
    so we will simply execute the DROP command and ignore any exceptions

    WARNING: Due to some engines (MySQL at least) being unable to use bind
    parameters in a DROP INDEX statement (at least via SQLAlchemy), the query
    string here is generated from the method parameters without sanitizing.
    DO NOT USE THIS FUNCTION IN ANY OPERATION THAT TAKES USER INPUT.
    """
    from sqlalchemy import text
    from sqlalchemy.exc import SQLAlchemyError

    _LOGGER.debug("Dropping index %s from table %s", index_name, table_name)
    success = False

    # Engines like DB2/Oracle
    try:
        engine.execute(text("DROP INDEX {index}".format(
            index=index_name)))
    except SQLAlchemyError:
        pass
    else:
        success = True

    # Engines like SQLite, SQL Server
    if not success:
        try:
            engine.execute(text("DROP INDEX {table}.{index}".format(
                index=index_name,
                table=table_name)))
        except SQLAlchemyError:
            pass
        else:
            success = True

    if not success:
        # Engines like MySQL, MS Access
        try:
            engine.execute(text("DROP INDEX {index} ON {table}".format(
                index=index_name,
                table=table_name)))
        except SQLAlchemyError:
            pass
        else:
            success = True

    if success:
        _LOGGER.debug("Finished dropping index %s from table %s",
                      index_name, table_name)
    else:
        _LOGGER.warning("Failed to drop index %s from table %s. Schema "
                        "Migration will continue; this is not a "
                        "critical operation.", index_name, table_name)


def _apply_update(engine, new_version, old_version):
    """Perform operations to bring schema up to date."""
    if new_version == 1:
        _create_index(engine, "events", "ix_events_time_fired")
    elif new_version == 2:
        # Create compound start/end index for recorder_runs
        _create_index(engine, "recorder_runs", "ix_recorder_runs_start_end")
        # Create indexes for states
        _create_index(engine, "states", "ix_states_last_updated")
    elif new_version == 3:
        # There used to be a new index here, but it was removed in version 4.
        pass
    elif new_version == 4:
        # Queries were rewritten in this schema release. Most indexes from
        # earlier versions of the schema are no longer needed.

        if old_version == 3:
            # Remove index that was added in version 3
            _drop_index(engine, "states", "ix_states_created_domain")
        if old_version == 2:
            # Remove index that was added in version 2
            _drop_index(engine, "states", "ix_states_entity_id_created")

        # Remove indexes that were added in version 0
        _drop_index(engine, "states", "states__state_changes")
        _drop_index(engine, "states", "states__significant_changes")
        _drop_index(engine, "states", "ix_states_entity_id_created")

        _create_index(engine, "states", "ix_states_entity_id_last_updated")
    else:
        raise ValueError("No schema migration defined for version {}"
                         .format(new_version))


def _inspect_schema_version(engine, session):
    """Determine the schema version by inspecting the db structure.

    When the schema version is not present in the db, either db was just
    created with the correct schema, or this is a db created before schema
    versions were tracked. For now, we'll test if the changes for schema
    version 1 are present to make the determination. Eventually this logic
    can be removed and we can assume a new db is being created.
    """
    from sqlalchemy.engine import reflection
    from .models import SchemaChanges, SCHEMA_VERSION

    inspector = reflection.Inspector.from_engine(engine)
    indexes = inspector.get_indexes("events")

    for index in indexes:
        if index['column_names'] == ["time_fired"]:
            # Schema addition from version 1 detected. New DB.
            session.add(SchemaChanges(
                schema_version=SCHEMA_VERSION))
            return SCHEMA_VERSION

    # Version 1 schema changes not found, this db needs to be migrated.
    current_version = SchemaChanges(schema_version=0)
    session.add(current_version)
    return current_version.schema_version
