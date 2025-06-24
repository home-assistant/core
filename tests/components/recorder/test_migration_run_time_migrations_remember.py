"""Test run time migrations are remembered in the migration_changes table."""

from collections.abc import Callable, Generator
import importlib
import sys
from unittest.mock import Mock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.schema import Index

from homeassistant.components import recorder
from homeassistant.components.recorder import core, migration, statistics
from homeassistant.components.recorder.db_schema import SCHEMA_VERSION
from homeassistant.components.recorder.migration import MigrationTask
from homeassistant.components.recorder.queries import get_migration_changes
from homeassistant.components.recorder.util import (
    execute_stmt_lambda_element,
    session_scope,
)
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant

from .common import async_recorder_block_till_done, async_wait_recording_done

from tests.common import async_test_home_assistant
from tests.typing import RecorderInstanceContextManager

CREATE_ENGINE_TARGET = "homeassistant.components.recorder.core.create_engine"
SCHEMA_MODULE_32 = "tests.components.recorder.db_schema_32"
SCHEMA_MODULE_CURRENT = "homeassistant.components.recorder.db_schema"


@pytest.fixture
async def mock_recorder_before_hass(
    async_test_recorder: RecorderInstanceContextManager,
) -> None:
    """Set up recorder."""


async def _async_wait_migration_done(hass: HomeAssistant) -> None:
    """Wait for the migration to be done."""
    await recorder.get_instance(hass).async_block_till_done()
    await async_recorder_block_till_done(hass)


def _get_migration_id(hass: HomeAssistant) -> dict[str, int]:
    with session_scope(hass=hass, read_only=True) as session:
        return dict(execute_stmt_lambda_element(session, get_migration_changes()))


def _create_engine_test(
    schema_module: str, *, initial_version: int | None = None
) -> Callable:
    """Test version of create_engine that initializes with old schema.

    This simulates an existing db with the old schema.
    """

    def _create_engine_test(*args, **kwargs):
        """Test version of create_engine that initializes with old schema.

        This simulates an existing db with the old schema.
        """
        importlib.import_module(schema_module)
        old_db_schema = sys.modules[schema_module]
        engine = create_engine(*args, **kwargs)
        old_db_schema.Base.metadata.create_all(engine)
        with Session(engine) as session:
            session.add(
                recorder.db_schema.StatisticsRuns(start=statistics.get_start_time())
            )
            if initial_version is not None:
                session.add(
                    recorder.db_schema.SchemaChanges(schema_version=initial_version)
                )
            session.add(
                recorder.db_schema.SchemaChanges(
                    schema_version=old_db_schema.SCHEMA_VERSION
                )
            )
            session.commit()
        return engine

    return _create_engine_test


