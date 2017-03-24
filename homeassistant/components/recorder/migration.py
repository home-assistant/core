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
            _apply_update(instance.engine, new_version)
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
    # Look up the index object by name from the table is the the models
    index = next(idx for idx in table.indexes if idx.name == index_name)
    _LOGGER.debug("Creating %s index", index_name)
    index.create(engine)
    _LOGGER.debug("Finished creating %s", index_name)


def _apply_update(engine, new_version):
    """Perform operations to bring schema up to date."""
    if new_version == 1:
        _create_index(engine, "events", "ix_events_time_fired")
    elif new_version == 2:
        # Create compound start/end index for recorder_runs
        _create_index(engine, "recorder_runs", "ix_recorder_runs_start_end")
        # Create indexes for states
        _create_index(engine, "states", "ix_states_last_updated")
        _create_index(engine, "states", "ix_states_entity_id_created")
    else:
        raise ValueError("No schema migration defined for version {}"
                         .format(new_version))


def _inspect_schema_version(engine, session):
    """Determine the schema version by inspecting the db structure.

    When the schema verison is not present in the db, either db was just
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
