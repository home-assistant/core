"""The issue117263 integration."""

from __future__ import annotations

from collections.abc import Callable
import logging
from time import time
from typing import cast

from sqlalchemy import Table, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm.session import Session
from sqlalchemy.schema import CreateTable

from homeassistant.components.recorder import Recorder, SupportedDialect, get_instance
from homeassistant.components.recorder.db_schema import (
    LEGACY_STATES_EVENT_ID_INDEX,
    TABLE_STATES,
    Base,
    States,
)
from homeassistant.components.recorder.migration import _drop_index
from homeassistant.components.recorder.queries import has_used_states_event_ids
from homeassistant.components.recorder.tasks import RecorderTask
from homeassistant.components.recorder.util import get_index_by_name, session_scope
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

DOMAIN = "issue117263"
_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


class RebuildStatesTableTask(RecorderTask):
    """A task to rebuild the states table."""

    def run(self, instance: Recorder) -> None:
        """Clean up the legacy event_id index on states."""
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
            # SQLite does not support dropping foreign key constraints
            # so we have to rebuild the table
            rebuild_sqlite_table(session_maker, instance.engine, States)
            _drop_index(session_maker, "states", LEGACY_STATES_EVENT_ID_INDEX)
            instance.use_legacy_events_index = False


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up up issue117263.

    This integration is only used to do a one time rebuild of the
    states table.
    """
    instance = get_instance(hass)
    if instance.dialect_name != SupportedDialect.SQLITE:
        _LOGGER.error("This integration is only for SQLite databases")
        return False
    await instance.async_add_executor_job(_queue_task_if_needed, instance)
    return True


def _queue_task_if_needed(instance: Recorder) -> None:
    with session_scope(session=instance.get_session()) as session:
        if get_index_by_name(session, TABLE_STATES, LEGACY_STATES_EVENT_ID_INDEX):
            instance.queue_task(RebuildStatesTableTask())


def rebuild_sqlite_table(
    session_maker: Callable[[], Session], engine: Engine, table: type[Base]
) -> None:
    """Rebuild an SQLite table.

    This must only be called after all migrations are complete
    and the database is in a consistent state.

    If the table is not migrated to the current schema this
    will likely fail.
    """
    table_table = cast(Table, table.__table__)
    orig_name = table_table.name
    temp_name = f"{table_table.name}_temp_{int(time())}"

    _LOGGER.warning(
        "Rebuilding SQLite table %s; This will take a while; Please be patient!",
        orig_name,
    )

    try:
        # 12 step SQLite table rebuild
        # https://www.sqlite.org/lang_altertable.html
        with session_scope(session=session_maker()) as session:
            # Step 1 - Disable foreign keys
            session.connection().execute(text("PRAGMA foreign_keys=OFF"))
        # Step 2 - create a transaction
        with session_scope(session=session_maker()) as session:
            # Step 3 - we know all the indexes, triggers, and views associated with table X
            new_sql = str(CreateTable(table_table).compile(engine)).strip("\n") + ";"
            source_sql = f"CREATE TABLE {orig_name}"
            replacement_sql = f"CREATE TABLE {temp_name}"
            assert source_sql in new_sql, f"{source_sql} should be in new_sql"
            new_sql = new_sql.replace(source_sql, replacement_sql)
            # Step 4 - Create temp table
            session.execute(text(new_sql))
            column_names = ",".join([column.name for column in table_table.columns])
            # Step 5 - Transfer content
            sql = f"INSERT INTO {temp_name} SELECT {column_names} FROM {orig_name};"  # noqa: S608
            session.execute(text(sql))
            # Step 6 - Drop the original table
            session.execute(text(f"DROP TABLE {orig_name}"))
            # Step 7 - Rename the temp table
            session.execute(text(f"ALTER TABLE {temp_name} RENAME TO {orig_name}"))
            # Step 8 - Recreate indexes
            for index in table_table.indexes:
                index.create(session.connection())
            # Step 9 - Recreate views (there are none)
            # Step 10 - Check foreign keys
            session.execute(text("PRAGMA foreign_key_check"))
            # Step 11 - Commit transaction
            session.commit()
    except SQLAlchemyError:
        _LOGGER.exception("Error recreating SQLite table %s", table_table.name)
        # Swallow the exception since we do not want to ever raise
        # an integrity error as it would cause the database
        # to be discarded and recreated from scratch
    else:
        _LOGGER.warning("Rebuilding SQLite table %s finished", orig_name)
    finally:
        with session_scope(session=session_maker()) as session:
            # Step 12 - Re-enable foreign keys
            session.connection().execute(text("PRAGMA foreign_keys=ON"))