@pytest.mark.usefixtures("hass_storage")  # Prevent test hass from writing to storage
@pytest.mark.parametrize(
    ("initial_version", "expected_migrator_calls", "expected_created_indices"),
    # expected_migrator_calls is a dict of
    # migrator_id: (needs_migrate_calls, migrate_data_calls)
    [
        (
            27,
            {
                "state_context_id_as_binary": (0, 1),
                "event_context_id_as_binary": (0, 1),
                "event_type_id_migration": (2, 1),
                "entity_id_migration": (2, 1),
                "event_id_post_migration": (1, 1),
                "entity_id_post_migration": (0, 1),
            },
            [
                "ix_states_context_id",
                "ix_events_context_id",
                "ix_states_entity_id_last_updated_ts",
            ],
        ),
        (
            28,
            {
                "state_context_id_as_binary": (0, 1),
                "event_context_id_as_binary": (0, 1),
                "event_type_id_migration": (2, 1),
                "entity_id_migration": (2, 1),
                "event_id_post_migration": (1, 1),
                "entity_id_post_migration": (0, 1),
            },
            [
                "ix_states_context_id",
                "ix_events_context_id",
                "ix_states_entity_id_last_updated_ts",
            ],
        ),
        (
            36,
            {
                "state_context_id_as_binary": (0, 0),
                "event_context_id_as_binary": (0, 0),
                "event_type_id_migration": (2, 1),
                "entity_id_migration": (2, 1),
                "event_id_post_migration": (1, 1),
                "entity_id_post_migration": (0, 1),
            },
            ["ix_states_entity_id_last_updated_ts"],
        ),
        (
            37,
            {
                "state_context_id_as_binary": (0, 0),
                "event_context_id_as_binary": (0, 0),
                "event_type_id_migration": (0, 0),
                "entity_id_migration": (2, 1),
                "event_id_post_migration": (1, 1),
                "entity_id_post_migration": (0, 1),
            },
            ["ix_states_entity_id_last_updated_ts"],
        ),
        (
            38,
            {
                "state_context_id_as_binary": (0, 0),
                "event_context_id_as_binary": (0, 0),
                "event_type_id_migration": (0, 0),
                "entity_id_migration": (0, 0),
                "event_id_post_migration": (1, 1),
                "entity_id_post_migration": (0, 0),
            },
            [],
        ),
        (
            43,
            {
                "state_context_id_as_binary": (0, 0),
                "event_context_id_as_binary": (0, 0),
                "event_type_id_migration": (0, 0),
                "entity_id_migration": (0, 0),
                # Schema was not bumped when the SQLite
                # table rebuild was implemented so we need
                # run event_id_post_migration up until
                # schema 44 since its the first one we can
                # be sure has the foreign key constraint was removed
                # via https://github.com/home-assistant/core/pull/120779
                "event_id_post_migration": (1, 1),
                "entity_id_post_migration": (0, 0),
            },
            [],
        ),
        (
            44,
            {
                "state_context_id_as_binary": (0, 0),
                "event_context_id_as_binary": (0, 0),
                "event_type_id_migration": (0, 0),
                "entity_id_migration": (0, 0),
                "event_id_post_migration": (0, 0),
                "entity_id_post_migration": (0, 0),
            },
            [],
        ),
        (
            SCHEMA_VERSION,
            {
                "state_context_id_as_binary": (0, 0),
                "event_context_id_as_binary": (0, 0),
                "event_type_id_migration": (0, 0),
                "entity_id_migration": (0, 0),
                "event_id_post_migration": (0, 0),
                "entity_id_post_migration": (0, 0),
            },
            [],
        ),
    ],
)
async def test_data_migrator_logic(
    async_test_recorder: RecorderInstanceContextManager,
    initial_version: int,
    expected_migrator_calls: dict[str, tuple[int, int]],
    expected_created_indices: list[str],
) -> None:
    """Test the data migrator logic.

    - The data migrators should not be executed on a new database.
    - Indices needed by the migrators should be created if missing.
    """
    config = {recorder.CONF_COMMIT_INTERVAL: 1}

    def migrator_mock() -> dict[str, Mock]:
        return {
            "needs_migrate": Mock(
                spec_set=[],
                return_value=migration.DataMigrationStatus(
                    needs_migrate=True, migration_done=False
                ),
            ),
            "migrate_data": Mock(spec_set=[], return_value=True),
        }

    migrator_mocks = {
        "state_context_id_as_binary": migrator_mock(),
        "event_context_id_as_binary": migrator_mock(),
        "event_type_id_migration": migrator_mock(),
        "entity_id_migration": migrator_mock(),
        "event_id_post_migration": migrator_mock(),
        "entity_id_post_migration": migrator_mock(),
    }

    def patch_check(
        migrator_id: str, migrator_class: type[migration.BaseMigration]
    ) -> Generator[None]:
        return patch.object(
            migrator_class,
            "needs_migrate_impl",
            side_effect=migrator_mocks[migrator_id]["needs_migrate"],
        )

    def patch_migrate(
        migrator_id: str, migrator_class: type[migration.BaseMigration]
    ) -> Generator[None]:
        return patch.object(
            migrator_class,
            "migrate_data",
            side_effect=migrator_mocks[migrator_id]["migrate_data"],
        )

    with (
        patch_check("state_context_id_as_binary", migration.StatesContextIDMigration),
        patch_check("event_context_id_as_binary", migration.EventsContextIDMigration),
        patch_check("event_type_id_migration", migration.EventTypeIDMigration),
        patch_check("entity_id_migration", migration.EntityIDMigration),
        patch_check("event_id_post_migration", migration.EventIDPostMigration),
        patch_check("entity_id_post_migration", migration.EntityIDPostMigration),
        patch_migrate("state_context_id_as_binary", migration.StatesContextIDMigration),
        patch_migrate("event_context_id_as_binary", migration.EventsContextIDMigration),
        patch_migrate("event_type_id_migration", migration.EventTypeIDMigration),
        patch_migrate("entity_id_migration", migration.EntityIDMigration),
        patch_migrate("event_id_post_migration", migration.EventIDPostMigration),
        patch_migrate("entity_id_post_migration", migration.EntityIDPostMigration),
        patch(
            CREATE_ENGINE_TARGET,
            new=_create_engine_test(
                SCHEMA_MODULE_CURRENT, initial_version=initial_version
            ),
        ),
        patch(
            "sqlalchemy.schema.Index.create", autospec=True, wraps=Index.create
        ) as wrapped_idx_create,
    ):
        async with (
            async_test_home_assistant() as hass,
            async_test_recorder(hass, config),
        ):
            await hass.async_block_till_done()
            await async_wait_recording_done(hass)
            await _async_wait_migration_done(hass)
            hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
            await hass.async_block_till_done()
            await hass.async_stop()

    index_names = [call[1][0].name for call in wrapped_idx_create.mock_calls]
    assert index_names == expected_created_indices

    # Check each data migrator's needs_migrate_impl and migrate_data methods were called
    # the expected number of times.
    for migrator, mock in migrator_mocks.items():
        needs_migrate_calls, migrate_data_calls = expected_migrator_calls[migrator]
        assert len(mock["needs_migrate"].mock_calls) == needs_migrate_calls, (
            f"Expected {migrator} needs_migrate to be called {needs_migrate_calls} times,"
            f" got {len(mock['needs_migrate'].mock_calls)}"
        )
        assert len(mock["migrate_data"].mock_calls) == migrate_data_calls, (
            f"Expected {migrator} migrate_data to be called {migrate_data_calls} times, "
            f"got {len(mock['migrate_data'].mock_calls)}"
        )


