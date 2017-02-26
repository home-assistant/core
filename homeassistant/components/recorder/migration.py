"""Schema migration helpers."""
import logging

from . import models
from .util import session_scope

_LOGGER = logging.getLogger(__name__)


def migrate_schema(instance):
    """Check if the schema needs to be upgraded."""
    schema_changes = models.SchemaChanges

    with session_scope(session=instance.get_session()) as session:
        res = session.query(schema_changes).order_by(
            schema_changes.change_id.desc()).first()
        current_version = getattr(res, 'schema_version', None)

        if current_version == models.SCHEMA_VERSION:
            return

        _LOGGER.debug("Database requires upgrade. Schema version: %s",
                      current_version)

        if current_version is None:
            current_version = _inspect_schema_version(instance.engine, session)
            _LOGGER.debug("No schema version found. Inspected version: %s",
                          current_version)

        for version in range(current_version, models.SCHEMA_VERSION):
            new_version = version + 1
            _LOGGER.info("Upgrading recorder db schema to version %s",
                         new_version)
            _apply_update(instance.engine, new_version)
            session.add(schema_changes(schema_version=new_version))

            _LOGGER.info("Upgrade to version %s done", new_version)


def _apply_update(engine, new_version):
    """Perform operations to bring schema up to date."""
    from sqlalchemy import Table

    if new_version == 1:
        def create_index(table_name, column_name):
            """Create an index for the specified table and column."""
            table = Table(table_name, models.Base.metadata)
            name = "_".join(("ix", table_name, column_name))
            # Look up the index object that was created from the models
            index = next(idx for idx in table.indexes if idx.name == name)
            _LOGGER.debug("Creating index for table %s column %s",
                          table_name, column_name)
            index.create(engine)
            _LOGGER.debug("Index creation done for table %s column %s",
                          table_name, column_name)

        create_index("events", "time_fired")
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

    inspector = reflection.Inspector.from_engine(engine)
    indexes = inspector.get_indexes("events")

    for index in indexes:
        if index['column_names'] == ["time_fired"]:
            # Schema addition from version 1 detected. New DB.
            session.add(models.SchemaChanges(
                schema_version=models.SCHEMA_VERSION))
            return models.SCHEMA_VERSION

    # Version 1 schema changes not found, this db needs to be migrated.
    current_version = models.SchemaChanges(schema_version=0)
    session.add(current_version)
    return current_version.schema_version