@pytest.mark.parametrize("enable_migrate_state_context_ids", [True])
@pytest.mark.parametrize("persistent_database", [True])
@pytest.mark.usefixtures("hass_storage")  # Prevent test hass from writing to storage
async def test_migration_changes_prevent_trying_to_migrate_again(
    async_test_recorder: RecorderInstanceContextManager,
) -> None:
    """Test that we do not try to migrate when migration_changes indicate its already migrated.

    This test will start Home Assistant 3 times:

    1. With schema 32 to populate the data
    2. With current schema so the migration happens
    3. With current schema to verify we do not have to query to see if the migration is done
    """

    config = {recorder.CONF_COMMIT_INTERVAL: 1}
    importlib.import_module(SCHEMA_MODULE_32)
    old_db_schema = sys.modules[SCHEMA_MODULE_32]

    # Start with db schema that needs migration (version 32)
    with (
        patch.object(recorder, "db_schema", old_db_schema),
        patch.object(migration, "SCHEMA_VERSION", old_db_schema.SCHEMA_VERSION),
        patch.object(migration, "non_live_data_migration_needed", return_value=False),
        patch.object(core, "StatesMeta", old_db_schema.StatesMeta),
        patch.object(core, "EventTypes", old_db_schema.EventTypes),
        patch.object(core, "EventData", old_db_schema.EventData),
        patch.object(core, "States", old_db_schema.States),
        patch.object(core, "Events", old_db_schema.Events),
        patch.object(core, "StateAttributes", old_db_schema.StateAttributes),
        patch(CREATE_ENGINE_TARGET, new=_create_engine_test(SCHEMA_MODULE_32)),
    ):
        async with (
            async_test_home_assistant() as hass,
            async_test_recorder(hass, config),
        ):
            await hass.async_block_till_done()
            await async_wait_recording_done(hass)
            await _async_wait_migration_done(hass)
            hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
            await hass.async_block_till_done()
            await hass.async_stop()

    # Now start again with current db schema
    async with async_test_home_assistant() as hass, async_test_recorder(hass, config):
        await hass.async_block_till_done()
        await async_wait_recording_done(hass)
        await _async_wait_migration_done(hass)
        instance = recorder.get_instance(hass)
        migration_changes = await instance.async_add_executor_job(
            _get_migration_id, hass
        )
        assert (
            migration_changes[migration.StatesContextIDMigration.migration_id]
            == migration.StatesContextIDMigration.migration_version
        )
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()
        await hass.async_stop()

    original_queue_task = core.Recorder.queue_task
    tasks = []

    def _queue_task(self, task):
        tasks.append(task)
        original_queue_task(self, task)

    # Finally verify we did not call needs_migrate_query on StatesContextIDMigration
    with (
        patch(
            "homeassistant.components.recorder.core.Recorder.queue_task",
            _queue_task,
        ),
        patch.object(
            migration.StatesContextIDMigration,
            "needs_migrate_query",
            side_effect=RuntimeError("Should not be called"),
        ),
    ):
        async with (
            async_test_home_assistant() as hass,
            async_test_recorder(hass, config),
        ):
            await hass.async_block_till_done()
            await async_wait_recording_done(hass)
            await _async_wait_migration_done(hass)
            instance = recorder.get_instance(hass)
            migration_changes = await instance.async_add_executor_job(
                _get_migration_id, hass
            )
            assert (
                migration_changes[migration.StatesContextIDMigration.migration_id]
                == migration.StatesContextIDMigration.migration_version
            )
            hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
            await hass.async_block_till_done()
            await hass.async_stop()

    for task in tasks:
        if not isinstance(task, MigrationTask):
            continue
        assert not isinstance(task.migrator, migration.StatesContextIDMigration)
