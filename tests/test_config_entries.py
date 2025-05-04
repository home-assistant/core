"""Test the config manager."""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from contextlib import AbstractContextManager, nullcontext as does_not_raise
from datetime import timedelta
import logging
import re
from typing import Any, Self
from unittest.mock import ANY, AsyncMock, Mock, patch

from freezegun import freeze_time
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant import config_entries, data_entry_flow, loader
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    EVENT_COMPONENT_LOADED,
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import (
    DOMAIN as HOMEASSISTANT_DOMAIN,
    CoreState,
    HomeAssistant,
    callback,
)
from homeassistant.data_entry_flow import BaseServiceInfo, FlowResult, FlowResultType
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers import entity_registry as er, frame, issue_registry as ir
from homeassistant.helpers.discovery_flow import DiscoveryKey
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.json import json_dumps
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.service_info.hassio import HassioServiceInfo
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.setup import async_set_domains_to_be_loaded, async_setup_component
from homeassistant.util import dt as dt_util
from homeassistant.util.async_ import create_eager_task
from homeassistant.util.json import json_loads

from .common import (
    MockConfigEntry,
    MockEntity,
    MockModule,
    MockPlatform,
    async_capture_events,
    async_fire_time_changed,
    flush_store,
    mock_config_flow,
    mock_integration,
    mock_platform,
)


@pytest.fixture(autouse=True)
def mock_handlers() -> Generator[None]:
    """Mock config flows."""

    class MockFlowHandler(config_entries.ConfigFlow):
        """Define a mock flow handler."""

        VERSION = 1

        async def async_step_reauth(self, data):
            """Mock Reauth."""
            return await self.async_step_reauth_confirm()

        async def async_step_reauth_confirm(self, user_input=None):
            """Test reauth confirm step."""
            if user_input is None:
                return self.async_show_form(step_id="reauth_confirm")
            return self.async_abort(reason="test")

        async def async_step_reconfigure(self, data):
            """Mock Reauth."""
            return await self.async_step_reauth_confirm()

    class MockFlowHandler2(config_entries.ConfigFlow):
        """Define a second mock flow handler."""

        VERSION = 1

        async def async_step_reauth(self, data):
            """Mock Reauth."""
            return await self.async_step_reauth_confirm()

        async def async_step_reauth_confirm(self, user_input=None):
            """Test reauth confirm step."""
            if user_input is None:
                return self.async_show_form(
                    step_id="reauth_confirm",
                    description_placeholders={CONF_NAME: "Custom title"},
                )
            return self.async_abort(reason="test")

    with patch.dict(
        config_entries.HANDLERS,
        {"comp": MockFlowHandler, "test": MockFlowHandler, "test2": MockFlowHandler2},
    ):
        yield


@pytest.fixture
async def manager(hass: HomeAssistant) -> config_entries.ConfigEntries:
    """Fixture of a loaded config manager."""
    manager = config_entries.ConfigEntries(hass, {})
    await manager.async_initialize()
    hass.config_entries = manager
    return manager


async def test_setup_race_only_setup_once(hass: HomeAssistant) -> None:
    """Test ensure that config entries are only setup once."""
    attempts = 0
    slow_config_entry_setup_future = hass.loop.create_future()
    fast_config_entry_setup_future = hass.loop.create_future()
    slow_setup_future = hass.loop.create_future()

    async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
        """Mock setup."""
        await slow_setup_future
        return True

    async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
        """Mock setup entry."""
        slow = entry.data["slow"]
        if slow:
            await slow_config_entry_setup_future
            return True
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise ConfigEntryNotReady
        await fast_config_entry_setup_future
        return True

    async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
        """Mock unload entry."""
        return True

    mock_integration(
        hass,
        MockModule(
            "comp",
            async_setup=async_setup,
            async_setup_entry=async_setup_entry,
            async_unload_entry=async_unload_entry,
        ),
    )
    mock_platform(hass, "comp.config_flow", None)

    entry = MockConfigEntry(domain="comp", data={"slow": False})
    entry.add_to_hass(hass)

    entry2 = MockConfigEntry(domain="comp", data={"slow": True})
    entry2.add_to_hass(hass)
    await entry2.setup_lock.acquire()

    async def _async_reload_entry(entry: MockConfigEntry):
        async with entry.setup_lock:
            await entry.async_unload(hass)
            await entry.async_setup(hass)

    hass.async_create_task(_async_reload_entry(entry2))

    setup_task = hass.async_create_task(async_setup_component(hass, "comp", {}))
    entry2.setup_lock.release()

    assert entry.state is config_entries.ConfigEntryState.NOT_LOADED
    assert entry2.state is config_entries.ConfigEntryState.NOT_LOADED

    assert "comp" not in hass.config.components
    slow_setup_future.set_result(None)
    await asyncio.sleep(0)
    assert "comp" in hass.config.components

    assert entry.state is config_entries.ConfigEntryState.SETUP_RETRY
    assert entry2.state is config_entries.ConfigEntryState.SETUP_IN_PROGRESS

    fast_config_entry_setup_future.set_result(None)
    # Make sure setup retry is started
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=5))
    slow_config_entry_setup_future.set_result(None)
    await hass.async_block_till_done()

    assert entry.state is config_entries.ConfigEntryState.LOADED
    await hass.async_block_till_done()

    assert attempts == 2
    await hass.async_block_till_done()
    assert setup_task.done()
    assert entry2.state is config_entries.ConfigEntryState.LOADED


async def test_call_setup_entry(hass: HomeAssistant) -> None:
    """Test we call <component>.setup_entry."""
    entry = MockConfigEntry(domain="comp")
    entry.add_to_hass(hass)
    assert not entry.supports_unload

    mock_setup_entry = AsyncMock(return_value=True)
    mock_migrate_entry = AsyncMock(return_value=True)

    mock_integration(
        hass,
        MockModule(
            "comp",
            async_setup_entry=mock_setup_entry,
            async_migrate_entry=mock_migrate_entry,
        ),
    )
    mock_platform(hass, "comp.config_flow", None)

    with patch("homeassistant.config_entries.support_entry_unload", return_value=True):
        result = await async_setup_component(hass, "comp", {})
        await hass.async_block_till_done()
    assert result
    assert len(mock_migrate_entry.mock_calls) == 0
    assert len(mock_setup_entry.mock_calls) == 1
    assert entry.state is config_entries.ConfigEntryState.LOADED
    assert entry.supports_unload


async def test_call_setup_entry_without_reload_support(hass: HomeAssistant) -> None:
    """Test we call <component>.setup_entry and the <component> does not support unloading."""
    entry = MockConfigEntry(domain="comp")
    entry.add_to_hass(hass)
    assert not entry.supports_unload

    mock_setup_entry = AsyncMock(return_value=True)
    mock_migrate_entry = AsyncMock(return_value=True)

    mock_integration(
        hass,
        MockModule(
            "comp",
            async_setup_entry=mock_setup_entry,
            async_migrate_entry=mock_migrate_entry,
        ),
    )
    mock_platform(hass, "comp.config_flow", None)

    with patch("homeassistant.config_entries.support_entry_unload", return_value=False):
        result = await async_setup_component(hass, "comp", {})
        await hass.async_block_till_done()
    assert result
    assert len(mock_migrate_entry.mock_calls) == 0
    assert len(mock_setup_entry.mock_calls) == 1
    assert entry.state is config_entries.ConfigEntryState.LOADED
    assert not entry.supports_unload


@pytest.mark.parametrize(("major_version", "minor_version"), [(2, 1), (1, 2), (2, 2)])
async def test_call_async_migrate_entry(
    hass: HomeAssistant, major_version: int, minor_version: int
) -> None:
    """Test we call <component>.async_migrate_entry when version mismatch."""
    entry = MockConfigEntry(
        domain="comp", version=major_version, minor_version=minor_version
    )
    assert not entry.supports_unload

    entry.add_to_hass(hass)

    mock_migrate_entry = AsyncMock(return_value=True)
    mock_setup_entry = AsyncMock(return_value=True)

    mock_integration(
        hass,
        MockModule(
            "comp",
            async_setup_entry=mock_setup_entry,
            async_migrate_entry=mock_migrate_entry,
        ),
    )
    mock_platform(hass, "comp.config_flow", None)

    with patch("homeassistant.config_entries.support_entry_unload", return_value=True):
        result = await async_setup_component(hass, "comp", {})
        await hass.async_block_till_done()
    assert result
    assert len(mock_migrate_entry.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
    assert entry.state is config_entries.ConfigEntryState.LOADED
    assert entry.supports_unload


@pytest.mark.parametrize(("major_version", "minor_version"), [(2, 1), (1, 2), (2, 2)])
async def test_call_async_migrate_entry_failure_false(
    hass: HomeAssistant, major_version: int, minor_version: int
) -> None:
    """Test migration fails if returns false."""
    entry = MockConfigEntry(
        domain="comp", version=major_version, minor_version=minor_version
    )
    entry.add_to_hass(hass)
    assert not entry.supports_unload

    mock_migrate_entry = AsyncMock(return_value=False)
    mock_setup_entry = AsyncMock(return_value=True)

    mock_integration(
        hass,
        MockModule(
            "comp",
            async_setup_entry=mock_setup_entry,
            async_migrate_entry=mock_migrate_entry,
        ),
    )
    mock_platform(hass, "comp.config_flow", None)

    result = await async_setup_component(hass, "comp", {})
    assert result
    assert len(mock_migrate_entry.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 0
    assert entry.state is config_entries.ConfigEntryState.MIGRATION_ERROR
    assert not entry.supports_unload


@pytest.mark.parametrize(("major_version", "minor_version"), [(2, 1), (1, 2), (2, 2)])
async def test_call_async_migrate_entry_failure_exception(
    hass: HomeAssistant, major_version: int, minor_version: int
) -> None:
    """Test migration fails if exception raised."""
    entry = MockConfigEntry(
        domain="comp", version=major_version, minor_version=minor_version
    )
    entry.add_to_hass(hass)
    assert not entry.supports_unload

    mock_migrate_entry = AsyncMock(side_effect=Exception)
    mock_setup_entry = AsyncMock(return_value=True)

    mock_integration(
        hass,
        MockModule(
            "comp",
            async_setup_entry=mock_setup_entry,
            async_migrate_entry=mock_migrate_entry,
        ),
    )
    mock_platform(hass, "comp.config_flow", None)

    result = await async_setup_component(hass, "comp", {})
    assert result
    assert len(mock_migrate_entry.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 0
    assert entry.state is config_entries.ConfigEntryState.MIGRATION_ERROR
    assert not entry.supports_unload


@pytest.mark.parametrize(("major_version", "minor_version"), [(2, 1), (1, 2), (2, 2)])
async def test_call_async_migrate_entry_failure_not_bool(
    hass: HomeAssistant, major_version: int, minor_version: int
) -> None:
    """Test migration fails if boolean not returned."""
    entry = MockConfigEntry(
        domain="comp", version=major_version, minor_version=minor_version
    )
    entry.add_to_hass(hass)
    assert not entry.supports_unload

    mock_migrate_entry = AsyncMock(return_value=None)
    mock_setup_entry = AsyncMock(return_value=True)

    mock_integration(
        hass,
        MockModule(
            "comp",
            async_setup_entry=mock_setup_entry,
            async_migrate_entry=mock_migrate_entry,
        ),
    )
    mock_platform(hass, "comp.config_flow", None)

    result = await async_setup_component(hass, "comp", {})
    assert result
    assert len(mock_migrate_entry.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 0
    assert entry.state is config_entries.ConfigEntryState.MIGRATION_ERROR
    assert not entry.supports_unload


@pytest.mark.parametrize(("major_version", "minor_version"), [(2, 1), (2, 2)])
async def test_call_async_migrate_entry_failure_not_supported(
    hass: HomeAssistant, major_version: int, minor_version: int
) -> None:
    """Test migration fails if async_migrate_entry not implemented."""
    entry = MockConfigEntry(
        domain="comp", version=major_version, minor_version=minor_version
    )
    entry.add_to_hass(hass)
    assert not entry.supports_unload

    mock_setup_entry = AsyncMock(return_value=True)

    mock_integration(hass, MockModule("comp", async_setup_entry=mock_setup_entry))
    mock_platform(hass, "comp.config_flow", None)

    result = await async_setup_component(hass, "comp", {})
    assert result
    assert len(mock_setup_entry.mock_calls) == 0
    assert entry.state is config_entries.ConfigEntryState.MIGRATION_ERROR
    assert not entry.supports_unload


@pytest.mark.parametrize(("major_version", "minor_version"), [(1, 2)])
async def test_call_async_migrate_entry_not_supported_minor_version(
    hass: HomeAssistant, major_version: int, minor_version: int
) -> None:
    """Test migration without async_migrate_entry and minor version changed."""
    entry = MockConfigEntry(
        domain="comp", version=major_version, minor_version=minor_version
    )
    entry.add_to_hass(hass)
    assert not entry.supports_unload

    mock_setup_entry = AsyncMock(return_value=True)

    mock_integration(hass, MockModule("comp", async_setup_entry=mock_setup_entry))
    mock_platform(hass, "comp.config_flow", None)

    result = await async_setup_component(hass, "comp", {})
    assert result
    assert len(mock_setup_entry.mock_calls) == 1
    assert entry.state is config_entries.ConfigEntryState.LOADED
    assert not entry.supports_unload


async def test_remove_entry(
    hass: HomeAssistant,
    manager: config_entries.ConfigEntries,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that we can remove an entry."""

    async def mock_setup_entry(
        hass: HomeAssistant, entry: config_entries.ConfigEntry
    ) -> bool:
        """Mock setting up entry."""
        await hass.config_entries.async_forward_entry_setups(entry, ["light"])
        return True

    async def mock_unload_entry(
        hass: HomeAssistant, entry: config_entries.ConfigEntry
    ) -> bool:
        """Mock unloading an entry."""
        result = await hass.config_entries.async_unload_platforms(entry, ["light"])
        assert result
        return result

    remove_entry_calls = []

    async def mock_remove_entry(
        hass: HomeAssistant, entry: config_entries.ConfigEntry
    ) -> None:
        """Mock removing an entry."""
        # Check that the entry is no longer in the config entries
        assert not hass.config_entries.async_get_entry(entry.entry_id)
        remove_entry_calls.append(None)

    entity = MockEntity(unique_id="1234", name="Test Entity")

    async def mock_setup_entry_platform(
        hass: HomeAssistant,
        entry: config_entries.ConfigEntry,
        async_add_entities: AddConfigEntryEntitiesCallback,
    ) -> None:
        """Mock setting up platform."""
        async_add_entities([entity])

    mock_integration(
        hass,
        MockModule(
            "test",
            async_setup_entry=mock_setup_entry,
            async_unload_entry=mock_unload_entry,
            async_remove_entry=mock_remove_entry,
        ),
    )
    mock_platform(
        hass, "test.light", MockPlatform(async_setup_entry=mock_setup_entry_platform)
    )
    mock_platform(hass, "test.config_flow", None)

    MockConfigEntry(domain="test_other", entry_id="test1").add_to_manager(manager)
    entry = MockConfigEntry(domain="test", entry_id="test2")
    entry.add_to_manager(manager)
    MockConfigEntry(domain="test_other", entry_id="test3").add_to_manager(manager)

    # Check all config entries exist
    assert manager.async_entry_ids() == [
        "test1",
        "test2",
        "test3",
    ]

    # Setup entry
    await manager.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Check entity state got added
    assert hass.states.get("light.test_entity") is not None
    assert len(hass.states.async_all()) == 1

    # Check entity got added to entity registry
    assert len(entity_registry.entities) == 1
    entity_entry = list(entity_registry.entities.values())[0]
    assert entity_entry.config_entry_id == entry.entry_id
    assert entity_entry.config_subentry_id is None

    # Remove entry
    result = await manager.async_remove("test2")
    await hass.async_block_till_done()

    # Check that unload went well and so no need to restart
    assert result == {"require_restart": False}

    # Check the remove callback was invoked.
    assert len(remove_entry_calls) == 1

    # Check that config entry was removed.
    assert manager.async_entry_ids() == ["test1", "test3"]

    # Check that entity state has been removed
    assert hass.states.get("light.test_entity") is None
    assert len(hass.states.async_all()) == 0

    # Check that entity registry entry has been removed
    entity_entry_list = list(entity_registry.entities.values())
    assert not entity_entry_list


async def test_remove_subentry(
    hass: HomeAssistant,
    manager: config_entries.ConfigEntries,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that we can remove a subentry."""
    subentry_id = "blabla"
    update_listener_calls = []

    async def mock_setup_entry(
        hass: HomeAssistant, entry: config_entries.ConfigEntry
    ) -> bool:
        """Mock setting up entry."""
        await hass.config_entries.async_forward_entry_setups(entry, ["light"])
        return True

    mock_remove_entry = AsyncMock(return_value=None)

    entry_entity = MockEntity(unique_id="0001", name="Test Entry Entity")
    subentry_entity = MockEntity(unique_id="0002", name="Test Subentry Entity")

    async def mock_setup_entry_platform(
        hass: HomeAssistant,
        entry: config_entries.ConfigEntry,
        async_add_entities: AddConfigEntryEntitiesCallback,
    ) -> None:
        """Mock setting up platform."""
        async_add_entities([entry_entity])
        async_add_entities([subentry_entity], config_subentry_id=subentry_id)

    mock_integration(
        hass,
        MockModule(
            "test",
            async_setup_entry=mock_setup_entry,
            async_remove_entry=mock_remove_entry,
        ),
    )
    mock_platform(
        hass, "test.light", MockPlatform(async_setup_entry=mock_setup_entry_platform)
    )
    mock_platform(hass, "test.config_flow", None)

    entry = MockConfigEntry(
        subentries_data=[
            config_entries.ConfigSubentryData(
                data={"first": True},
                subentry_id=subentry_id,
                subentry_type="test",
                unique_id="unique",
                title="Mock title",
            )
        ]
    )

    async def update_listener(
        hass: HomeAssistant, entry: config_entries.ConfigEntry
    ) -> None:
        """Test function."""
        assert entry.subentries == {}
        update_listener_calls.append(None)

    entry.add_update_listener(update_listener)
    entry.add_to_manager(manager)

    # Setup entry
    await manager.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Check entity states got added
    assert hass.states.get("light.test_entry_entity") is not None
    assert hass.states.get("light.test_subentry_entity") is not None
    assert len(hass.states.async_all()) == 2

    # Check entities got added to entity registry
    assert len(entity_registry.entities) == 2
    entry_entity_entry = entity_registry.entities["light.test_entry_entity"]
    assert entry_entity_entry.config_entry_id == entry.entry_id
    assert entry_entity_entry.config_subentry_id is None
    subentry_entity_entry = entity_registry.entities["light.test_subentry_entity"]
    assert subentry_entity_entry.config_entry_id == entry.entry_id
    assert subentry_entity_entry.config_subentry_id == subentry_id

    # Remove subentry
    result = manager.async_remove_subentry(entry, subentry_id)
    assert len(update_listener_calls) == 1
    await hass.async_block_till_done()

    # Check that remove went well
    assert result is True

    # Check the remove callback was not invoked.
    assert mock_remove_entry.call_count == 0

    # Check that the config subentry was removed.
    assert entry.subentries == {}

    # Check that entity state has been removed
    assert hass.states.get("light.test_entry_entity") is not None
    assert hass.states.get("light.test_subentry_entity") is None
    assert len(hass.states.async_all()) == 1

    # Check that entity registry entry has been removed
    entity_entry_list = list(entity_registry.entities)
    assert entity_entry_list == ["light.test_entry_entity"]

    # Try to remove the subentry again
    with pytest.raises(config_entries.UnknownSubEntry):
        manager.async_remove_subentry(entry, subentry_id)
    assert len(update_listener_calls) == 1


async def test_remove_entry_non_unique_unique_id(
    hass: HomeAssistant,
    manager: config_entries.ConfigEntries,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that we can remove entry with colliding unique_id."""
    entry_1 = MockConfigEntry(
        domain="test_other", entry_id="test1", unique_id="not_unique"
    )
    entry_1.add_to_manager(manager)
    entry_2 = MockConfigEntry(
        domain="test_other", entry_id="test2", unique_id="not_unique"
    )
    entry_2.add_to_manager(manager)
    entry_3 = MockConfigEntry(
        domain="test_other", entry_id="test3", unique_id="not_unique"
    )
    entry_3.add_to_manager(manager)

    # Check all config entries exist
    assert manager.async_entry_ids() == [
        "test1",
        "test2",
        "test3",
    ]

    # Remove entries
    assert await manager.async_remove("test1") == {"require_restart": False}
    await hass.async_block_till_done()
    assert await manager.async_remove("test2") == {"require_restart": False}
    await hass.async_block_till_done()
    assert await manager.async_remove("test3") == {"require_restart": False}
    await hass.async_block_till_done()


async def test_remove_entry_cancels_reauth(
    hass: HomeAssistant,
    manager: config_entries.ConfigEntries,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Tests that removing a config entry also aborts existing reauth flows."""
    entry = MockConfigEntry(title="test_title", domain="test")

    mock_setup_entry = AsyncMock(side_effect=ConfigEntryAuthFailed())
    mock_integration(hass, MockModule("test", async_setup_entry=mock_setup_entry))
    mock_platform(hass, "test.config_flow", None)

    entry.add_to_hass(hass)
    await manager.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress_by_handler("test")
    assert len(flows) == 1
    assert flows[0]["context"]["entry_id"] == entry.entry_id
    assert flows[0]["context"]["source"] == config_entries.SOURCE_REAUTH
    assert entry.state is config_entries.ConfigEntryState.SETUP_ERROR

    issue_id = f"config_entry_reauth_test_{entry.entry_id}"
    assert issue_registry.async_get_issue(HOMEASSISTANT_DOMAIN, issue_id)

    await manager.async_remove(entry.entry_id)

    flows = hass.config_entries.flow.async_progress_by_handler("test")
    assert len(flows) == 0
    assert not issue_registry.async_get_issue(HOMEASSISTANT_DOMAIN, issue_id)


async def test_reload_entry_cancels_reauth(
    hass: HomeAssistant,
    manager: config_entries.ConfigEntries,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Tests that reloading a config entry also aborts existing reauth flows."""
    entry = MockConfigEntry(title="test_title", domain="test")

    mock_setup_entry = AsyncMock(side_effect=ConfigEntryAuthFailed())
    mock_integration(hass, MockModule("test", async_setup_entry=mock_setup_entry))
    mock_platform(hass, "test.config_flow", None)

    entry.add_to_hass(hass)
    await manager.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress_by_handler("test")
    assert len(flows) == 1
    assert flows[0]["context"]["entry_id"] == entry.entry_id
    assert flows[0]["context"]["source"] == config_entries.SOURCE_REAUTH
    assert entry.state is config_entries.ConfigEntryState.SETUP_ERROR

    issue_id = f"config_entry_reauth_test_{entry.entry_id}"
    assert issue_registry.async_get_issue(HOMEASSISTANT_DOMAIN, issue_id)

    mock_setup_entry.return_value = True
    mock_setup_entry.side_effect = None
    await manager.async_reload(entry.entry_id)

    flows = hass.config_entries.flow.async_progress_by_handler("test")
    assert len(flows) == 0
    assert not issue_registry.async_get_issue(HOMEASSISTANT_DOMAIN, issue_id)


async def test_remove_entry_handles_callback_error(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test that exceptions in the remove callback are handled."""
    mock_setup_entry = AsyncMock(return_value=True)
    mock_unload_entry = AsyncMock(return_value=True)
    mock_remove_entry = AsyncMock(return_value=None)
    mock_integration(
        hass,
        MockModule(
            "test",
            async_setup_entry=mock_setup_entry,
            async_unload_entry=mock_unload_entry,
            async_remove_entry=mock_remove_entry,
        ),
    )
    entry = MockConfigEntry(domain="test", entry_id="test1")
    entry.add_to_manager(manager)
    # Check all config entries exist
    assert manager.async_entry_ids() == ["test1"]
    # Setup entry
    await manager.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Remove entry
    result = await manager.async_remove("test1")
    await hass.async_block_till_done()
    # Check that unload went well and so no need to restart
    assert result == {"require_restart": False}
    # Check the remove callback was invoked.
    assert mock_remove_entry.call_count == 1
    # Check that config entry was removed.
    assert manager.async_entry_ids() == []


async def test_remove_entry_raises(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test if a component raises while removing entry."""

    async def mock_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
        """Mock unload entry function."""
        raise Exception("BROKEN")  # noqa: TRY002

    mock_integration(hass, MockModule("comp", async_unload_entry=mock_unload_entry))

    MockConfigEntry(domain="test", entry_id="test1").add_to_manager(manager)
    MockConfigEntry(
        domain="comp", entry_id="test2", state=config_entries.ConfigEntryState.LOADED
    ).add_to_manager(manager)
    MockConfigEntry(domain="test", entry_id="test3").add_to_manager(manager)

    assert manager.async_entry_ids() == [
        "test1",
        "test2",
        "test3",
    ]

    result = await manager.async_remove("test2")

    assert result == {"require_restart": True}
    assert manager.async_entry_ids() == ["test1", "test3"]


async def test_remove_entry_if_not_loaded(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test that we can remove an entry that is not loaded."""
    mock_unload_entry = AsyncMock(return_value=True)

    mock_integration(hass, MockModule("comp", async_unload_entry=mock_unload_entry))

    MockConfigEntry(domain="test", entry_id="test1").add_to_manager(manager)
    MockConfigEntry(domain="comp", entry_id="test2").add_to_manager(manager)
    MockConfigEntry(domain="test", entry_id="test3").add_to_manager(manager)

    assert manager.async_entry_ids() == [
        "test1",
        "test2",
        "test3",
    ]

    result = await manager.async_remove("test2")

    assert result == {"require_restart": False}
    assert manager.async_entry_ids() == ["test1", "test3"]

    assert len(mock_unload_entry.mock_calls) == 0


async def test_remove_entry_if_integration_deleted(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test that we can remove an entry when the integration is deleted."""
    mock_unload_entry = AsyncMock(return_value=True)

    MockConfigEntry(domain="test", entry_id="test1").add_to_manager(manager)
    MockConfigEntry(domain="comp", entry_id="test2").add_to_manager(manager)
    MockConfigEntry(domain="test", entry_id="test3").add_to_manager(manager)

    assert manager.async_entry_ids() == [
        "test1",
        "test2",
        "test3",
    ]

    result = await manager.async_remove("test2")

    assert result == {"require_restart": False}
    assert manager.async_entry_ids() == ["test1", "test3"]

    assert len(mock_unload_entry.mock_calls) == 0


async def test_add_entry_calls_setup_entry(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test we call setup_config_entry."""
    mock_setup_entry = AsyncMock(return_value=True)

    mock_integration(hass, MockModule("comp", async_setup_entry=mock_setup_entry))
    mock_platform(hass, "comp.config_flow", None)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 1

        async def async_step_user(self, user_input=None):
            """Test user step."""
            return self.async_create_entry(title="title", data={"token": "supersecret"})

    with mock_config_flow("comp", TestFlow), mock_config_flow("invalid_flow", 5):
        await manager.flow.async_init(
            "comp", context={"source": config_entries.SOURCE_USER}
        )
        await hass.async_block_till_done()

    assert len(mock_setup_entry.mock_calls) == 1
    p_hass, p_entry = mock_setup_entry.mock_calls[0][1]

    assert p_hass is hass
    assert p_entry.data == {"token": "supersecret"}


async def test_entries_gets_entries(manager: config_entries.ConfigEntries) -> None:
    """Test entries are filtered by domain."""
    MockConfigEntry(domain="test").add_to_manager(manager)
    entry1 = MockConfigEntry(domain="test2")
    entry1.add_to_manager(manager)
    entry2 = MockConfigEntry(domain="test2")
    entry2.add_to_manager(manager)

    assert manager.async_entries("test2") == [entry1, entry2]


async def test_domains_gets_domains_uniques(
    manager: config_entries.ConfigEntries,
) -> None:
    """Test we only return each domain once."""
    MockConfigEntry(domain="test").add_to_manager(manager)
    MockConfigEntry(domain="test2").add_to_manager(manager)
    MockConfigEntry(domain="test2").add_to_manager(manager)
    MockConfigEntry(domain="test").add_to_manager(manager)
    MockConfigEntry(domain="test3").add_to_manager(manager)

    assert manager.async_domains() == ["test", "test2", "test3"]


async def test_domains_gets_domains_excludes_ignore_and_disabled(
    manager: config_entries.ConfigEntries,
) -> None:
    """Test we only return each domain once."""
    MockConfigEntry(domain="test").add_to_manager(manager)
    MockConfigEntry(domain="test2").add_to_manager(manager)
    MockConfigEntry(domain="test2").add_to_manager(manager)
    MockConfigEntry(
        domain="ignored", source=config_entries.SOURCE_IGNORE
    ).add_to_manager(manager)
    MockConfigEntry(domain="test3").add_to_manager(manager)
    MockConfigEntry(
        domain="disabled", disabled_by=config_entries.ConfigEntryDisabler.USER
    ).add_to_manager(manager)
    assert manager.async_domains() == ["test", "test2", "test3"]
    assert manager.async_domains(include_ignore=False) == ["test", "test2", "test3"]
    assert manager.async_domains(include_disabled=False) == ["test", "test2", "test3"]
    assert manager.async_domains(include_ignore=False, include_disabled=False) == [
        "test",
        "test2",
        "test3",
    ]

    assert manager.async_domains(include_ignore=True) == [
        "test",
        "test2",
        "ignored",
        "test3",
    ]
    assert manager.async_domains(include_disabled=True) == [
        "test",
        "test2",
        "test3",
        "disabled",
    ]
    assert manager.async_domains(include_ignore=True, include_disabled=True) == [
        "test",
        "test2",
        "ignored",
        "test3",
        "disabled",
    ]


async def test_entries_excludes_ignore_and_disabled(
    manager: config_entries.ConfigEntries,
) -> None:
    """Test ignored and disabled entries are returned by default."""
    entry = MockConfigEntry(domain="test")
    entry.add_to_manager(manager)
    entry2a = MockConfigEntry(domain="test2")
    entry2a.add_to_manager(manager)
    entry2b = MockConfigEntry(domain="test2")
    entry2b.add_to_manager(manager)
    entry_ignored = MockConfigEntry(
        domain="ignored", source=config_entries.SOURCE_IGNORE
    )
    entry_ignored.add_to_manager(manager)
    entry3 = MockConfigEntry(domain="test3")
    entry3.add_to_manager(manager)
    disabled_entry = MockConfigEntry(
        domain="disabled", disabled_by=config_entries.ConfigEntryDisabler.USER
    )
    disabled_entry.add_to_manager(manager)
    assert manager.async_entries() == [
        entry,
        entry2a,
        entry2b,
        entry_ignored,
        entry3,
        disabled_entry,
    ]
    assert manager.async_has_entries("test") is True
    assert manager.async_has_entries("test2") is True
    assert manager.async_has_entries("test3") is True
    assert manager.async_has_entries("ignored") is True
    assert manager.async_has_entries("disabled") is True

    assert manager.async_has_entries("not") is False
    assert manager.async_entries(include_ignore=False) == [
        entry,
        entry2a,
        entry2b,
        entry3,
        disabled_entry,
    ]
    assert manager.async_entries(include_disabled=False) == [
        entry,
        entry2a,
        entry2b,
        entry_ignored,
        entry3,
    ]
    assert manager.async_entries(include_ignore=False, include_disabled=False) == [
        entry,
        entry2a,
        entry2b,
        entry3,
    ]
    assert manager.async_has_entries("test", include_ignore=False) is True
    assert manager.async_has_entries("test2", include_ignore=False) is True
    assert manager.async_has_entries("test3", include_ignore=False) is True
    assert manager.async_has_entries("ignored", include_ignore=False) is False

    assert manager.async_entries(include_ignore=True) == [
        entry,
        entry2a,
        entry2b,
        entry_ignored,
        entry3,
        disabled_entry,
    ]
    assert manager.async_entries(include_disabled=True) == [
        entry,
        entry2a,
        entry2b,
        entry_ignored,
        entry3,
        disabled_entry,
    ]
    assert manager.async_entries(include_ignore=True, include_disabled=True) == [
        entry,
        entry2a,
        entry2b,
        entry_ignored,
        entry3,
        disabled_entry,
    ]
    assert manager.async_has_entries("test", include_disabled=False) is True
    assert manager.async_has_entries("test2", include_disabled=False) is True
    assert manager.async_has_entries("test3", include_disabled=False) is True
    assert manager.async_has_entries("disabled", include_disabled=False) is False


async def test_saving_and_loading(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, hass_storage: dict[str, Any]
) -> None:
    """Test that we're saving and loading correctly."""
    mock_integration(
        hass,
        MockModule("test", async_setup_entry=AsyncMock(return_value=True)),
    )
    mock_platform(hass, "test.config_flow", None)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 5

        async def async_step_user(self, user_input=None):
            """Test user step."""
            await self.async_set_unique_id("unique")
            subentries = [
                config_entries.ConfigSubentryData(
                    data={"foo": "bar"}, subentry_type="test", title="subentry 1"
                ),
                config_entries.ConfigSubentryData(
                    data={"sun": "moon"},
                    subentry_type="test",
                    title="subentry 2",
                    unique_id="very_unique",
                ),
            ]
            return self.async_create_entry(
                title="Test Title", data={"token": "abcd"}, subentries=subentries
            )

    with mock_config_flow("test", TestFlow):
        await hass.config_entries.flow.async_init(
            "test", context={"source": config_entries.SOURCE_USER}
        )

    class Test2Flow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 3

        async def async_step_user(self, user_input=None):
            """Test user step."""
            return self.async_create_entry(
                title="Test 2 Title", data={"username": "bla"}
            )

    with patch("homeassistant.config_entries.HANDLERS.get", return_value=Test2Flow):
        await hass.config_entries.flow.async_init(
            "test",
            context={
                "source": config_entries.SOURCE_USER,
                "discovery_key": DiscoveryKey(domain="test", key=("blah"), version=1),
            },
        )
        await hass.config_entries.flow.async_init(
            "test",
            context={
                "source": config_entries.SOURCE_USER,
                "discovery_key": DiscoveryKey(domain="test", key=("a", "b"), version=1),
            },
        )

    assert len(hass.config_entries.async_entries()) == 3
    entry_1 = hass.config_entries.async_entries()[0]

    hass.config_entries.async_update_entry(
        entry_1,
        pref_disable_polling=True,
        pref_disable_new_entities=True,
    )

    # To trigger the call_later
    freezer.tick(1.0)
    async_fire_time_changed(hass)
    # To execute the save
    await hass.async_block_till_done()

    stored_data = hass_storage["core.config_entries"]
    assert stored_data == {
        "data": {
            "entries": [
                {
                    "created_at": ANY,
                    "data": {
                        "token": "abcd",
                    },
                    "disabled_by": None,
                    "discovery_keys": {},
                    "domain": "test",
                    "entry_id": ANY,
                    "minor_version": 1,
                    "modified_at": ANY,
                    "options": {},
                    "pref_disable_new_entities": True,
                    "pref_disable_polling": True,
                    "source": "user",
                    "subentries": [
                        {
                            "data": {"foo": "bar"},
                            "subentry_id": ANY,
                            "subentry_type": "test",
                            "title": "subentry 1",
                            "unique_id": None,
                        },
                        {
                            "data": {"sun": "moon"},
                            "subentry_id": ANY,
                            "subentry_type": "test",
                            "title": "subentry 2",
                            "unique_id": "very_unique",
                        },
                    ],
                    "title": "Test Title",
                    "unique_id": "unique",
                    "version": 5,
                },
                {
                    "created_at": ANY,
                    "data": {
                        "username": "bla",
                    },
                    "disabled_by": None,
                    "discovery_keys": {
                        "test": [
                            {"domain": "test", "key": "blah", "version": 1},
                        ],
                    },
                    "domain": "test",
                    "entry_id": ANY,
                    "minor_version": 1,
                    "modified_at": ANY,
                    "options": {},
                    "pref_disable_new_entities": False,
                    "pref_disable_polling": False,
                    "source": "user",
                    "subentries": [],
                    "title": "Test 2 Title",
                    "unique_id": None,
                    "version": 3,
                },
                {
                    "created_at": ANY,
                    "data": {
                        "username": "bla",
                    },
                    "disabled_by": None,
                    "discovery_keys": {
                        "test": [
                            {"domain": "test", "key": ["a", "b"], "version": 1},
                        ],
                    },
                    "domain": "test",
                    "entry_id": ANY,
                    "minor_version": 1,
                    "modified_at": ANY,
                    "options": {},
                    "pref_disable_new_entities": False,
                    "pref_disable_polling": False,
                    "source": "user",
                    "subentries": [],
                    "title": "Test 2 Title",
                    "unique_id": None,
                    "version": 3,
                },
            ],
        },
        "key": "core.config_entries",
        "minor_version": 5,
        "version": 1,
    }

    # Now load written data in new config manager
    manager = config_entries.ConfigEntries(hass, {})
    await manager.async_initialize()

    assert len(manager.async_entries()) == 3

    # Ensure same order
    for orig, loaded in zip(
        hass.config_entries.async_entries(), manager.async_entries(), strict=False
    ):
        assert orig.as_dict() == loaded.as_dict()

    hass.config_entries.async_update_entry(
        entry_1,
        pref_disable_polling=False,
        pref_disable_new_entities=False,
    )

    # To trigger the call_later
    freezer.tick(1.0)
    async_fire_time_changed(hass)
    # To execute the save
    await hass.async_block_till_done()

    # Assert no data is lost when storing again
    expected_stored_data = stored_data
    expected_stored_data["data"]["entries"][0]["modified_at"] = ANY
    expected_stored_data["data"]["entries"][0]["pref_disable_new_entities"] = False
    expected_stored_data["data"]["entries"][0]["pref_disable_polling"] = False
    assert hass_storage["core.config_entries"] == expected_stored_data | {}


@freeze_time("2024-02-14 12:00:00")
async def test_as_dict(snapshot: SnapshotAssertion) -> None:
    """Test ConfigEntry.as_dict."""

    # Ensure as_dict is not overridden
    assert MockConfigEntry.as_dict is config_entries.ConfigEntry.as_dict

    excluded_from_dict = {
        "supports_unload",
        "supports_remove_device",
        "state",
        "_setup_lock",
        "update_listeners",
        "reason",
        "error_reason_translation_key",
        "error_reason_translation_placeholders",
        "_async_cancel_retry_setup",
        "_on_unload",
        "setup_lock",
        "_reauth_lock",
        "_tasks",
        "_background_tasks",
        "_integration_for_domain",
        "_tries",
        "_setup_again_job",
        "_supports_options",
        "supports_reconfigure",
    }

    entry = MockConfigEntry(entry_id="mock-entry")

    # Make sure the expected keys are present
    dict_repr = entry.as_dict()
    for key in config_entries.ConfigEntry.__dict__:
        func = getattr(config_entries.ConfigEntry, key)
        if (
            key.startswith("__")
            or callable(func)
            or type(func).__name__ in ("cached_property", "property")
        ):
            continue
        assert key in dict_repr or key in excluded_from_dict
        assert not (key in dict_repr and key in excluded_from_dict)

    # Make sure the dict representation is as expected
    assert dict_repr == snapshot


async def test_forward_entry_sets_up_component(hass: HomeAssistant) -> None:
    """Test we setup the component entry is forwarded to."""
    entry = MockConfigEntry(
        domain="original", state=config_entries.ConfigEntryState.LOADED
    )

    mock_original_setup_entry = AsyncMock(return_value=True)
    integration = mock_integration(
        hass, MockModule("original", async_setup_entry=mock_original_setup_entry)
    )

    mock_forwarded_setup_entry = AsyncMock(return_value=True)
    mock_integration(
        hass, MockModule("forwarded", async_setup_entry=mock_forwarded_setup_entry)
    )

    with patch.object(integration, "async_get_platforms") as mock_async_get_platforms:
        await hass.config_entries.async_forward_entry_setups(entry, ["forwarded"])

    mock_async_get_platforms.assert_called_once_with(["forwarded"])
    assert len(mock_original_setup_entry.mock_calls) == 0
    assert len(mock_forwarded_setup_entry.mock_calls) == 1


async def test_forward_entry_does_not_setup_entry_if_setup_fails(
    hass: HomeAssistant,
) -> None:
    """Test we do not set up entry if component setup fails."""
    entry = MockConfigEntry(
        domain="original", state=config_entries.ConfigEntryState.LOADED
    )

    mock_original_setup_entry = AsyncMock(return_value=True)
    integration = mock_integration(
        hass, MockModule("original", async_setup_entry=mock_original_setup_entry)
    )

    mock_setup = AsyncMock(return_value=False)
    mock_setup_entry = AsyncMock()
    mock_integration(
        hass,
        MockModule(
            "forwarded", async_setup=mock_setup, async_setup_entry=mock_setup_entry
        ),
    )

    with patch.object(integration, "async_get_platforms"):
        await hass.config_entries.async_forward_entry_setups(entry, ["forwarded"])
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 0


async def test_async_forward_entry_setup_deprecated(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test async_forward_entry_setup is deprecated."""
    entry = MockConfigEntry(
        domain="original", state=config_entries.ConfigEntryState.LOADED
    )

    mock_original_setup_entry = AsyncMock(return_value=True)
    integration = mock_integration(
        hass, MockModule("original", async_setup_entry=mock_original_setup_entry)
    )

    mock_setup = AsyncMock(return_value=False)
    mock_setup_entry = AsyncMock()
    mock_integration(
        hass,
        MockModule(
            "forwarded", async_setup=mock_setup, async_setup_entry=mock_setup_entry
        ),
    )

    entry_id = entry.entry_id
    caplog.clear()
    with patch.object(integration, "async_get_platforms"):
        async with entry.setup_lock:
            await hass.config_entries.async_forward_entry_setup(entry, "forwarded")

    assert (
        "Detected code that calls async_forward_entry_setup for integration, "
        f"original with title: Mock Title and entry_id: {entry_id}, "
        "which is deprecated, await async_forward_entry_setups instead. "
        "This will stop working in Home Assistant 2025.6, please report this issue"
    ) in caplog.text


async def test_reauth_issue_flow_returns_abort(
    hass: HomeAssistant,
    manager: config_entries.ConfigEntries,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test that we create/delete an issue when source is reauth.

    In this test, the reauth flow returns abort.
    """
    issue = await _test_reauth_issue(hass, manager, issue_registry)

    result = await manager.flow.async_configure(issue.data["flow_id"], {})
    assert result["type"] == FlowResultType.ABORT
    assert len(issue_registry.issues) == 0


async def test_reauth_issue_flow_aborted(
    hass: HomeAssistant,
    manager: config_entries.ConfigEntries,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test that we create/delete an issue when source is reauth.

    In this test, the reauth flow is aborted.
    """
    issue = await _test_reauth_issue(hass, manager, issue_registry)

    manager.flow.async_abort(issue.data["flow_id"])
    assert len(issue_registry.issues) == 0


async def _test_reauth_issue(
    hass: HomeAssistant,
    manager: config_entries.ConfigEntries,
    issue_registry: ir.IssueRegistry,
) -> ir.IssueEntry:
    """Test that we create/delete an issue when source is reauth."""
    assert len(issue_registry.issues) == 0

    entry = MockConfigEntry(title="test_title", domain="test")

    mock_setup_entry = AsyncMock(side_effect=ConfigEntryAuthFailed())
    mock_integration(hass, MockModule("test", async_setup_entry=mock_setup_entry))
    mock_platform(hass, "test.config_flow", None)

    entry.add_to_hass(hass)
    await manager.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress_by_handler("test")
    assert len(flows) == 1

    assert len(issue_registry.issues) == 1
    issue_id = f"config_entry_reauth_test_{entry.entry_id}"
    issue = issue_registry.async_get_issue(HOMEASSISTANT_DOMAIN, issue_id)
    assert issue == ir.IssueEntry(
        active=True,
        breaks_in_ha_version=None,
        created=ANY,
        data={"flow_id": flows[0]["flow_id"]},
        dismissed_version=None,
        domain=HOMEASSISTANT_DOMAIN,
        is_fixable=False,
        is_persistent=False,
        issue_domain="test",
        issue_id=issue_id,
        learn_more_url=None,
        severity=ir.IssueSeverity.ERROR,
        translation_key="config_entry_reauth",
        translation_placeholders={"name": "test_title"},
    )
    return issue


async def test_loading_default_config(hass: HomeAssistant) -> None:
    """Test loading the default config."""
    manager = config_entries.ConfigEntries(hass, {})

    with patch("homeassistant.util.json.open", side_effect=FileNotFoundError):
        await manager.async_initialize()

    assert len(manager.async_entries()) == 0


async def test_updating_entry_data(
    manager: config_entries.ConfigEntries, freezer: FrozenDateTimeFactory
) -> None:
    """Test that we can update an entry data."""
    created = dt_util.utcnow()
    entry = MockConfigEntry(
        domain="test",
        data={"first": True},
        state=config_entries.ConfigEntryState.SETUP_ERROR,
    )
    entry.add_to_manager(manager)

    assert len(manager.async_entries()) == 1
    assert manager.async_entries()[0] == entry
    assert entry.created_at == created
    assert entry.modified_at == created

    freezer.tick()

    assert manager.async_update_entry(entry) is False
    assert entry.data == {"first": True}
    assert entry.modified_at == created
    assert manager.async_entries()[0].modified_at == created

    freezer.tick()
    modified = dt_util.utcnow()

    assert manager.async_update_entry(entry, data={"second": True}) is True
    assert entry.data == {"second": True}
    assert entry.modified_at == modified
    assert manager.async_entries()[0].modified_at == modified


async def test_updating_entry_system_options(
    manager: config_entries.ConfigEntries, freezer: FrozenDateTimeFactory
) -> None:
    """Test that we can update an entry data."""
    created = dt_util.utcnow()
    entry = MockConfigEntry(
        domain="test",
        data={"first": True},
        state=config_entries.ConfigEntryState.SETUP_ERROR,
        pref_disable_new_entities=True,
    )
    entry.add_to_manager(manager)

    assert entry.pref_disable_new_entities is True
    assert entry.pref_disable_polling is False
    assert entry.created_at == created
    assert entry.modified_at == created

    freezer.tick()
    modified = dt_util.utcnow()

    manager.async_update_entry(
        entry, pref_disable_new_entities=False, pref_disable_polling=True
    )

    assert entry.pref_disable_new_entities is False
    assert entry.pref_disable_polling is True
    assert entry.created_at == created
    assert entry.modified_at == modified


async def test_update_entry_options_and_trigger_listener(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test that we can update entry options and trigger listener."""
    entry = MockConfigEntry(domain="test", options={"first": True})
    entry.add_to_manager(manager)
    update_listener_calls = []

    async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Test function."""
        assert entry.options == {"second": True}
        update_listener_calls.append(None)

    entry.add_update_listener(update_listener)

    assert manager.async_update_entry(entry, options={"second": True}) is True

    await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.options == {"second": True}
    assert len(update_listener_calls) == 1


async def test_updating_subentry_data(
    manager: config_entries.ConfigEntries, freezer: FrozenDateTimeFactory
) -> None:
    """Test that we can update an entry data."""
    created = dt_util.utcnow()
    subentry_id = "blabla"
    entry = MockConfigEntry(
        subentries_data=[
            config_entries.ConfigSubentryData(
                data={"first": True},
                subentry_id=subentry_id,
                subentry_type="test",
                unique_id="unique",
                title="Mock title",
            )
        ]
    )
    subentry = entry.subentries[subentry_id]
    entry.add_to_manager(manager)

    assert len(manager.async_entries()) == 1
    assert manager.async_entries()[0] == entry
    assert entry.created_at == created
    assert entry.modified_at == created

    freezer.tick()

    assert manager.async_update_subentry(entry, subentry) is False
    assert entry.subentries == {
        subentry_id: config_entries.ConfigSubentry(
            data={"first": True},
            subentry_id=subentry_id,
            subentry_type="test",
            title="Mock title",
            unique_id="unique",
        )
    }
    assert entry.modified_at == created
    assert manager.async_entries()[0].modified_at == created

    freezer.tick()
    modified = dt_util.utcnow()

    assert manager.async_update_subentry(entry, subentry, data={"second": True}) is True
    assert entry.subentries == {
        subentry_id: config_entries.ConfigSubentry(
            data={"second": True},
            subentry_id=subentry_id,
            subentry_type="test",
            title="Mock title",
            unique_id="unique",
        )
    }
    assert entry.modified_at == modified
    assert manager.async_entries()[0].modified_at == modified


async def test_update_subentry_and_trigger_listener(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test that we can update subentry and trigger listener."""
    entry = MockConfigEntry(domain="test", options={"first": True})
    entry.add_to_manager(manager)
    update_listener_calls = []

    subentry = config_entries.ConfigSubentry(
        data={"test": "test"},
        subentry_type="test",
        unique_id="test",
        title="Mock title",
    )

    async def update_listener(
        hass: HomeAssistant, entry: config_entries.ConfigEntry
    ) -> None:
        """Test function."""
        assert entry.subentries == expected_subentries
        update_listener_calls.append(None)

    entry.add_update_listener(update_listener)

    expected_subentries = {subentry.subentry_id: subentry}
    assert manager.async_add_subentry(entry, subentry) is True

    await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.subentries == expected_subentries
    assert len(update_listener_calls) == 1

    assert (
        manager.async_update_subentry(
            entry,
            subentry,
            data={"test": "test2"},
            title="New title",
            unique_id="test2",
        )
        is True
    )

    await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.subentries == expected_subentries
    assert len(update_listener_calls) == 2

    expected_subentries = {}
    assert manager.async_remove_subentry(entry, subentry.subentry_id) is True

    await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.subentries == expected_subentries
    assert len(update_listener_calls) == 3


async def test_setup_raise_not_ready(
    hass: HomeAssistant,
    manager: config_entries.ConfigEntries,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a setup raising not ready."""
    entry = MockConfigEntry(title="test_title", domain="test")
    entry.add_to_hass(hass)

    mock_setup_entry = AsyncMock(
        side_effect=ConfigEntryNotReady("The internet connection is offline")
    )
    mock_integration(hass, MockModule("test", async_setup_entry=mock_setup_entry))
    mock_platform(hass, "test.config_flow", None)

    with patch("homeassistant.config_entries.async_call_later") as mock_call:
        await manager.async_setup(entry.entry_id)

    assert len(mock_call.mock_calls) == 1
    assert (
        "Config entry 'test_title' for test integration not ready yet:"
        " The internet connection is offline"
    ) in caplog.text

    p_hass, p_wait_time, p_setup = mock_call.mock_calls[0][1]

    assert p_hass is hass
    assert 5 <= p_wait_time <= 5.5
    assert entry.state is config_entries.ConfigEntryState.SETUP_RETRY
    assert entry.reason == "The internet connection is offline"

    mock_setup_entry.side_effect = None
    mock_setup_entry.return_value = True

    hass.async_run_hass_job(p_setup, None)
    await hass.async_block_till_done()
    assert entry.state is config_entries.ConfigEntryState.LOADED
    assert entry.reason is None


async def test_setup_raise_not_ready_from_exception(
    hass: HomeAssistant,
    manager: config_entries.ConfigEntries,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a setup raising not ready from another exception."""
    entry = MockConfigEntry(title="test_title", domain="test")
    entry.add_to_hass(hass)

    original_exception = HomeAssistantError("The device dropped the connection")
    config_entry_exception = ConfigEntryNotReady()
    config_entry_exception.__cause__ = original_exception

    mock_setup_entry = AsyncMock(side_effect=config_entry_exception)
    mock_integration(hass, MockModule("test", async_setup_entry=mock_setup_entry))
    mock_platform(hass, "test.config_flow", None)

    with patch("homeassistant.config_entries.async_call_later") as mock_call:
        await manager.async_setup(entry.entry_id)

    assert len(mock_call.mock_calls) == 1
    assert (
        "Config entry 'test_title' for test integration not ready yet: The device"
        " dropped the connection" in caplog.text
    )


async def test_setup_retrying_during_unload(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test if we unload an entry that is in retry mode."""
    entry = MockConfigEntry(domain="test")
    entry.add_to_hass(hass)

    mock_setup_entry = AsyncMock(side_effect=ConfigEntryNotReady)
    mock_integration(hass, MockModule("test", async_setup_entry=mock_setup_entry))
    mock_platform(hass, "test.config_flow", None)

    with patch("homeassistant.config_entries.async_call_later") as mock_call:
        await manager.async_setup(entry.entry_id)

    assert entry.state is config_entries.ConfigEntryState.SETUP_RETRY
    assert len(mock_call.return_value.mock_calls) == 0

    await manager.async_unload(entry.entry_id)

    assert entry.state is config_entries.ConfigEntryState.NOT_LOADED
    assert len(mock_call.return_value.mock_calls) == 1


async def test_setup_retrying_during_unload_before_started(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test if we unload an entry that is in retry mode before started."""
    entry = MockConfigEntry(domain="test")
    entry.add_to_hass(hass)
    hass.set_state(CoreState.starting)
    initial_listeners = hass.bus.async_listeners()[EVENT_HOMEASSISTANT_STARTED]

    mock_setup_entry = AsyncMock(side_effect=ConfigEntryNotReady)
    mock_integration(hass, MockModule("test", async_setup_entry=mock_setup_entry))
    mock_platform(hass, "test.config_flow", None)

    await manager.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is config_entries.ConfigEntryState.SETUP_RETRY
    assert (
        hass.bus.async_listeners()[EVENT_HOMEASSISTANT_STARTED] == initial_listeners + 1
    )

    await manager.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is config_entries.ConfigEntryState.NOT_LOADED
    assert (
        hass.bus.async_listeners()[EVENT_HOMEASSISTANT_STARTED] == initial_listeners + 0
    )


async def test_setup_does_not_retry_during_shutdown(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test we do not retry when HASS is shutting down."""
    entry = MockConfigEntry(domain="test")
    entry.add_to_hass(hass)

    mock_setup_entry = AsyncMock(side_effect=ConfigEntryNotReady)
    mock_integration(hass, MockModule("test", async_setup_entry=mock_setup_entry))
    mock_platform(hass, "test.config_flow", None)

    await manager.async_setup(entry.entry_id)

    assert entry.state is config_entries.ConfigEntryState.SETUP_RETRY
    assert len(mock_setup_entry.mock_calls) == 1

    hass.set_state(CoreState.stopping)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=5))
    await hass.async_block_till_done()

    assert entry.state is config_entries.ConfigEntryState.SETUP_RETRY
    assert len(mock_setup_entry.mock_calls) == 1


async def test_reload_during_setup_retrying_waits(hass: HomeAssistant) -> None:
    """Test reloading during setup retry waits."""
    entry = MockConfigEntry(domain="test")
    entry.add_to_hass(hass)
    load_attempts = []
    sleep_duration = 0

    async def _mock_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
        """Mock setup entry."""
        nonlocal sleep_duration
        await asyncio.sleep(sleep_duration)
        load_attempts.append(entry.entry_id)
        raise ConfigEntryNotReady

    mock_integration(hass, MockModule("test", async_setup_entry=_mock_setup_entry))
    mock_platform(hass, "test.config_flow", None)

    await hass.async_create_task(
        hass.config_entries.async_setup(entry.entry_id), eager_start=True
    )
    assert entry.state is config_entries.ConfigEntryState.SETUP_RETRY

    # Now make the setup take a while so that the setup retry
    # will still be in progress when the reload request comes in
    sleep_duration = 0.1
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=5))
    await asyncio.sleep(0)

    # Should not raise homeassistant.config_entries.OperationNotAllowed
    await hass.config_entries.async_reload(entry.entry_id)

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=10))
    await asyncio.sleep(0)

    # Should not raise homeassistant.config_entries.OperationNotAllowed
    hass.config_entries.async_schedule_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert load_attempts == [
        entry.entry_id,
        entry.entry_id,
        entry.entry_id,
        entry.entry_id,
        entry.entry_id,
    ]


async def test_create_entry_options(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test a config entry being created with options."""

    async def mock_async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
        """Mock setup."""
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                "comp",
                context={"source": config_entries.SOURCE_IMPORT},
                data={"data": "data", "option": "option"},
            )
        )
        return True

    async_setup_entry = AsyncMock(return_value=True)
    mock_integration(
        hass,
        MockModule(
            "comp", async_setup=mock_async_setup, async_setup_entry=async_setup_entry
        ),
    )
    mock_platform(hass, "comp.config_flow", None)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 1

        async def async_step_import(self, user_input):
            """Test import step creating entry, with options."""
            return self.async_create_entry(
                title="title",
                data={"example": user_input["data"]},
                options={"example": user_input["option"]},
            )

    with mock_config_flow("comp", TestFlow):
        assert await async_setup_component(hass, "comp", {})

        await hass.async_block_till_done()

        assert len(async_setup_entry.mock_calls) == 1

        entries = hass.config_entries.async_entries("comp")
        assert len(entries) == 1
        assert entries[0].supports_options is False
        assert entries[0].data == {"example": "data"}
        assert entries[0].options == {"example": "option"}


async def test_entry_options(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test that we can set options on an entry."""
    mock_integration(hass, MockModule("test"))
    mock_platform(hass, "test.config_flow", None)
    entry = MockConfigEntry(domain="test", data={"first": True}, options=None)
    entry.add_to_manager(manager)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        @staticmethod
        @callback
        def async_get_options_flow(config_entry):
            """Test options flow."""

            class OptionsFlowHandler(data_entry_flow.FlowHandler):
                """Test options flow handler."""

            return OptionsFlowHandler()

    with mock_config_flow("test", TestFlow):
        flow = await manager.options.async_create_flow(
            entry.entry_id, context={"source": "test"}, data=None
        )

        flow.handler = entry.entry_id  # Used to keep reference to config entry

        await manager.options.async_finish_flow(
            flow,
            {
                "data": {"second": True},
                "type": data_entry_flow.FlowResultType.CREATE_ENTRY,
            },
        )

        assert entry.data == {"first": True}
        assert entry.options == {"second": True}
        assert entry.supports_options is True


async def test_entry_options_abort(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test that we can abort options flow."""
    mock_integration(hass, MockModule("test"))
    mock_platform(hass, "test.config_flow", None)
    entry = MockConfigEntry(domain="test", data={"first": True}, options=None)
    entry.add_to_manager(manager)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        @staticmethod
        @callback
        def async_get_options_flow(config_entry):
            """Test options flow."""

            class OptionsFlowHandler(data_entry_flow.FlowHandler):
                """Test options flow handler."""

            return OptionsFlowHandler()

    with mock_config_flow("test", TestFlow):
        flow = await manager.options.async_create_flow(
            entry.entry_id, context={"source": "test"}, data=None
        )

        flow.handler = entry.entry_id  # Used to keep reference to config entry

        assert await manager.options.async_finish_flow(
            flow, {"type": data_entry_flow.FlowResultType.ABORT, "reason": "test"}
        )


async def test_entry_options_unknown_config_entry(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test that we can abort options flow."""
    mock_integration(hass, MockModule("test"))
    mock_platform(hass, "test.config_flow", None)

    with pytest.raises(config_entries.UnknownEntry):
        await manager.options.async_create_flow(
            "blah", context={"source": "test"}, data=None
        )


async def test_create_entry_subentries(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test a config entry being created with subentries."""

    subentrydata = config_entries.ConfigSubentryData(
        data={"test": "test"},
        title="Mock title",
        subentry_type="test",
        unique_id="test",
    )

    async def mock_async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
        """Mock setup."""
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                "comp",
                context={"source": config_entries.SOURCE_IMPORT},
                data={"data": "data", "subentry": subentrydata},
            )
        )
        return True

    async_setup_entry = AsyncMock(return_value=True)
    mock_integration(
        hass,
        MockModule(
            "comp", async_setup=mock_async_setup, async_setup_entry=async_setup_entry
        ),
    )
    mock_platform(hass, "comp.config_flow", None)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 1

        async def async_step_import(self, user_input):
            """Test import step creating entry, with subentry."""
            return self.async_create_entry(
                title="title",
                data={"example": user_input["data"]},
                subentries=[user_input["subentry"]],
            )

    with patch.dict(config_entries.HANDLERS, {"comp": TestFlow}):
        assert await async_setup_component(hass, "comp", {})

        await hass.async_block_till_done()

        assert len(async_setup_entry.mock_calls) == 1

        entries = hass.config_entries.async_entries("comp")
        assert len(entries) == 1
        assert entries[0].supported_subentry_types == {}
        assert entries[0].data == {"example": "data"}
        assert len(entries[0].subentries) == 1
        subentry_id = list(entries[0].subentries)[0]
        subentry = config_entries.ConfigSubentry(
            data=subentrydata["data"],
            subentry_id=subentry_id,
            subentry_type="test",
            title=subentrydata["title"],
            unique_id="test",
        )
        assert entries[0].subentries == {subentry_id: subentry}


async def test_entry_subentry(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test that we can add a subentry to an entry."""
    mock_integration(hass, MockModule("test"))
    mock_platform(hass, "test.config_flow", None)
    entry = MockConfigEntry(domain="test", data={"first": True})
    entry.add_to_manager(manager)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        class SubentryFlowHandler(config_entries.ConfigSubentryFlow):
            """Test subentry flow handler."""

        @classmethod
        @callback
        def async_get_supported_subentry_types(
            cls, config_entry: ConfigEntry
        ) -> dict[str, type[config_entries.ConfigSubentryFlow]]:
            return {"test": TestFlow.SubentryFlowHandler}

    with mock_config_flow("test", TestFlow):
        flow = await manager.subentries.async_create_flow(
            (entry.entry_id, "test"), context={"source": "test"}, data=None
        )

        flow.handler = (entry.entry_id, "test")  # Set to keep reference to config entry

        await manager.subentries.async_finish_flow(
            flow,
            {
                "data": {"second": True},
                "title": "Mock title",
                "type": data_entry_flow.FlowResultType.CREATE_ENTRY,
                "unique_id": "test",
            },
        )

        assert entry.data == {"first": True}
        assert entry.options == {}
        subentry_id = list(entry.subentries)[0]
        assert entry.subentries == {
            subentry_id: config_entries.ConfigSubentry(
                data={"second": True},
                subentry_id=subentry_id,
                subentry_type="test",
                title="Mock title",
                unique_id="test",
            )
        }
        assert entry.supported_subentry_types == {
            "test": {"supports_reconfigure": False}
        }


async def test_subentry_flow(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test that we can execute a subentry flow."""
    mock_integration(hass, MockModule("test"))
    mock_platform(hass, "test.config_flow", None)
    entry = MockConfigEntry(domain="test", data={"first": True})
    entry.add_to_manager(manager)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        class SubentryFlowHandler(config_entries.ConfigSubentryFlow):
            """Test subentry flow handler."""

            async def async_step_user(self, user_input=None):
                return self.async_create_entry(
                    title="Mock title",
                    data={"second": True},
                    unique_id="test",
                )

        @classmethod
        @callback
        def async_get_supported_subentry_types(
            cls, config_entry: ConfigEntry
        ) -> dict[str, type[config_entries.ConfigSubentryFlow]]:
            return {"test": TestFlow.SubentryFlowHandler}

    with mock_config_flow("test", TestFlow):
        result = await manager.subentries.async_init(
            (entry.entry_id, "test"), context={"source": "user"}
        )
        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY

        assert entry.data == {"first": True}
        assert entry.options == {}
        subentry_id = list(entry.subentries)[0]
        assert entry.subentries == {
            subentry_id: config_entries.ConfigSubentry(
                data={"second": True},
                subentry_id=subentry_id,
                subentry_type="test",
                title="Mock title",
                unique_id="test",
            )
        }
        assert entry.supported_subentry_types == {
            "test": {"supports_reconfigure": False}
        }


async def test_entry_subentry_non_string(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test adding an invalid subentry to an entry."""
    mock_integration(hass, MockModule("test"))
    mock_platform(hass, "test.config_flow", None)
    entry = MockConfigEntry(domain="test", data={"first": True})
    entry.add_to_manager(manager)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        class SubentryFlowHandler(config_entries.ConfigSubentryFlow):
            """Test subentry flow handler."""

        @classmethod
        @callback
        def async_get_supported_subentry_types(
            cls, config_entry: ConfigEntry
        ) -> dict[str, type[config_entries.ConfigSubentryFlow]]:
            return {"test": TestFlow.SubentryFlowHandler}

    with mock_config_flow("test", TestFlow):
        flow = await manager.subentries.async_create_flow(
            (entry.entry_id, "test"), context={"source": "test"}, data=None
        )

        flow.handler = (entry.entry_id, "test")  # Set to keep reference to config entry

        with pytest.raises(HomeAssistantError):
            await manager.subentries.async_finish_flow(
                flow,
                {
                    "data": {"second": True},
                    "title": "Mock title",
                    "type": data_entry_flow.FlowResultType.CREATE_ENTRY,
                    "unique_id": 123,
                },
            )


@pytest.mark.parametrize("context", [None, {}, {"bla": "bleh"}])
async def test_entry_subentry_no_context(
    hass: HomeAssistant, manager: config_entries.ConfigEntries, context: dict | None
) -> None:
    """Test starting a subentry flow without "source" in context."""
    mock_integration(hass, MockModule("test"))
    mock_platform(hass, "test.config_flow", None)
    entry = MockConfigEntry(domain="test", data={"first": True})
    entry.add_to_manager(manager)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        class SubentryFlowHandler(config_entries.ConfigSubentryFlow):
            """Test subentry flow handler."""

        @classmethod
        @callback
        def async_get_supported_subentry_types(
            cls, config_entry: ConfigEntry
        ) -> dict[str, type[config_entries.ConfigSubentryFlow]]:
            return {"test": TestFlow.SubentryFlowHandler}

    with mock_config_flow("test", TestFlow), pytest.raises(KeyError):
        await manager.subentries.async_create_flow(
            (entry.entry_id, "test"), context=context, data=None
        )


@pytest.mark.parametrize(
    ("unique_id", "expected_result"),
    [(None, does_not_raise()), ("test", pytest.raises(HomeAssistantError))],
)
async def test_entry_subentry_duplicate(
    hass: HomeAssistant,
    manager: config_entries.ConfigEntries,
    unique_id: str | None,
    expected_result: AbstractContextManager,
) -> None:
    """Test adding a duplicated subentry to an entry."""
    mock_integration(hass, MockModule("test"))
    mock_platform(hass, "test.config_flow", None)
    entry = MockConfigEntry(
        domain="test",
        data={"first": True},
        subentries_data=[
            config_entries.ConfigSubentryData(
                data={},
                subentry_id="blabla",
                subentry_type="test",
                title="Mock title",
                unique_id=unique_id,
            )
        ],
    )
    entry.add_to_manager(manager)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        class SubentryFlowHandler(config_entries.ConfigSubentryFlow):
            """Test subentry flow handler."""

        @classmethod
        @callback
        def async_get_supported_subentry_types(
            cls, config_entry: ConfigEntry
        ) -> dict[str, type[config_entries.ConfigSubentryFlow]]:
            return {"test": TestFlow.SubentryFlowHandler}

    with mock_config_flow("test", TestFlow):
        flow = await manager.subentries.async_create_flow(
            (entry.entry_id, "test"), context={"source": "test"}, data=None
        )

        flow.handler = (entry.entry_id, "test")  # Set to keep reference to config entry

        with expected_result:
            await manager.subentries.async_finish_flow(
                flow,
                {
                    "data": {"second": True},
                    "title": "Mock title",
                    "type": data_entry_flow.FlowResultType.CREATE_ENTRY,
                    "unique_id": unique_id,
                },
            )


async def test_entry_subentry_abort(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test that we can abort subentry flow."""
    mock_integration(hass, MockModule("test"))
    mock_platform(hass, "test.config_flow", None)
    entry = MockConfigEntry(domain="test", data={"first": True})
    entry.add_to_manager(manager)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        class SubentryFlowHandler(config_entries.ConfigSubentryFlow):
            """Test subentry flow handler."""

        @classmethod
        @callback
        def async_get_supported_subentry_types(
            cls, config_entry: ConfigEntry
        ) -> dict[str, type[config_entries.ConfigSubentryFlow]]:
            return {"test": TestFlow.SubentryFlowHandler}

    with mock_config_flow("test", TestFlow):
        flow = await manager.subentries.async_create_flow(
            (entry.entry_id, "test"), context={"source": "test"}, data=None
        )

        flow.handler = (entry.entry_id, "test")  # Set to keep reference to config entry

        assert await manager.subentries.async_finish_flow(
            flow, {"type": data_entry_flow.FlowResultType.ABORT, "reason": "test"}
        )


async def test_entry_subentry_unknown_config_entry(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test attempting to start a subentry flow for an unknown config entry."""
    mock_integration(hass, MockModule("test"))
    mock_platform(hass, "test.config_flow", None)

    with pytest.raises(config_entries.UnknownEntry):
        await manager.subentries.async_create_flow(
            ("blah", "blah"), context={"source": "test"}, data=None
        )


async def test_entry_subentry_deleted_config_entry(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test attempting to finish a subentry flow for a deleted config entry."""
    mock_integration(hass, MockModule("test"))
    mock_platform(hass, "test.config_flow", None)
    entry = MockConfigEntry(domain="test", data={"first": True})
    entry.add_to_manager(manager)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        class SubentryFlowHandler(config_entries.ConfigSubentryFlow):
            """Test subentry flow handler."""

        @classmethod
        @callback
        def async_get_supported_subentry_types(
            cls, config_entry: ConfigEntry
        ) -> dict[str, type[config_entries.ConfigSubentryFlow]]:
            return {"test": TestFlow.SubentryFlowHandler}

    with mock_config_flow("test", TestFlow):
        flow = await manager.subentries.async_create_flow(
            (entry.entry_id, "test"), context={"source": "test"}, data=None
        )

        flow.handler = (entry.entry_id, "test")  # Set to keep reference to config entry

        await hass.config_entries.async_remove(entry.entry_id)

        with pytest.raises(config_entries.UnknownEntry):
            await manager.subentries.async_finish_flow(
                flow,
                {
                    "data": {"second": True},
                    "title": "Mock title",
                    "type": data_entry_flow.FlowResultType.CREATE_ENTRY,
                    "unique_id": "test",
                },
            )


async def test_entry_subentry_unsupported_subentry_type(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test attempting to start a subentry flow for a config entry without support."""
    mock_integration(hass, MockModule("test"))
    mock_platform(hass, "test.config_flow", None)
    entry = MockConfigEntry(domain="test", data={"first": True})
    entry.add_to_manager(manager)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        class SubentryFlowHandler(config_entries.ConfigSubentryFlow):
            """Test subentry flow handler."""

        @classmethod
        @callback
        def async_get_supported_subentry_types(
            cls, config_entry: ConfigEntry
        ) -> dict[str, type[config_entries.ConfigSubentryFlow]]:
            return {"test": TestFlow.SubentryFlowHandler}

    with (
        mock_config_flow("test", TestFlow),
        pytest.raises(data_entry_flow.UnknownHandler),
    ):
        await manager.subentries.async_create_flow(
            (
                entry.entry_id,
                "unknown",
            ),
            context={"source": "test"},
            data=None,
        )


async def test_entry_subentry_unsupported(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test attempting to start a subentry flow for a config entry without support."""
    mock_integration(hass, MockModule("test"))
    mock_platform(hass, "test.config_flow", None)
    entry = MockConfigEntry(domain="test", data={"first": True})
    entry.add_to_manager(manager)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

    with (
        mock_config_flow("test", TestFlow),
        pytest.raises(data_entry_flow.UnknownHandler),
    ):
        await manager.subentries.async_create_flow(
            (entry.entry_id, "test"), context={"source": "test"}, data=None
        )


async def test_entry_setup_succeed(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test that we can setup an entry."""
    entry = MockConfigEntry(
        domain="comp", state=config_entries.ConfigEntryState.NOT_LOADED
    )
    entry.add_to_hass(hass)

    mock_setup = AsyncMock(return_value=True)
    mock_setup_entry = AsyncMock(return_value=True)

    mock_integration(
        hass,
        MockModule("comp", async_setup=mock_setup, async_setup_entry=mock_setup_entry),
    )
    mock_platform(hass, "comp.config_flow", None)

    assert await manager.async_setup(entry.entry_id)
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
    assert entry.state is config_entries.ConfigEntryState.LOADED


@pytest.mark.parametrize(
    "state",
    [
        config_entries.ConfigEntryState.LOADED,
        config_entries.ConfigEntryState.SETUP_ERROR,
        config_entries.ConfigEntryState.MIGRATION_ERROR,
        config_entries.ConfigEntryState.SETUP_RETRY,
        config_entries.ConfigEntryState.FAILED_UNLOAD,
    ],
)
async def test_entry_setup_invalid_state(
    hass: HomeAssistant,
    manager: config_entries.ConfigEntries,
    state: config_entries.ConfigEntryState,
) -> None:
    """Test that we cannot setup an entry with invalid state."""
    entry = MockConfigEntry(domain="comp", state=state)
    entry.add_to_hass(hass)

    mock_setup = AsyncMock(return_value=True)
    mock_setup_entry = AsyncMock(return_value=True)

    mock_integration(
        hass,
        MockModule("comp", async_setup=mock_setup, async_setup_entry=mock_setup_entry),
    )

    with pytest.raises(config_entries.OperationNotAllowed, match=str(state)):
        assert await manager.async_setup(entry.entry_id)

    assert len(mock_setup.mock_calls) == 0
    assert len(mock_setup_entry.mock_calls) == 0
    assert entry.state is state


@pytest.mark.parametrize(
    ("unload_result", "expected_result", "expected_state", "has_runtime_data"),
    [
        (True, True, config_entries.ConfigEntryState.NOT_LOADED, False),
        (False, False, config_entries.ConfigEntryState.FAILED_UNLOAD, True),
    ],
)
async def test_entry_unload(
    hass: HomeAssistant,
    manager: config_entries.ConfigEntries,
    unload_result: bool,
    expected_result: bool,
    expected_state: config_entries.ConfigEntryState,
    has_runtime_data: bool,
) -> None:
    """Test that we can unload an entry."""
    unload_entry_calls = []

    @callback
    def verify_runtime_data() -> None:
        """Verify runtime data."""
        assert entry.runtime_data == 2

    async def async_unload_entry(
        hass: HomeAssistant, entry: config_entries.ConfigEntry
    ) -> bool:
        """Mock unload entry."""
        unload_entry_calls.append(None)
        verify_runtime_data()
        assert entry.state is config_entries.ConfigEntryState.UNLOAD_IN_PROGRESS
        return unload_result

    entry = MockConfigEntry(domain="comp", state=config_entries.ConfigEntryState.LOADED)
    entry.add_to_hass(hass)
    entry.async_on_unload(verify_runtime_data)
    entry.runtime_data = 2

    mock_integration(hass, MockModule("comp", async_unload_entry=async_unload_entry))

    assert await manager.async_unload(entry.entry_id) == expected_result
    assert len(unload_entry_calls) == 1
    assert entry.state is expected_state
    assert hasattr(entry, "runtime_data") == has_runtime_data


@pytest.mark.parametrize(
    "state",
    [
        config_entries.ConfigEntryState.NOT_LOADED,
        config_entries.ConfigEntryState.SETUP_ERROR,
        config_entries.ConfigEntryState.SETUP_RETRY,
    ],
)
async def test_entry_unload_failed_to_load(
    hass: HomeAssistant,
    manager: config_entries.ConfigEntries,
    state: config_entries.ConfigEntryState,
) -> None:
    """Test that we can unload an entry."""
    entry = MockConfigEntry(domain="comp", state=state)
    entry.add_to_hass(hass)

    async_unload_entry = AsyncMock(return_value=True)

    mock_integration(hass, MockModule("comp", async_unload_entry=async_unload_entry))

    assert await manager.async_unload(entry.entry_id)
    assert len(async_unload_entry.mock_calls) == 0
    assert entry.state is config_entries.ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    "state",
    [
        config_entries.ConfigEntryState.MIGRATION_ERROR,
        config_entries.ConfigEntryState.FAILED_UNLOAD,
    ],
)
async def test_entry_unload_invalid_state(
    hass: HomeAssistant,
    manager: config_entries.ConfigEntries,
    state: config_entries.ConfigEntryState,
) -> None:
    """Test that we cannot unload an entry with invalid state."""
    entry = MockConfigEntry(domain="comp", state=state)
    entry.add_to_hass(hass)

    async_unload_entry = AsyncMock(return_value=True)

    mock_integration(hass, MockModule("comp", async_unload_entry=async_unload_entry))

    with pytest.raises(config_entries.OperationNotAllowed, match=str(state)):
        assert await manager.async_unload(entry.entry_id)

    assert len(async_unload_entry.mock_calls) == 0
    assert entry.state is state


async def test_entry_reload_succeed(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test that we can reload an entry."""
    entry = MockConfigEntry(
        domain="comp", state=config_entries.ConfigEntryState.NOT_LOADED
    )
    entry.add_to_hass(hass)

    async_setup = AsyncMock(return_value=True)
    async_setup_entry = AsyncMock(return_value=True)
    async_unload_entry = AsyncMock(return_value=True)

    mock_integration(
        hass,
        MockModule(
            "comp",
            async_setup=async_setup,
            async_setup_entry=async_setup_entry,
            async_unload_entry=async_unload_entry,
        ),
    )
    mock_platform(hass, "comp.config_flow", None)

    assert await manager.async_reload(entry.entry_id)
    assert len(async_setup.mock_calls) == 1
    assert len(async_setup_entry.mock_calls) == 1
    assert entry.state is config_entries.ConfigEntryState.LOADED


@pytest.mark.parametrize(
    "state",
    [
        config_entries.ConfigEntryState.LOADED,
        config_entries.ConfigEntryState.SETUP_IN_PROGRESS,
    ],
)
async def test_entry_cannot_be_loaded_twice(
    hass: HomeAssistant, state: config_entries.ConfigEntryState
) -> None:
    """Test that a config entry cannot be loaded twice."""
    entry = MockConfigEntry(domain="comp", state=state)
    entry.add_to_hass(hass)

    async_setup = AsyncMock(return_value=True)
    async_setup_entry = AsyncMock(return_value=True)
    async_unload_entry = AsyncMock(return_value=True)

    mock_integration(
        hass,
        MockModule(
            "comp",
            async_setup=async_setup,
            async_setup_entry=async_setup_entry,
            async_unload_entry=async_unload_entry,
        ),
    )
    mock_platform(hass, "comp.config_flow", None)

    with pytest.raises(config_entries.OperationNotAllowed, match=str(state)):
        await entry.async_setup(hass)
    assert len(async_setup.mock_calls) == 0
    assert len(async_setup_entry.mock_calls) == 0
    assert entry.state is state


async def test_entry_setup_without_lock_raises(hass: HomeAssistant) -> None:
    """Test trying to setup a config entry without the lock."""
    entry = MockConfigEntry(
        domain="comp", state=config_entries.ConfigEntryState.NOT_LOADED
    )
    entry.add_to_hass(hass)

    async_setup = AsyncMock(return_value=True)
    async_setup_entry = AsyncMock(return_value=True)
    async_unload_entry = AsyncMock(return_value=True)

    mock_integration(
        hass,
        MockModule(
            "comp",
            async_setup=async_setup,
            async_setup_entry=async_setup_entry,
            async_unload_entry=async_unload_entry,
        ),
    )
    mock_platform(hass, "comp.config_flow", None)

    with pytest.raises(
        config_entries.OperationNotAllowed,
        match="cannot be set up because it does not hold the setup lock",
    ):
        await entry.async_setup(hass)
    assert len(async_setup.mock_calls) == 0
    assert len(async_setup_entry.mock_calls) == 0
    assert entry.state is config_entries.ConfigEntryState.NOT_LOADED


async def test_entry_unload_without_lock_raises(hass: HomeAssistant) -> None:
    """Test trying to unload a config entry without the lock."""
    entry = MockConfigEntry(domain="comp", state=config_entries.ConfigEntryState.LOADED)
    entry.add_to_hass(hass)

    async_setup = AsyncMock(return_value=True)
    async_setup_entry = AsyncMock(return_value=True)
    async_unload_entry = AsyncMock(return_value=True)

    mock_integration(
        hass,
        MockModule(
            "comp",
            async_setup=async_setup,
            async_setup_entry=async_setup_entry,
            async_unload_entry=async_unload_entry,
        ),
    )
    mock_platform(hass, "comp.config_flow", None)

    with pytest.raises(
        config_entries.OperationNotAllowed,
        match="cannot be unloaded because it does not hold the setup lock",
    ):
        await entry.async_unload(hass)
    assert len(async_setup.mock_calls) == 0
    assert len(async_setup_entry.mock_calls) == 0
    assert entry.state is config_entries.ConfigEntryState.LOADED


async def test_entry_remove_without_lock_raises(hass: HomeAssistant) -> None:
    """Test trying to remove a config entry without the lock."""
    entry = MockConfigEntry(domain="comp", state=config_entries.ConfigEntryState.LOADED)
    entry.add_to_hass(hass)

    async_setup = AsyncMock(return_value=True)
    async_setup_entry = AsyncMock(return_value=True)
    async_unload_entry = AsyncMock(return_value=True)

    mock_integration(
        hass,
        MockModule(
            "comp",
            async_setup=async_setup,
            async_setup_entry=async_setup_entry,
            async_unload_entry=async_unload_entry,
        ),
    )
    mock_platform(hass, "comp.config_flow", None)

    with pytest.raises(
        config_entries.OperationNotAllowed,
        match="cannot be removed because it does not hold the setup lock",
    ):
        await entry.async_remove(hass)
    assert len(async_setup.mock_calls) == 0
    assert len(async_setup_entry.mock_calls) == 0
    assert entry.state is config_entries.ConfigEntryState.LOADED


@pytest.mark.parametrize(
    "state",
    [
        config_entries.ConfigEntryState.NOT_LOADED,
        config_entries.ConfigEntryState.SETUP_ERROR,
        config_entries.ConfigEntryState.SETUP_RETRY,
    ],
)
async def test_entry_reload_not_loaded(
    hass: HomeAssistant,
    manager: config_entries.ConfigEntries,
    state: config_entries.ConfigEntryState,
) -> None:
    """Test that we can reload an entry."""
    entry = MockConfigEntry(domain="comp", state=state)
    entry.add_to_hass(hass)

    async_setup = AsyncMock(return_value=True)
    async_setup_entry = AsyncMock(return_value=True)
    async_unload_entry = AsyncMock(return_value=True)

    mock_integration(
        hass,
        MockModule(
            "comp",
            async_setup=async_setup,
            async_setup_entry=async_setup_entry,
            async_unload_entry=async_unload_entry,
        ),
    )
    mock_platform(hass, "comp.config_flow", None)

    assert await manager.async_reload(entry.entry_id)
    assert len(async_unload_entry.mock_calls) == 0
    assert len(async_setup.mock_calls) == 1
    assert len(async_setup_entry.mock_calls) == 1
    assert entry.state is config_entries.ConfigEntryState.LOADED


@pytest.mark.parametrize(
    "state",
    [
        config_entries.ConfigEntryState.MIGRATION_ERROR,
        config_entries.ConfigEntryState.FAILED_UNLOAD,
    ],
)
async def test_entry_reload_error(
    hass: HomeAssistant,
    manager: config_entries.ConfigEntries,
    state: config_entries.ConfigEntryState,
) -> None:
    """Test that we can reload an entry."""
    entry = MockConfigEntry(domain="comp", state=state)
    entry.add_to_hass(hass)

    async_setup = AsyncMock(return_value=True)
    async_setup_entry = AsyncMock(return_value=True)
    async_unload_entry = AsyncMock(return_value=True)

    mock_integration(
        hass,
        MockModule(
            "comp",
            async_setup=async_setup,
            async_setup_entry=async_setup_entry,
            async_unload_entry=async_unload_entry,
        ),
    )

    hass.config.components.add("comp")

    with pytest.raises(config_entries.OperationNotAllowed, match=str(state)):
        assert await manager.async_reload(entry.entry_id)

    assert len(async_unload_entry.mock_calls) == 0
    assert len(async_setup.mock_calls) == 0
    assert len(async_setup_entry.mock_calls) == 0

    assert entry.state == state


async def test_entry_disable_succeed(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test that we can disable an entry."""
    entry = MockConfigEntry(domain="comp", state=config_entries.ConfigEntryState.LOADED)
    entry.add_to_hass(hass)

    async_setup = AsyncMock(return_value=True)
    async_setup_entry = AsyncMock(return_value=True)
    async_unload_entry = AsyncMock(return_value=True)

    mock_integration(
        hass,
        MockModule(
            "comp",
            async_setup=async_setup,
            async_setup_entry=async_setup_entry,
            async_unload_entry=async_unload_entry,
        ),
    )
    mock_platform(hass, "comp.config_flow", None)
    hass.config.components.add("comp")

    # Disable
    assert len(async_setup.mock_calls) == 0
    assert len(async_setup_entry.mock_calls) == 0
    assert await manager.async_set_disabled_by(
        entry.entry_id, config_entries.ConfigEntryDisabler.USER
    )
    assert len(async_unload_entry.mock_calls) == 1
    assert len(async_setup.mock_calls) == 0
    assert len(async_setup_entry.mock_calls) == 0
    assert entry.state is config_entries.ConfigEntryState.NOT_LOADED

    # Enable
    assert await manager.async_set_disabled_by(entry.entry_id, None)
    assert len(async_unload_entry.mock_calls) == 1
    assert len(async_setup.mock_calls) == 0
    assert len(async_setup_entry.mock_calls) == 1
    assert entry.state is config_entries.ConfigEntryState.LOADED


async def test_entry_disable_without_reload_support(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test that we can disable an entry without reload support."""
    entry = MockConfigEntry(domain="comp", state=config_entries.ConfigEntryState.LOADED)
    entry.add_to_hass(hass)

    async_setup = AsyncMock(return_value=True)
    async_setup_entry = AsyncMock(return_value=True)

    mock_integration(
        hass,
        MockModule(
            "comp",
            async_setup=async_setup,
            async_setup_entry=async_setup_entry,
        ),
    )
    mock_platform(hass, "comp.config_flow", None)
    hass.config.components.add("comp")

    # Disable
    assert not await manager.async_set_disabled_by(
        entry.entry_id, config_entries.ConfigEntryDisabler.USER
    )
    assert len(async_setup.mock_calls) == 0
    assert len(async_setup_entry.mock_calls) == 0
    assert entry.state is config_entries.ConfigEntryState.FAILED_UNLOAD

    # Enable
    with pytest.raises(
        config_entries.OperationNotAllowed,
        match=str(config_entries.ConfigEntryState.FAILED_UNLOAD),
    ):
        await manager.async_set_disabled_by(entry.entry_id, None)
    assert len(async_setup.mock_calls) == 0
    assert len(async_setup_entry.mock_calls) == 0
    assert entry.state is config_entries.ConfigEntryState.FAILED_UNLOAD


async def test_entry_enable_without_reload_support(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test that we can disable an entry without reload support."""
    entry = MockConfigEntry(
        domain="comp", disabled_by=config_entries.ConfigEntryDisabler.USER
    )
    entry.add_to_hass(hass)

    async_setup = AsyncMock(return_value=True)
    async_setup_entry = AsyncMock(return_value=True)

    mock_integration(
        hass,
        MockModule(
            "comp",
            async_setup=async_setup,
            async_setup_entry=async_setup_entry,
        ),
    )
    mock_platform(hass, "comp.config_flow", None)

    # Enable
    assert await manager.async_set_disabled_by(entry.entry_id, None)
    assert len(async_setup.mock_calls) == 1
    assert len(async_setup_entry.mock_calls) == 1
    assert entry.state is config_entries.ConfigEntryState.LOADED

    # Disable
    assert not await manager.async_set_disabled_by(
        entry.entry_id, config_entries.ConfigEntryDisabler.USER
    )
    assert len(async_setup.mock_calls) == 1
    assert len(async_setup_entry.mock_calls) == 1
    assert entry.state is config_entries.ConfigEntryState.FAILED_UNLOAD


async def test_init_custom_integration(hass: HomeAssistant) -> None:
    """Test initializing flow for custom integration."""
    integration = loader.Integration(
        hass,
        "custom_components.hue",
        None,
        {"name": "Hue", "dependencies": [], "requirements": [], "domain": "hue"},
    )
    with (
        pytest.raises(data_entry_flow.UnknownHandler),
        patch(
            "homeassistant.loader.async_get_integration",
            return_value=integration,
        ),
    ):
        await hass.config_entries.flow.async_init("bla", context={"source": "user"})


async def test_init_custom_integration_with_missing_handler(
    hass: HomeAssistant,
) -> None:
    """Test initializing flow for custom integration with a missing handler."""
    integration = loader.Integration(
        hass,
        "custom_components.hue",
        None,
        {"name": "Hue", "dependencies": [], "requirements": [], "domain": "hue"},
    )
    mock_integration(
        hass,
        MockModule("hue"),
    )
    mock_platform(hass, "hue.config_flow", None)
    with (
        pytest.raises(data_entry_flow.UnknownHandler),
        patch(
            "homeassistant.loader.async_get_integration",
            return_value=integration,
        ),
    ):
        await hass.config_entries.flow.async_init("bla", context={"source": "user"})


async def test_support_entry_unload(hass: HomeAssistant) -> None:
    """Test unloading entry."""
    assert await config_entries.support_entry_unload(hass, "light")
    assert not await config_entries.support_entry_unload(hass, "auth")


async def test_reload_entry_entity_registry_ignores_no_entry(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test reloading entry in entity registry skips if no config entry linked."""
    handler = config_entries.EntityRegistryDisabledHandler(hass)

    # Test we ignore entities without config entry
    entry = entity_registry.async_get_or_create("light", "hue", "123")
    entity_registry.async_update_entity(
        entry.entity_id, disabled_by=er.RegistryEntryDisabler.USER
    )
    await hass.async_block_till_done()
    assert not handler.changed
    assert handler._remove_call_later is None


async def test_reload_entry_entity_registry_works(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test we schedule an entry to be reloaded if disabled_by is updated."""
    handler = config_entries.EntityRegistryDisabledHandler(hass)
    handler.async_setup()

    config_entry = MockConfigEntry(
        domain="comp", state=config_entries.ConfigEntryState.LOADED
    )
    config_entry.supports_unload = True
    config_entry.add_to_hass(hass)
    mock_setup_entry = AsyncMock(return_value=True)
    mock_unload_entry = AsyncMock(return_value=True)
    mock_integration(
        hass,
        MockModule(
            "comp",
            async_setup_entry=mock_setup_entry,
            async_unload_entry=mock_unload_entry,
        ),
    )
    mock_platform(hass, "comp.config_flow", None)

    # Only changing disabled_by should update trigger
    entity_entry = entity_registry.async_get_or_create(
        "light", "hue", "123", config_entry=config_entry
    )
    entity_registry.async_update_entity(entity_entry.entity_id, name="yo")
    await hass.async_block_till_done()
    assert not handler.changed
    assert handler._remove_call_later is None

    # Disable entity, we should not do anything, only act when enabled.
    entity_registry.async_update_entity(
        entity_entry.entity_id, disabled_by=er.RegistryEntryDisabler.USER
    )
    await hass.async_block_till_done()
    assert not handler.changed
    assert handler._remove_call_later is None

    # Enable entity, check we are reloading config entry.
    entity_registry.async_update_entity(entity_entry.entity_id, disabled_by=None)
    await hass.async_block_till_done()
    assert handler.changed == {config_entry.entry_id}
    assert handler._remove_call_later is not None

    async_fire_time_changed(
        hass,
        dt_util.utcnow()
        + timedelta(seconds=config_entries.RELOAD_AFTER_UPDATE_DELAY + 1),
    )
    await hass.async_block_till_done()

    assert len(mock_unload_entry.mock_calls) == 1


async def test_unique_id_persisted(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test that a unique ID is stored in the config entry."""
    mock_setup_entry = AsyncMock(return_value=True)

    mock_integration(hass, MockModule("comp", async_setup_entry=mock_setup_entry))
    mock_platform(hass, "comp.config_flow", None)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 1

        async def async_step_user(self, user_input=None):
            """Test user step."""
            await self.async_set_unique_id("mock-unique-id")
            return self.async_create_entry(title="mock-title", data={})

    with mock_config_flow("comp", TestFlow):
        await manager.flow.async_init(
            "comp", context={"source": config_entries.SOURCE_USER}
        )

    assert len(mock_setup_entry.mock_calls) == 1
    p_hass, p_entry = mock_setup_entry.mock_calls[0][1]

    assert p_hass is hass
    assert p_entry.unique_id == "mock-unique-id"


async def test_unique_id_existing_entry(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test that we remove an entry if there already is an entry with unique ID."""
    hass.config.components.add("comp")
    MockConfigEntry(
        domain="comp",
        state=config_entries.ConfigEntryState.LOADED,
        unique_id="mock-unique-id",
    ).add_to_hass(hass)

    async_setup_entry = AsyncMock(return_value=True)
    async_unload_entry = AsyncMock(return_value=True)
    async_remove_entry = AsyncMock(return_value=True)

    mock_integration(
        hass,
        MockModule(
            "comp",
            async_setup_entry=async_setup_entry,
            async_unload_entry=async_unload_entry,
            async_remove_entry=async_remove_entry,
        ),
    )
    mock_platform(hass, "comp.config_flow", None)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 1

        async def async_step_user(self, user_input=None):
            """Test user step."""
            existing_entry = await self.async_set_unique_id("mock-unique-id")

            assert existing_entry is not None

            return self.async_create_entry(title="mock-title", data={"via": "flow"})

    with mock_config_flow("comp", TestFlow):
        result = await manager.flow.async_init(
            "comp", context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY

    entries = hass.config_entries.async_entries("comp")
    assert len(entries) == 1
    assert entries[0].data == {"via": "flow"}

    assert len(async_setup_entry.mock_calls) == 1
    assert len(async_unload_entry.mock_calls) == 1
    assert len(async_remove_entry.mock_calls) == 1


async def test_entry_id_existing_entry(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test that we throw when the entry id collides."""
    collide_entry_id = "collide"
    hass.config.components.add("comp")
    MockConfigEntry(
        entry_id=collide_entry_id,
        domain="comp",
        state=config_entries.ConfigEntryState.LOADED,
        unique_id="mock-unique-id",
    ).add_to_hass(hass)

    mock_integration(
        hass,
        MockModule("comp"),
    )
    mock_platform(hass, "comp.config_flow", None)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 1

        async def async_step_user(self, user_input=None):
            """Test user step."""
            return self.async_create_entry(title="mock-title", data={"via": "flow"})

    with (
        pytest.raises(HomeAssistantError),
        mock_config_flow("comp", TestFlow),
        patch(
            "homeassistant.config_entries.ulid_util.ulid_now",
            return_value=collide_entry_id,
        ),
    ):
        await manager.flow.async_init(
            "comp", context={"source": config_entries.SOURCE_USER}
        )


async def test_unique_id_update_existing_entry_without_reload(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test that we update an entry if there already is an entry with unique ID."""
    hass.config.components.add("comp")
    entry = MockConfigEntry(
        domain="comp",
        data={"additional": "data", "host": "0.0.0.0"},
        unique_id="mock-unique-id",
        state=config_entries.ConfigEntryState.LOADED,
    )
    entry.add_to_hass(hass)

    mock_integration(
        hass,
        MockModule("comp"),
    )
    mock_platform(hass, "comp.config_flow", None)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 1

        async def async_step_user(self, user_input=None):
            """Test user step."""
            await self.async_set_unique_id("mock-unique-id")
            self._abort_if_unique_id_configured(
                updates={"host": "1.1.1.1"},
                reload_on_update=False,
                description_placeholders={"title": "Other device"},
            )

    with (
        mock_config_flow("comp", TestFlow),
        patch(
            "homeassistant.config_entries.ConfigEntries.async_reload"
        ) as async_reload,
    ):
        result = await manager.flow.async_init(
            "comp", context={"source": config_entries.SOURCE_USER}
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert result["description_placeholders"]["title"] == "Other device"
    assert entry.data["host"] == "1.1.1.1"
    assert entry.data["additional"] == "data"
    assert len(async_reload.mock_calls) == 0


async def test_unique_id_update_existing_entry_with_reload(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test that we update an entry if there already is an entry with unique ID and we reload on changes."""
    hass.config.components.add("comp")
    entry = MockConfigEntry(
        domain="comp",
        data={"additional": "data", "host": "0.0.0.0"},
        unique_id="mock-unique-id",
        state=config_entries.ConfigEntryState.LOADED,
    )
    entry.add_to_hass(hass)

    mock_integration(
        hass,
        MockModule("comp"),
    )
    mock_platform(hass, "comp.config_flow", None)
    updates = {"host": "1.1.1.1"}

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 1

        async def async_step_user(self, user_input=None):
            """Test user step."""
            await self.async_set_unique_id("mock-unique-id")
            await self._abort_if_unique_id_configured(
                updates=updates,
                reload_on_update=True,
                description_placeholders={"title": "Other device"},
            )

    with (
        mock_config_flow("comp", TestFlow),
        patch(
            "homeassistant.config_entries.ConfigEntries.async_reload"
        ) as async_reload,
    ):
        result = await manager.flow.async_init(
            "comp", context={"source": config_entries.SOURCE_USER}
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert result["description_placeholders"]["title"] == "Other device"
    assert entry.data["host"] == "1.1.1.1"
    assert entry.data["additional"] == "data"
    assert len(async_reload.mock_calls) == 1

    # Test we don't reload if entry not started
    updates["host"] = "2.2.2.2"
    entry._async_set_state(hass, config_entries.ConfigEntryState.NOT_LOADED, None)
    with (
        mock_config_flow("comp", TestFlow),
        patch(
            "homeassistant.config_entries.ConfigEntries.async_reload"
        ) as async_reload,
    ):
        result = await manager.flow.async_init(
            "comp", context={"source": config_entries.SOURCE_USER}
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert result["description_placeholders"]["title"] == "Other device"
    assert entry.data["host"] == "2.2.2.2"
    assert entry.data["additional"] == "data"
    assert len(async_reload.mock_calls) == 0


async def test_unique_id_from_discovery_in_setup_retry(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test that we reload when in a setup retry state from discovery."""
    hass.config.components.add("comp")
    unique_id = "34ea34b43b5a"
    host = "0.0.0.0"
    entry = MockConfigEntry(
        domain="comp",
        data={"additional": "data", "host": host},
        unique_id=unique_id,
        state=config_entries.ConfigEntryState.SETUP_RETRY,
    )
    entry.add_to_hass(hass)

    mock_integration(
        hass,
        MockModule("comp"),
    )
    mock_platform(hass, "comp.config_flow", None)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 1

        async def async_step_dhcp(self, discovery_info: DhcpServiceInfo) -> FlowResult:
            """Test dhcp step."""
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

        async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
            """Test user step."""
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

    # Verify we do not reload from a user source
    with (
        mock_config_flow("comp", TestFlow),
        patch(
            "homeassistant.config_entries.ConfigEntries.async_reload"
        ) as async_reload,
    ):
        result = await manager.flow.async_init(
            "comp", context={"source": config_entries.SOURCE_USER}
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(async_reload.mock_calls) == 0

    # Verify do reload from a discovery source
    with (
        mock_config_flow("comp", TestFlow),
        patch(
            "homeassistant.config_entries.ConfigEntries.async_reload"
        ) as async_reload,
    ):
        discovery_result = await manager.flow.async_init(
            "comp",
            context={"source": config_entries.SOURCE_DHCP},
            data=DhcpServiceInfo(
                hostname="any",
                ip=host,
                macaddress=unique_id,
            ),
        )
        await hass.async_block_till_done()

    assert discovery_result["type"] == FlowResultType.ABORT
    assert discovery_result["reason"] == "already_configured"
    assert len(async_reload.mock_calls) == 1


async def test_unique_id_not_update_existing_entry(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test that we do not update an entry if existing entry has the data."""
    hass.config.components.add("comp")
    entry = MockConfigEntry(
        domain="comp",
        data={"additional": "data", "host": "0.0.0.0"},
        unique_id="mock-unique-id",
    )
    entry.add_to_hass(hass)

    mock_integration(
        hass,
        MockModule("comp"),
    )
    mock_platform(hass, "comp.config_flow", None)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 1

        async def async_step_user(self, user_input=None):
            """Test user step."""
            await self.async_set_unique_id("mock-unique-id")
            await self._abort_if_unique_id_configured(
                updates={"host": "0.0.0.0"}, reload_on_update=True
            )

    with (
        mock_config_flow("comp", TestFlow),
        patch(
            "homeassistant.config_entries.ConfigEntries.async_reload"
        ) as async_reload,
    ):
        result = await manager.flow.async_init(
            "comp", context={"source": config_entries.SOURCE_USER}
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data["host"] == "0.0.0.0"
    assert entry.data["additional"] == "data"
    assert len(async_reload.mock_calls) == 0


ABORT_IN_PROGRESS = {
    "type": data_entry_flow.FlowResultType.ABORT,
    "reason": "already_in_progress",
}


@pytest.mark.parametrize(
    ("existing_flow_source", "expected_result"),
    # Test all sources except SOURCE_IGNORE
    [
        (config_entries.SOURCE_BLUETOOTH, ABORT_IN_PROGRESS),
        (config_entries.SOURCE_DHCP, ABORT_IN_PROGRESS),
        (config_entries.SOURCE_DISCOVERY, ABORT_IN_PROGRESS),
        (config_entries.SOURCE_HARDWARE, ABORT_IN_PROGRESS),
        (config_entries.SOURCE_HASSIO, ABORT_IN_PROGRESS),
        (config_entries.SOURCE_HOMEKIT, ABORT_IN_PROGRESS),
        (config_entries.SOURCE_IMPORT, ABORT_IN_PROGRESS),
        (config_entries.SOURCE_INTEGRATION_DISCOVERY, ABORT_IN_PROGRESS),
        (config_entries.SOURCE_MQTT, ABORT_IN_PROGRESS),
        (config_entries.SOURCE_REAUTH, {"type": data_entry_flow.FlowResultType.FORM}),
        (config_entries.SOURCE_RECONFIGURE, ABORT_IN_PROGRESS),
        (config_entries.SOURCE_SSDP, ABORT_IN_PROGRESS),
        (config_entries.SOURCE_SYSTEM, ABORT_IN_PROGRESS),
        (config_entries.SOURCE_USB, ABORT_IN_PROGRESS),
        (config_entries.SOURCE_USER, ABORT_IN_PROGRESS),
        (config_entries.SOURCE_ZEROCONF, ABORT_IN_PROGRESS),
    ],
)
async def test_unique_id_in_progress(
    hass: HomeAssistant,
    manager: config_entries.ConfigEntries,
    existing_flow_source: str,
    expected_result: dict,
) -> None:
    """Test that we abort if there is already a flow in progress with same unique id."""
    mock_integration(hass, MockModule("comp"))
    mock_platform(hass, "comp.config_flow", None)
    entry = MockConfigEntry(domain="comp")
    entry.add_to_hass(hass)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 1

        async def _async_step_discovery_without_unique_id(self):
            """Handle a flow initialized by discovery."""
            return await self._async_step()

        async def async_step_hardware(self, user_input=None):
            """Test hardware step."""
            return await self._async_step()

        async def async_step_import(self, user_input=None):
            """Test import step."""
            return await self._async_step()

        async def async_step_reauth(self, user_input=None):
            """Test reauth step."""
            return await self._async_step()

        async def async_step_reconfigure(self, user_input=None):
            """Test reconfigure step."""
            return await self._async_step()

        async def async_step_system(self, user_input=None):
            """Test system step."""
            return await self._async_step()

        async def async_step_user(self, user_input=None):
            """Test user step."""
            return await self._async_step()

        async def _async_step(self, user_input=None):
            """Test step."""
            await self.async_set_unique_id("mock-unique-id")
            return self.async_show_form(step_id="discovery")

    with mock_config_flow("comp", TestFlow):
        # Create one to be in progress
        result = await manager.flow.async_init(
            "comp", context={"source": existing_flow_source, "entry_id": entry.entry_id}
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM

        result2 = await manager.flow.async_init(
            "comp", context={"source": config_entries.SOURCE_USER}
        )

    for k, v in expected_result.items():
        assert result2[k] == v


async def test_finish_flow_aborts_progress(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test that when finishing a flow, we abort other flows in progress with unique ID."""
    mock_integration(
        hass,
        MockModule("comp", async_setup_entry=AsyncMock(return_value=True)),
    )
    mock_platform(hass, "comp.config_flow", None)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 1

        async def async_step_user(self, user_input=None):
            """Test user step."""
            await self.async_set_unique_id("mock-unique-id", raise_on_progress=False)

            if user_input is None:
                return self.async_show_form(step_id="discovery")

            return self.async_create_entry(title="yo", data={})

    with mock_config_flow("comp", TestFlow):
        # Create one to be in progress
        result = await manager.flow.async_init(
            "comp", context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM

        # Will finish and cancel other one.
        result2 = await manager.flow.async_init(
            "comp", context={"source": config_entries.SOURCE_USER}, data={}
        )

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY

    assert len(hass.config_entries.flow.async_progress()) == 0


@pytest.mark.parametrize(
    ("extra_context", "expected_entry_discovery_keys"),
    [
        (
            {},
            {},
        ),
        (
            {"discovery_key": DiscoveryKey(domain="test", key="blah", version=1)},
            {"test": (DiscoveryKey(domain="test", key="blah", version=1),)},
        ),
    ],
)
async def test_unique_id_ignore(
    hass: HomeAssistant,
    manager: config_entries.ConfigEntries,
    extra_context: dict,
    expected_entry_discovery_keys: dict,
) -> None:
    """Test that we can ignore flows that are in progress and have a unique ID."""
    async_setup_entry = AsyncMock(return_value=False)
    mock_integration(hass, MockModule("comp", async_setup_entry=async_setup_entry))
    mock_platform(hass, "comp.config_flow", None)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 1

        async def async_step_user(self, user_input=None):
            """Test user flow."""
            await self.async_set_unique_id("mock-unique-id")
            return self.async_show_form(step_id="discovery")

    with mock_config_flow("comp", TestFlow):
        # Create one to be in progress
        result = await manager.flow.async_init(
            "comp", context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM

        result2 = await manager.flow.async_init(
            "comp",
            context={"source": config_entries.SOURCE_IGNORE} | extra_context,
            data={"unique_id": "mock-unique-id", "title": "Ignored Title"},
        )

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY

    # assert len(hass.config_entries.flow.async_progress()) == 0

    # We should never set up an ignored entry.
    assert len(async_setup_entry.mock_calls) == 0

    entry = hass.config_entries.async_entries("comp")[0]

    assert entry.source == "ignore"
    assert entry.unique_id == "mock-unique-id"
    assert entry.title == "Ignored Title"
    assert entry.data == {}
    assert entry.discovery_keys == expected_entry_discovery_keys


async def test_manual_add_overrides_ignored_entry(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test that we can ignore manually add entry, overriding ignored entry."""
    hass.config.components.add("comp")
    entry = MockConfigEntry(
        domain="comp",
        data={"additional": "data", "host": "0.0.0.0"},
        unique_id="mock-unique-id",
        state=config_entries.ConfigEntryState.LOADED,
        source=config_entries.SOURCE_IGNORE,
    )
    entry.add_to_hass(hass)

    mock_integration(
        hass,
        MockModule("comp"),
    )
    mock_platform(hass, "comp.config_flow", None)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 1

        async def async_step_user(self, user_input=None):
            """Test user step."""
            await self.async_set_unique_id("mock-unique-id")
            self._abort_if_unique_id_configured(
                updates={"host": "1.1.1.1"}, reload_on_update=False
            )
            return self.async_show_form(step_id="step2")

        async def async_step_step2(self, user_input=None):
            raise NotImplementedError

    with (
        mock_config_flow("comp", TestFlow),
        patch(
            "homeassistant.config_entries.ConfigEntries.async_reload"
        ) as async_reload,
    ):
        result = await manager.flow.async_init(
            "comp", context={"source": config_entries.SOURCE_USER}
        )
        await hass.async_block_till_done()

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert entry.data["host"] == "1.1.1.1"
    assert entry.data["additional"] == "data"
    assert len(async_reload.mock_calls) == 0


async def test_manual_add_overrides_ignored_entry_singleton(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test that we can ignore manually add entry, overriding ignored entry."""
    hass.config.components.add("comp")
    entry = MockConfigEntry(
        domain="comp",
        state=config_entries.ConfigEntryState.LOADED,
        source=config_entries.SOURCE_IGNORE,
    )
    entry.add_to_hass(hass)

    mock_setup_entry = AsyncMock(return_value=True)

    mock_integration(hass, MockModule("comp", async_setup_entry=mock_setup_entry))
    mock_platform(hass, "comp.config_flow", None)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 1

        async def async_step_user(self, user_input=None):
            """Test user step."""
            if self._async_current_entries():
                return self.async_abort(reason="single_instance_allowed")
            return self.async_create_entry(title="title", data={"token": "supersecret"})

    with mock_config_flow("comp", TestFlow), mock_config_flow("invalid_flow", 5):
        await manager.flow.async_init(
            "comp", context={"source": config_entries.SOURCE_USER}
        )
        await hass.async_block_till_done()

    assert len(mock_setup_entry.mock_calls) == 1
    p_hass, p_entry = mock_setup_entry.mock_calls[0][1]

    assert p_hass is hass
    assert p_entry.data == {"token": "supersecret"}


@pytest.mark.parametrize(
    (
        "discovery_keys",
        "entry_unique_id",
        "flow_context",
        "flow_source",
        "flow_result",
        "updated_discovery_keys",
    ),
    [
        # No discovery key
        (
            {},
            "mock-unique-id",
            {},
            config_entries.SOURCE_ZEROCONF,
            data_entry_flow.FlowResultType.ABORT,
            {},
        ),
        # Discovery key added to ignored entry data
        (
            {},
            "mock-unique-id",
            {"discovery_key": DiscoveryKey(domain="test", key="blah", version=1)},
            config_entries.SOURCE_ZEROCONF,
            data_entry_flow.FlowResultType.ABORT,
            {"test": (DiscoveryKey(domain="test", key="blah", version=1),)},
        ),
        # Discovery key added to ignored entry data
        (
            {"test": (DiscoveryKey(domain="test", key="bleh", version=1),)},
            "mock-unique-id",
            {"discovery_key": DiscoveryKey(domain="test", key="blah", version=1)},
            config_entries.SOURCE_ZEROCONF,
            data_entry_flow.FlowResultType.ABORT,
            {
                "test": (
                    DiscoveryKey(domain="test", key="bleh", version=1),
                    DiscoveryKey(domain="test", key="blah", version=1),
                )
            },
        ),
        # Discovery key added to ignored entry data
        (
            {
                "test": (
                    DiscoveryKey(domain="test", key="1", version=1),
                    DiscoveryKey(domain="test", key="2", version=1),
                    DiscoveryKey(domain="test", key="3", version=1),
                    DiscoveryKey(domain="test", key="4", version=1),
                    DiscoveryKey(domain="test", key="5", version=1),
                    DiscoveryKey(domain="test", key="6", version=1),
                    DiscoveryKey(domain="test", key="7", version=1),
                    DiscoveryKey(domain="test", key="8", version=1),
                    DiscoveryKey(domain="test", key="9", version=1),
                    DiscoveryKey(domain="test", key="10", version=1),
                )
            },
            "mock-unique-id",
            {"discovery_key": DiscoveryKey(domain="test", key="11", version=1)},
            config_entries.SOURCE_ZEROCONF,
            data_entry_flow.FlowResultType.ABORT,
            {
                "test": (
                    DiscoveryKey(domain="test", key="2", version=1),
                    DiscoveryKey(domain="test", key="3", version=1),
                    DiscoveryKey(domain="test", key="4", version=1),
                    DiscoveryKey(domain="test", key="5", version=1),
                    DiscoveryKey(domain="test", key="6", version=1),
                    DiscoveryKey(domain="test", key="7", version=1),
                    DiscoveryKey(domain="test", key="8", version=1),
                    DiscoveryKey(domain="test", key="9", version=1),
                    DiscoveryKey(domain="test", key="10", version=1),
                    DiscoveryKey(domain="test", key="11", version=1),
                )
            },
        ),
        # Discovery key already in ignored entry data
        (
            {"test": (DiscoveryKey(domain="test", key="blah", version=1),)},
            "mock-unique-id",
            {"discovery_key": DiscoveryKey(domain="test", key="blah", version=1)},
            config_entries.SOURCE_ZEROCONF,
            data_entry_flow.FlowResultType.ABORT,
            {"test": (DiscoveryKey(domain="test", key="blah", version=1),)},
        ),
        # Flow not aborted when unique id is not matching
        (
            {},
            "mock-unique-id-2",
            {"discovery_key": DiscoveryKey(domain="test", key="blah", version=1)},
            config_entries.SOURCE_ZEROCONF,
            data_entry_flow.FlowResultType.FORM,
            {},
        ),
    ],
)
@pytest.mark.parametrize(
    "entry_source",
    [
        config_entries.SOURCE_IGNORE,
        config_entries.SOURCE_USER,
        config_entries.SOURCE_ZEROCONF,
    ],
)
async def test_update_discovery_keys(
    hass: HomeAssistant,
    manager: config_entries.ConfigEntries,
    discovery_keys: tuple,
    entry_source: str,
    entry_unique_id: str,
    flow_context: dict,
    flow_source: str,
    flow_result: data_entry_flow.FlowResultType,
    updated_discovery_keys: tuple,
) -> None:
    """Test that discovery keys of an entry can be updated."""
    hass.config.components.add("comp")
    entry = MockConfigEntry(
        domain="comp",
        discovery_keys=discovery_keys,
        unique_id=entry_unique_id,
        state=config_entries.ConfigEntryState.LOADED,
        source=entry_source,
    )
    entry.add_to_hass(hass)

    mock_integration(hass, MockModule("comp"))
    mock_platform(hass, "comp.config_flow", None)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 1

        async def async_step_user(self, user_input=None):
            """Test user step."""
            await self.async_set_unique_id("mock-unique-id")
            self._abort_if_unique_id_configured(reload_on_update=False)
            return self.async_show_form(step_id="step2")

        async def async_step_step2(self, user_input=None):
            raise NotImplementedError

        async def async_step_zeroconf(self, discovery_info=None):
            """Test zeroconf step."""
            return await self.async_step_user(discovery_info)

    with (
        mock_config_flow("comp", TestFlow),
        patch(
            "homeassistant.config_entries.ConfigEntries.async_reload"
        ) as async_reload,
    ):
        result = await manager.flow.async_init(
            "comp", context={"source": flow_source} | flow_context
        )
        await hass.async_block_till_done()

    assert result["type"] == flow_result
    assert entry.data == {}
    assert entry.discovery_keys == updated_discovery_keys
    assert len(async_reload.mock_calls) == 0


@pytest.mark.parametrize(
    (
        "discovery_keys",
        "entry_source",
        "entry_unique_id",
        "flow_context",
        "flow_source",
        "flow_result",
        "updated_discovery_keys",
    ),
    [
        # Flow not aborted when user initiated flow
        (
            {},
            config_entries.SOURCE_IGNORE,
            "mock-unique-id-2",
            {"discovery_key": DiscoveryKey(domain="test", key="blah", version=1)},
            config_entries.SOURCE_USER,
            data_entry_flow.FlowResultType.FORM,
            {},
        ),
    ],
)
async def test_update_discovery_keys_2(
    hass: HomeAssistant,
    manager: config_entries.ConfigEntries,
    discovery_keys: tuple,
    entry_source: str,
    entry_unique_id: str,
    flow_context: dict,
    flow_source: str,
    flow_result: data_entry_flow.FlowResultType,
    updated_discovery_keys: tuple,
) -> None:
    """Test that discovery keys of an entry can be updated."""
    hass.config.components.add("comp")
    entry = MockConfigEntry(
        domain="comp",
        discovery_keys=discovery_keys,
        unique_id=entry_unique_id,
        state=config_entries.ConfigEntryState.LOADED,
        source=entry_source,
    )
    entry.add_to_hass(hass)

    mock_integration(hass, MockModule("comp"))
    mock_platform(hass, "comp.config_flow", None)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 1

        async def async_step_user(self, user_input=None):
            """Test user step."""
            await self.async_set_unique_id("mock-unique-id")
            self._abort_if_unique_id_configured(reload_on_update=False)
            return self.async_show_form(step_id="step2")

        async def async_step_step2(self, user_input=None):
            raise NotImplementedError

        async def async_step_zeroconf(self, discovery_info=None):
            """Test zeroconf step."""
            return await self.async_step_user(discovery_info)

    with (
        mock_config_flow("comp", TestFlow),
        patch(
            "homeassistant.config_entries.ConfigEntries.async_reload"
        ) as async_reload,
    ):
        result = await manager.flow.async_init(
            "comp", context={"source": flow_source} | flow_context
        )
        await hass.async_block_till_done()

    assert result["type"] == flow_result
    assert entry.data == {}
    assert entry.discovery_keys == updated_discovery_keys
    assert len(async_reload.mock_calls) == 0


async def test_async_current_entries_does_not_skip_ignore_non_user(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test that _async_current_entries does not skip ignore by default for non user step."""
    hass.config.components.add("comp")
    entry = MockConfigEntry(
        domain="comp",
        state=config_entries.ConfigEntryState.LOADED,
        source=config_entries.SOURCE_IGNORE,
    )
    entry.add_to_hass(hass)

    mock_setup_entry = AsyncMock(return_value=True)

    mock_integration(hass, MockModule("comp", async_setup_entry=mock_setup_entry))
    mock_platform(hass, "comp.config_flow", None)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 1

        async def async_step_import(self, user_input=None):
            """Test not the user step."""
            if self._async_current_entries():
                return self.async_abort(reason="single_instance_allowed")
            return self.async_create_entry(title="title", data={"token": "supersecret"})

    with mock_config_flow("comp", TestFlow), mock_config_flow("invalid_flow", 5):
        await manager.flow.async_init(
            "comp", context={"source": config_entries.SOURCE_IMPORT}
        )
        await hass.async_block_till_done()

    assert len(mock_setup_entry.mock_calls) == 0


async def test_async_current_entries_explicit_skip_ignore(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test that _async_current_entries can explicitly include ignore."""
    hass.config.components.add("comp")
    entry = MockConfigEntry(
        domain="comp",
        state=config_entries.ConfigEntryState.LOADED,
        source=config_entries.SOURCE_IGNORE,
    )
    entry.add_to_hass(hass)

    mock_setup_entry = AsyncMock(return_value=True)

    mock_integration(hass, MockModule("comp", async_setup_entry=mock_setup_entry))
    mock_platform(hass, "comp.config_flow", None)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 1

        async def async_step_import(self, user_input=None):
            """Test not the user step."""
            if self._async_current_entries(include_ignore=False):
                return self.async_abort(reason="single_instance_allowed")
            return self.async_create_entry(title="title", data={"token": "supersecret"})

    with mock_config_flow("comp", TestFlow), mock_config_flow("invalid_flow", 5):
        await manager.flow.async_init(
            "comp", context={"source": config_entries.SOURCE_IMPORT}
        )
        await hass.async_block_till_done()

    assert len(mock_setup_entry.mock_calls) == 1
    p_hass, p_entry = mock_setup_entry.mock_calls[0][1]

    assert p_hass is hass
    assert p_entry.data == {"token": "supersecret"}


async def test_async_current_entries_explicit_include_ignore(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test that _async_current_entries can explicitly include ignore."""
    hass.config.components.add("comp")
    entry = MockConfigEntry(
        domain="comp",
        state=config_entries.ConfigEntryState.LOADED,
        source=config_entries.SOURCE_IGNORE,
    )
    entry.add_to_hass(hass)

    mock_setup_entry = AsyncMock(return_value=True)

    mock_integration(hass, MockModule("comp", async_setup_entry=mock_setup_entry))
    mock_platform(hass, "comp.config_flow", None)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 1

        async def async_step_import(self, user_input=None):
            """Test not the user step."""
            if self._async_current_entries(include_ignore=True):
                return self.async_abort(reason="single_instance_allowed")
            return self.async_create_entry(title="title", data={"token": "supersecret"})

    with mock_config_flow("comp", TestFlow), mock_config_flow("invalid_flow", 5):
        await manager.flow.async_init(
            "comp", context={"source": config_entries.SOURCE_IMPORT}
        )
        await hass.async_block_till_done()

    assert len(mock_setup_entry.mock_calls) == 0


async def test_partial_flows_hidden(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test that flows that don't have a cur_step and haven't finished initing are hidden."""
    async_setup_entry = AsyncMock(return_value=True)
    mock_integration(hass, MockModule("comp", async_setup_entry=async_setup_entry))
    mock_platform(hass, "comp.config_flow", None)

    # A flag to test our assertion that `async_step_discovery` was called and is in its blocked state
    # This simulates if the step was e.g. doing network i/o
    discovery_started = asyncio.Event()

    # A flag to allow `async_step_discovery` to resume after we have verified the uninited flow is not
    # visible and has not triggered a discovery alert. This lets us control when the mocked network
    # i/o is complete.
    pause_discovery = asyncio.Event()

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 1

        async def async_step_discovery(self, discovery_info):
            """Test discovery step."""
            discovery_started.set()
            await pause_discovery.wait()
            return self.async_show_form(step_id="someform")

        async def async_step_someform(self, user_input=None):
            raise NotImplementedError

    with mock_config_flow("comp", TestFlow):
        # Start a config entry flow and wait for it to be blocked
        init_task = asyncio.ensure_future(
            manager.flow.async_init(
                "comp",
                context={"source": config_entries.SOURCE_DISCOVERY},
                data={"unique_id": "mock-unique-id"},
            )
        )
        await discovery_started.wait()

        # While it's blocked it shouldn't be visible or trigger discovery notifications
        assert len(hass.config_entries.flow.async_progress()) == 0

        # Let the flow init complete
        pause_discovery.set()

        # When it's complete it should now be visible in async_progress and have triggered
        # discovery notifications
        result = await init_task
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert len(hass.config_entries.flow.async_progress()) == 1


async def test_async_setup_init_entry(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test a config entry being initialized during integration setup."""

    async def mock_async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
        """Mock setup."""
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                "comp",
                context={"source": config_entries.SOURCE_IMPORT},
                data={},
            )
        )
        return True

    async_setup_entry = AsyncMock(return_value=True)
    mock_integration(
        hass,
        MockModule(
            "comp", async_setup=mock_async_setup, async_setup_entry=async_setup_entry
        ),
    )
    mock_platform(hass, "comp.config_flow", None)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 1

        async def async_step_import(self, user_input):
            """Test import step creating entry."""
            return self.async_create_entry(title="title", data={})

    with mock_config_flow("comp", TestFlow):
        assert await async_setup_component(hass, "comp", {})

        await hass.async_block_till_done()

        assert len(async_setup_entry.mock_calls) == 1

        entries = hass.config_entries.async_entries("comp")
        assert len(entries) == 1
        assert entries[0].state is config_entries.ConfigEntryState.LOADED


async def test_async_setup_init_entry_completes_before_loaded_event_fires(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test a config entry being initialized during integration setup before the loaded event fires."""
    load_events = async_capture_events(hass, EVENT_COMPONENT_LOADED)

    async def mock_async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
        """Mock setup."""
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                "comp",
                context={"source": config_entries.SOURCE_IMPORT},
                data={},
            )
        )
        return True

    async_setup_entry = AsyncMock(return_value=True)
    mock_integration(
        hass,
        MockModule(
            "comp", async_setup=mock_async_setup, async_setup_entry=async_setup_entry
        ),
    )
    mock_platform(hass, "comp.config_flow", None)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 1

        async def async_step_three(self, user_input=None):
            """Test import step creating entry."""
            return self.async_create_entry(title="title", data={})

        async def async_step_two(self, user_input=None):
            """Test import step creating entry."""
            return await self.async_step_three()

        async def async_step_one(self, user_input=None):
            """Test import step creating entry."""
            return await self.async_step_two()

        async def async_step_import(self, user_input=None):
            """Test import step creating entry."""
            return await self.async_step_one()

    # This test must not use hass.async_block_till_done()
    # as its explicitly testing what happens without it
    with mock_config_flow("comp", TestFlow):
        assert await async_setup_component(hass, "comp", {})
        assert len(async_setup_entry.mock_calls) == 1
        assert load_events[0].event_type == EVENT_COMPONENT_LOADED
        assert load_events[0].data == {"component": "comp"}
        entries = hass.config_entries.async_entries("comp")
        assert len(entries) == 1
        assert entries[0].state is config_entries.ConfigEntryState.LOADED


async def test_async_setup_update_entry(hass: HomeAssistant) -> None:
    """Test a config entry being updated during integration setup."""
    entry = MockConfigEntry(domain="comp", data={"value": "initial"})
    entry.add_to_hass(hass)

    async def mock_async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
        """Mock setup."""
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                "comp",
                context={"source": config_entries.SOURCE_IMPORT},
                data={},
            )
        )
        return True

    async def mock_async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
        """Mock setting up an entry."""
        assert entry.data["value"] == "updated"
        return True

    mock_integration(
        hass,
        MockModule(
            "comp",
            async_setup=mock_async_setup,
            async_setup_entry=mock_async_setup_entry,
        ),
    )
    mock_platform(hass, "comp.config_flow", None)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 1

        async def async_step_import(self, user_input):
            """Test import step updating existing entry."""
            assert (
                self.hass.config_entries.async_update_entry(
                    entry, data={"value": "updated"}
                )
                is True
            )
            return self.async_abort(reason="yo")

    with mock_config_flow("comp", TestFlow):
        assert await async_setup_component(hass, "comp", {})

        entries = hass.config_entries.async_entries("comp")
        assert len(entries) == 1
        assert entries[0].state is config_entries.ConfigEntryState.LOADED
        assert entries[0].data == {"value": "updated"}


@pytest.mark.parametrize(
    "discovery_source",
    [
        (config_entries.SOURCE_BLUETOOTH, BaseServiceInfo()),
        (config_entries.SOURCE_DISCOVERY, {}),
        (config_entries.SOURCE_SSDP, BaseServiceInfo()),
        (config_entries.SOURCE_USB, BaseServiceInfo()),
        (config_entries.SOURCE_HOMEKIT, BaseServiceInfo()),
        (config_entries.SOURCE_DHCP, BaseServiceInfo()),
        (config_entries.SOURCE_ZEROCONF, BaseServiceInfo()),
        (
            config_entries.SOURCE_HASSIO,
            HassioServiceInfo(config={}, name="Test", slug="test", uuid="1234"),
        ),
    ],
)
async def test_flow_with_default_discovery(
    hass: HomeAssistant,
    manager: config_entries.ConfigEntries,
    discovery_source: tuple[str, dict | BaseServiceInfo],
) -> None:
    """Test that finishing a default discovery flow removes the unique ID in the entry."""
    mock_integration(
        hass,
        MockModule("comp", async_setup_entry=AsyncMock(return_value=True)),
    )
    mock_platform(hass, "comp.config_flow", None)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 1

        async def async_step_user(self, user_input=None):
            """Test user step."""
            if user_input is None:
                return self.async_show_form(step_id="user")

            return self.async_create_entry(title="yo", data={})

    with mock_config_flow("comp", TestFlow):
        # Create one to be in progress
        result = await manager.flow.async_init(
            "comp", context={"source": discovery_source[0]}, data=discovery_source[1]
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM

        flows = hass.config_entries.flow.async_progress()
        assert len(flows) == 1
        assert (
            flows[0]["context"]["unique_id"]
            == config_entries.DEFAULT_DISCOVERY_UNIQUE_ID
        )

        # Finish flow
        result2 = await manager.flow.async_configure(
            result["flow_id"], user_input={"fake": "data"}
        )
        assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY

    assert len(hass.config_entries.flow.async_progress()) == 0

    entry = hass.config_entries.async_entries("comp")[0]
    assert entry.title == "yo"
    assert entry.source == discovery_source[0]
    assert entry.unique_id is None


async def test_flow_with_default_discovery_with_unique_id(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test discovery flow using the default discovery is ignored when unique ID is set."""
    mock_integration(hass, MockModule("comp"))
    mock_platform(hass, "comp.config_flow", None)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 1

        async def async_step_discovery(self, discovery_info):
            """Test discovery step."""
            await self.async_set_unique_id("mock-unique-id")
            # This call should make no difference, as a unique ID is set
            await self._async_handle_discovery_without_unique_id()
            return self.async_show_form(step_id="mock")

        async def async_step_mock(self, user_input=None):
            raise NotImplementedError

    with mock_config_flow("comp", TestFlow):
        result = await manager.flow.async_init(
            "comp", context={"source": config_entries.SOURCE_DISCOVERY}
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["unique_id"] == "mock-unique-id"


async def test_default_discovery_abort_existing_entries(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test that a flow without discovery implementation aborts when a config entry exists."""
    hass.config.components.add("comp")
    entry = MockConfigEntry(domain="comp", data={}, unique_id="mock-unique-id")
    entry.add_to_hass(hass)

    mock_integration(hass, MockModule("comp"))
    mock_platform(hass, "comp.config_flow", None)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 1

    with mock_config_flow("comp", TestFlow):
        result = await manager.flow.async_init(
            "comp", context={"source": config_entries.SOURCE_DISCOVERY}
        )
        assert result["type"] == data_entry_flow.FlowResultType.ABORT
        assert result["reason"] == "already_configured"


async def test_default_discovery_in_progress(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test that a flow using default discovery can only be triggered once."""
    mock_integration(hass, MockModule("comp"))
    mock_platform(hass, "comp.config_flow", None)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 1

        async def async_step_discovery(self, discovery_info):
            """Test discovery step."""
            await self.async_set_unique_id(discovery_info.get("unique_id"))
            await self._async_handle_discovery_without_unique_id()
            return self.async_show_form(step_id="mock")

        async def async_step_mock(self, user_input=None):
            raise NotImplementedError

    with mock_config_flow("comp", TestFlow):
        result = await manager.flow.async_init(
            "comp",
            context={"source": config_entries.SOURCE_DISCOVERY},
            data={"unique_id": "mock-unique-id"},
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM

        # Second discovery without a unique ID
        result2 = await manager.flow.async_init(
            "comp", context={"source": config_entries.SOURCE_DISCOVERY}, data={}
        )
        assert result2["type"] == data_entry_flow.FlowResultType.ABORT

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["unique_id"] == "mock-unique-id"


async def test_default_discovery_abort_on_new_unique_flow(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test that a flow using default discovery is aborted when a second flow with unique ID is created."""
    mock_integration(hass, MockModule("comp"))
    mock_platform(hass, "comp.config_flow", None)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 1

        async def async_step_discovery(self, discovery_info):
            """Test discovery step."""
            await self.async_set_unique_id(discovery_info.get("unique_id"))
            await self._async_handle_discovery_without_unique_id()
            return self.async_show_form(step_id="mock")

        async def async_step_mock(self, user_input=None):
            raise NotImplementedError

    with mock_config_flow("comp", TestFlow):
        # First discovery with default, no unique ID
        result2 = await manager.flow.async_init(
            "comp", context={"source": config_entries.SOURCE_DISCOVERY}, data={}
        )
        assert result2["type"] == data_entry_flow.FlowResultType.FORM

        # Second discovery brings in a unique ID
        result = await manager.flow.async_init(
            "comp",
            context={"source": config_entries.SOURCE_DISCOVERY},
            data={"unique_id": "mock-unique-id"},
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM

    # Ensure the first one is cancelled and we end up with just the last one
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["unique_id"] == "mock-unique-id"


async def test_default_discovery_abort_on_user_flow_complete(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test that a flow using default discovery is aborted when a second flow completes."""
    mock_integration(hass, MockModule("comp"))
    mock_platform(hass, "comp.config_flow", None)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 1

        async def async_step_user(self, user_input=None):
            """Test user step."""
            if user_input is None:
                return self.async_show_form(step_id="user")
            return self.async_create_entry(title="title", data={"token": "supersecret"})

        async def async_step_discovery(self, discovery_info=None):
            """Test discovery step."""
            await self._async_handle_discovery_without_unique_id()
            return self.async_show_form(step_id="mock")

        async def async_step_mock(self, user_input=None):
            raise NotImplementedError

    with mock_config_flow("comp", TestFlow):
        # First discovery with default, no unique ID
        flow1 = await manager.flow.async_init(
            "comp", context={"source": config_entries.SOURCE_DISCOVERY}, data={}
        )
        assert flow1["type"] == data_entry_flow.FlowResultType.FORM

        flows = hass.config_entries.flow.async_progress()
        assert len(flows) == 1

        # User sets up a manual flow
        flow2 = await manager.flow.async_init(
            "comp", context={"source": config_entries.SOURCE_USER}
        )
        assert flow2["type"] == data_entry_flow.FlowResultType.FORM

        flows = hass.config_entries.flow.async_progress()
        assert len(flows) == 2

        # Complete the manual flow
        result = await hass.config_entries.flow.async_configure(flow2["flow_id"], {})
        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY

    # Ensure the first flow is gone now
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 0


async def test_flow_same_device_multiple_sources(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test discovery of the same devices from multiple discovery sources."""
    mock_integration(
        hass,
        MockModule("comp", async_setup_entry=AsyncMock(return_value=True)),
    )
    mock_platform(hass, "comp.config_flow", None)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 1

        async def async_step_zeroconf(self, discovery_info=None):
            """Test zeroconf step."""
            return await self._async_discovery_handler(discovery_info)

        async def async_step_homekit(self, discovery_info=None):
            """Test homekit step."""
            return await self._async_discovery_handler(discovery_info)

        async def _async_discovery_handler(self, discovery_info=None):
            """Test any discovery handler."""
            await self.async_set_unique_id("thisid")
            self._abort_if_unique_id_configured()
            await asyncio.sleep(0.1)
            return await self.async_step_link()

        async def async_step_link(self, user_input=None):
            """Test a link step."""
            if user_input is None:
                return self.async_show_form(step_id="link")
            return self.async_create_entry(title="title", data={"token": "supersecret"})

    with mock_config_flow("comp", TestFlow):
        # Create one to be in progress
        flow1 = manager.flow.async_init(
            "comp", context={"source": config_entries.SOURCE_ZEROCONF}
        )
        flow2 = manager.flow.async_init(
            "comp", context={"source": config_entries.SOURCE_ZEROCONF}
        )
        flow3 = manager.flow.async_init(
            "comp", context={"source": config_entries.SOURCE_HOMEKIT}
        )
        result1, result2, result3 = await asyncio.gather(flow1, flow2, flow3)

        flows = hass.config_entries.flow.async_progress()
        assert len(flows) == 1
        assert flows[0]["context"]["unique_id"] == "thisid"

        # Finish flow
        result2 = await manager.flow.async_configure(
            flows[0]["flow_id"], user_input={"fake": "data"}
        )
        assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY

    assert len(hass.config_entries.flow.async_progress()) == 0

    entry = hass.config_entries.async_entries("comp")[0]
    assert entry.title == "title"
    assert entry.source in {
        config_entries.SOURCE_ZEROCONF,
        config_entries.SOURCE_HOMEKIT,
    }
    assert entry.unique_id == "thisid"


async def test_updating_entry_with_and_without_changes(
    manager: config_entries.ConfigEntries,
) -> None:
    """Test that we can update an entry data."""
    entry = MockConfigEntry(
        domain="test",
        data={"first": True},
        title="thetitle",
        options={"option": True},
        unique_id="abc123",
        state=config_entries.ConfigEntryState.SETUP_ERROR,
    )
    entry.add_to_manager(manager)
    assert "abc123" in str(entry)

    assert manager.async_entry_for_domain_unique_id("test", "abc123") is entry

    assert manager.async_update_entry(entry) is False

    for change, expected_value in (
        ({"data": {"second": True, "third": 456}}, {"second": True, "third": 456}),
        ({"data": {"second": True}}, {"second": True}),
        ({"minor_version": 2}, 2),
        ({"options": {"hello": True}}, {"hello": True}),
        ({"pref_disable_new_entities": True}, True),
        ({"pref_disable_polling": True}, True),
        ({"title": "sometitle"}, "sometitle"),
        ({"unique_id": "abcd1234"}, "abcd1234"),
        ({"version": 2}, 2),
    ):
        assert manager.async_update_entry(entry, **change) is True
        key = next(iter(change))
        assert getattr(entry, key) == expected_value
        assert manager.async_update_entry(entry, **change) is False

    assert manager.async_entry_for_domain_unique_id("test", "abc123") is None
    assert manager.async_entry_for_domain_unique_id("test", "abcd1234") is entry
    assert "abcd1234" in str(entry)


async def test_entry_reload_calls_on_unload_listeners(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test reload calls the on unload listeners."""
    entry = MockConfigEntry(domain="comp", state=config_entries.ConfigEntryState.LOADED)
    entry.add_to_hass(hass)

    async_setup = AsyncMock(return_value=True)
    mock_setup_entry = AsyncMock(return_value=True)
    async_unload_entry = AsyncMock(return_value=True)

    mock_integration(
        hass,
        MockModule(
            "comp",
            async_setup=async_setup,
            async_setup_entry=mock_setup_entry,
            async_unload_entry=async_unload_entry,
        ),
    )
    mock_platform(hass, "comp.config_flow", None)
    hass.config.components.add("comp")

    mock_unload_callback = Mock()

    entry.async_on_unload(mock_unload_callback)

    assert await manager.async_reload(entry.entry_id)
    assert len(async_unload_entry.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_unload_callback.mock_calls) == 1
    assert entry.state is config_entries.ConfigEntryState.LOADED

    assert await manager.async_reload(entry.entry_id)
    assert len(async_unload_entry.mock_calls) == 2
    assert len(mock_setup_entry.mock_calls) == 2
    # Since we did not register another async_on_unload it should
    # have only been called once
    assert len(mock_unload_callback.mock_calls) == 1
    assert entry.state is config_entries.ConfigEntryState.LOADED


@pytest.mark.parametrize(
    ("source_state", "target_state", "transition_method_name", "call_count"),
    [
        (
            config_entries.ConfigEntryState.NOT_LOADED,
            config_entries.ConfigEntryState.LOADED,
            "async_setup",
            2,
        ),
        (
            config_entries.ConfigEntryState.LOADED,
            config_entries.ConfigEntryState.NOT_LOADED,
            "async_unload",
            2,
        ),
        (
            config_entries.ConfigEntryState.LOADED,
            config_entries.ConfigEntryState.LOADED,
            "async_reload",
            4,
        ),
    ],
)
async def test_entry_state_change_calls_listener(
    hass: HomeAssistant,
    manager: config_entries.ConfigEntries,
    source_state: config_entries.ConfigEntryState,
    target_state: config_entries.ConfigEntryState,
    transition_method_name: str,
    call_count: int,
) -> None:
    """Test listeners get called on entry state changes."""
    entry = MockConfigEntry(domain="comp", state=source_state)
    entry.add_to_hass(hass)

    mock_integration(
        hass,
        MockModule(
            "comp",
            async_setup=AsyncMock(return_value=True),
            async_setup_entry=AsyncMock(return_value=True),
            async_unload_entry=AsyncMock(return_value=True),
        ),
    )
    mock_platform(hass, "comp.config_flow", None)
    hass.config.components.add("comp")

    mock_state_change_callback = Mock()
    entry.async_on_state_change(mock_state_change_callback)

    transition_method = getattr(manager, transition_method_name)
    await transition_method(entry.entry_id)

    assert len(mock_state_change_callback.mock_calls) == call_count
    assert entry.state is target_state


async def test_entry_state_change_listener_removed(
    hass: HomeAssistant,
    manager: config_entries.ConfigEntries,
) -> None:
    """Test state_change listener can be removed."""
    entry = MockConfigEntry(
        domain="comp", state=config_entries.ConfigEntryState.NOT_LOADED
    )
    entry.add_to_hass(hass)

    mock_integration(
        hass,
        MockModule(
            "comp",
            async_setup=AsyncMock(return_value=True),
            async_setup_entry=AsyncMock(return_value=True),
            async_unload_entry=AsyncMock(return_value=True),
        ),
    )
    mock_platform(hass, "comp.config_flow", None)
    hass.config.components.add("comp")

    mock_state_change_callback = Mock()
    remove = entry.async_on_state_change(mock_state_change_callback)

    await manager.async_setup(entry.entry_id)

    assert len(mock_state_change_callback.mock_calls) == 2
    assert entry.state is config_entries.ConfigEntryState.LOADED

    remove()

    await manager.async_unload(entry.entry_id)

    # the listener should no longer be called
    assert len(mock_state_change_callback.mock_calls) == 2
    assert entry.state is config_entries.ConfigEntryState.NOT_LOADED


async def test_entry_state_change_error_does_not_block_transition(
    hass: HomeAssistant,
    manager: config_entries.ConfigEntries,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test we transition states normally even if the callback throws in on_state_change."""
    entry = MockConfigEntry(
        title="test", domain="comp", state=config_entries.ConfigEntryState.NOT_LOADED
    )
    entry.add_to_hass(hass)

    mock_integration(
        hass,
        MockModule(
            "comp",
            async_setup=AsyncMock(return_value=True),
            async_setup_entry=AsyncMock(return_value=True),
            async_unload_entry=AsyncMock(return_value=True),
        ),
    )
    mock_platform(hass, "comp.config_flow", None)
    hass.config.components.add("comp")

    mock_state_change_callback = Mock(side_effect=Exception())

    entry.async_on_state_change(mock_state_change_callback)

    await manager.async_setup(entry.entry_id)

    assert len(mock_state_change_callback.mock_calls) == 2
    assert entry.state is config_entries.ConfigEntryState.LOADED
    assert "Error calling on_state_change callback for test (comp)" in caplog.text


async def test_setup_raise_entry_error(
    hass: HomeAssistant,
    manager: config_entries.ConfigEntries,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a setup raising ConfigEntryError."""
    entry = MockConfigEntry(title="test_title", domain="test")
    entry.add_to_hass(hass)

    mock_setup_entry = AsyncMock(
        side_effect=ConfigEntryError("Incompatible firmware version")
    )
    mock_integration(hass, MockModule("test", async_setup_entry=mock_setup_entry))
    mock_platform(hass, "test.config_flow", None)

    await manager.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert (
        "Error setting up entry test_title for test: Incompatible firmware version"
        in caplog.text
    )

    assert entry.state is config_entries.ConfigEntryState.SETUP_ERROR
    assert entry.reason == "Incompatible firmware version"


async def test_setup_raise_entry_error_from_first_coordinator_update(
    hass: HomeAssistant,
    manager: config_entries.ConfigEntries,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test async_config_entry_first_refresh raises ConfigEntryError."""
    entry = MockConfigEntry(title="test_title", domain="test")
    entry.add_to_hass(hass)

    async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
        """Mock setup entry with a simple coordinator."""

        async def _async_update_data():
            raise ConfigEntryError("Incompatible firmware version")

        coordinator = DataUpdateCoordinator(
            hass,
            logging.getLogger(__name__),
            name="any",
            update_method=_async_update_data,
            update_interval=timedelta(seconds=1000),
        )

        await coordinator.async_config_entry_first_refresh()
        return True

    mock_integration(hass, MockModule("test", async_setup_entry=async_setup_entry))
    mock_platform(hass, "test.config_flow", None)

    await manager.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert (
        "Error setting up entry test_title for test: Incompatible firmware version"
        in caplog.text
    )

    assert entry.state is config_entries.ConfigEntryState.SETUP_ERROR
    assert entry.reason == "Incompatible firmware version"


async def test_setup_not_raise_entry_error_from_future_coordinator_update(
    hass: HomeAssistant,
    manager: config_entries.ConfigEntries,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a coordinator not raises ConfigEntryError in the future."""
    entry = MockConfigEntry(title="test_title", domain="test")
    entry.add_to_hass(hass)

    async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
        """Mock setup entry with a simple coordinator."""

        async def _async_update_data():
            raise ConfigEntryError("Incompatible firmware version")

        coordinator = DataUpdateCoordinator(
            hass,
            logging.getLogger(__name__),
            name="any",
            update_method=_async_update_data,
            update_interval=timedelta(seconds=1000),
        )

        await coordinator.async_refresh()
        return True

    mock_integration(hass, MockModule("test", async_setup_entry=async_setup_entry))
    mock_platform(hass, "test.config_flow", None)

    await manager.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert (
        "Config entry setup failed while fetching any data: Incompatible firmware"
        " version" in caplog.text
    )

    assert entry.state is config_entries.ConfigEntryState.LOADED


async def test_setup_raise_auth_failed(
    hass: HomeAssistant,
    manager: config_entries.ConfigEntries,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a setup raising ConfigEntryAuthFailed."""
    entry = MockConfigEntry(title="test_title", domain="test")
    entry.add_to_hass(hass)

    mock_setup_entry = AsyncMock(
        side_effect=ConfigEntryAuthFailed("The password is no longer valid")
    )
    mock_integration(hass, MockModule("test", async_setup_entry=mock_setup_entry))
    mock_platform(hass, "test.config_flow", None)

    await manager.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert "could not authenticate: The password is no longer valid" in caplog.text

    assert entry.state is config_entries.ConfigEntryState.SETUP_ERROR
    assert entry.reason == "The password is no longer valid"
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["entry_id"] == entry.entry_id
    assert flows[0]["context"]["source"] == config_entries.SOURCE_REAUTH
    assert flows[0]["context"]["title_placeholders"] == {"name": "test_title"}

    caplog.clear()
    entry._async_set_state(hass, config_entries.ConfigEntryState.NOT_LOADED, None)

    await manager.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert "could not authenticate: The password is no longer valid" in caplog.text

    # Verify multiple ConfigEntryAuthFailed does not generate a second flow
    assert entry.state is config_entries.ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1


async def test_setup_raise_auth_failed_from_first_coordinator_update(
    hass: HomeAssistant,
    manager: config_entries.ConfigEntries,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test async_config_entry_first_refresh raises ConfigEntryAuthFailed."""
    entry = MockConfigEntry(title="test_title", domain="test")
    entry.add_to_hass(hass)

    async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
        """Mock setup entry with a simple coordinator."""

        async def _async_update_data():
            raise ConfigEntryAuthFailed("The password is no longer valid")

        coordinator = DataUpdateCoordinator(
            hass,
            logging.getLogger(__name__),
            name="any",
            update_method=_async_update_data,
            update_interval=timedelta(seconds=1000),
        )

        await coordinator.async_config_entry_first_refresh()
        return True

    mock_integration(hass, MockModule("test", async_setup_entry=async_setup_entry))
    mock_platform(hass, "test.config_flow", None)

    await manager.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert "could not authenticate: The password is no longer valid" in caplog.text

    assert entry.state is config_entries.ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["entry_id"] == entry.entry_id
    assert flows[0]["context"]["source"] == config_entries.SOURCE_REAUTH

    caplog.clear()
    entry._async_set_state(hass, config_entries.ConfigEntryState.NOT_LOADED, None)

    await manager.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert "could not authenticate: The password is no longer valid" in caplog.text

    # Verify multiple ConfigEntryAuthFailed does not generate a second flow
    assert entry.state is config_entries.ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1


async def test_setup_raise_auth_failed_from_future_coordinator_update(
    hass: HomeAssistant,
    manager: config_entries.ConfigEntries,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a coordinator raises ConfigEntryAuthFailed in the future."""
    entry = MockConfigEntry(title="test_title", domain="test")
    entry.add_to_hass(hass)

    async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
        """Mock setup entry with a simple coordinator."""

        async def _async_update_data():
            raise ConfigEntryAuthFailed("The password is no longer valid")

        coordinator = DataUpdateCoordinator(
            hass,
            logging.getLogger(__name__),
            name="any",
            update_method=_async_update_data,
            update_interval=timedelta(seconds=1000),
        )

        await coordinator.async_refresh()
        return True

    mock_integration(hass, MockModule("test", async_setup_entry=async_setup_entry))
    mock_platform(hass, "test.config_flow", None)

    await manager.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert "Authentication failed while fetching" in caplog.text
    assert "The password is no longer valid" in caplog.text

    assert entry.state is config_entries.ConfigEntryState.LOADED
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["entry_id"] == entry.entry_id
    assert flows[0]["context"]["source"] == config_entries.SOURCE_REAUTH

    caplog.clear()
    entry._async_set_state(hass, config_entries.ConfigEntryState.NOT_LOADED, None)

    await manager.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert "Authentication failed while fetching" in caplog.text
    assert "The password is no longer valid" in caplog.text

    # Verify multiple ConfigEntryAuthFailed does not generate a second flow
    assert entry.state is config_entries.ConfigEntryState.LOADED
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1


async def test_initialize_and_shutdown(hass: HomeAssistant) -> None:
    """Test we call the shutdown function at stop."""
    manager = config_entries.ConfigEntries(hass, {})

    with patch.object(manager, "_async_shutdown") as mock_async_shutdown:
        await manager.async_initialize()
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()

    assert mock_async_shutdown.called


async def test_setup_retrying_during_shutdown(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test if we shutdown an entry that is in retry mode."""
    entry = MockConfigEntry(domain="test")
    entry.add_to_hass(hass)

    mock_setup_entry = AsyncMock(side_effect=ConfigEntryNotReady)
    mock_integration(hass, MockModule("test", async_setup_entry=mock_setup_entry))
    mock_platform(hass, "test.config_flow", None)

    with patch("homeassistant.helpers.event.async_call_later") as mock_call:
        await manager.async_setup(entry.entry_id)

    assert entry.state is config_entries.ConfigEntryState.SETUP_RETRY
    assert len(mock_call.return_value.mock_calls) == 0

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    assert len(mock_call.return_value.mock_calls) == 0

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(hours=4))
    await hass.async_block_till_done()

    assert len(mock_call.return_value.mock_calls) == 0

    # Cleanup to avoid lingering timer
    entry.async_cancel_retry_setup()


async def test_scheduling_reload_cancels_setup_retry(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test scheduling a reload cancels setup retry."""
    entry = MockConfigEntry(domain="test")
    entry.add_to_hass(hass)

    mock_setup_entry = AsyncMock(side_effect=ConfigEntryNotReady)
    mock_integration(hass, MockModule("test", async_setup_entry=mock_setup_entry))
    mock_platform(hass, "test.config_flow", None)
    cancel_mock = Mock()

    with patch(
        "homeassistant.config_entries.async_call_later", return_value=cancel_mock
    ):
        await manager.async_setup(entry.entry_id)

    assert entry.state is config_entries.ConfigEntryState.SETUP_RETRY
    assert len(cancel_mock.mock_calls) == 0

    mock_setup_entry.side_effect = None
    mock_setup_entry.return_value = True
    hass.config_entries.async_schedule_reload(entry.entry_id)

    assert len(cancel_mock.mock_calls) == 1
    await hass.async_block_till_done()
    assert entry.state is config_entries.ConfigEntryState.LOADED


async def test_scheduling_reload_unknown_entry(hass: HomeAssistant) -> None:
    """Test scheduling a reload raises with an unknown entry."""
    with pytest.raises(config_entries.UnknownEntry):
        hass.config_entries.async_schedule_reload("non-existing")


@pytest.mark.parametrize(
    ("matchers", "reason"),
    [
        ({}, "already_configured"),
        ({"host": "3.3.3.3"}, "no_match"),
        ({"vendor": "no_match"}, "no_match"),
        ({"host": "3.4.5.6"}, "already_configured"),
        ({"host": "3.4.5.6", "ip": "3.4.5.6"}, "no_match"),
        ({"host": "3.4.5.6", "ip": "1.2.3.4"}, "already_configured"),
        ({"host": "3.4.5.6", "ip": "1.2.3.4", "port": 23}, "already_configured"),
        (
            {"host": "9.9.9.9", "ip": "6.6.6.6", "port": 12, "vendor": "zoo"},
            "already_configured",
        ),
        ({"vendor": "zoo"}, "already_configured"),
        ({"ip": "9.9.9.9"}, "already_configured"),
        ({"ip": "7.7.7.7"}, "no_match"),  # ignored
        # The next two data sets ensure options or data match
        # as options previously shadowed data when matching.
        ({"vendor": "data"}, "already_configured"),
        (
            {"vendor": "options"},
            "already_configured",
        ),
    ],
)
async def test_async_abort_entries_match(
    hass: HomeAssistant,
    manager: config_entries.ConfigEntries,
    matchers: dict[str, str],
    reason: str,
) -> None:
    """Test aborting if matching config entries exist."""
    MockConfigEntry(
        domain="comp", data={"ip": "1.2.3.4", "host": "4.5.6.7", "port": 23}
    ).add_to_hass(hass)
    MockConfigEntry(
        domain="comp", data={"ip": "9.9.9.9", "host": "4.5.6.7", "port": 23}
    ).add_to_hass(hass)
    MockConfigEntry(
        domain="comp", data={"ip": "1.2.3.4", "host": "3.4.5.6", "port": 23}
    ).add_to_hass(hass)
    MockConfigEntry(
        domain="comp",
        source=config_entries.SOURCE_IGNORE,
        data={"ip": "7.7.7.7", "host": "4.5.6.7", "port": 23},
    ).add_to_hass(hass)
    MockConfigEntry(
        domain="comp",
        data={"ip": "6.6.6.6", "host": "9.9.9.9", "port": 12},
        options={"vendor": "zoo"},
    ).add_to_hass(hass)
    MockConfigEntry(
        domain="comp",
        data={"vendor": "data"},
        options={"vendor": "options"},
    ).add_to_hass(hass)

    mock_setup_entry = AsyncMock(return_value=True)

    mock_integration(hass, MockModule("comp", async_setup_entry=mock_setup_entry))
    mock_platform(hass, "comp.config_flow", None)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 1

        async def async_step_user(self, user_input=None):
            """Test user step."""
            self._async_abort_entries_match(matchers)
            return self.async_abort(reason="no_match")

    with mock_config_flow("comp", TestFlow), mock_config_flow("invalid_flow", 5):
        result = await manager.flow.async_init(
            "comp", context={"source": config_entries.SOURCE_USER}
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == reason


@pytest.mark.parametrize(
    ("matchers", "reason"),
    [
        ({}, "already_configured"),
        ({"host": "3.3.3.3"}, "no_match"),
        ({"vendor": "no_match"}, "no_match"),
        ({"host": "3.4.5.6"}, "already_configured"),
        ({"host": "3.4.5.6", "ip": "3.4.5.6"}, "no_match"),
        ({"host": "3.4.5.6", "ip": "1.2.3.4"}, "already_configured"),
        ({"host": "3.4.5.6", "ip": "1.2.3.4", "port": 23}, "already_configured"),
        (
            {"host": "9.9.9.9", "ip": "6.6.6.6", "port": 12, "vendor": "zoo"},
            "already_configured",
        ),
        ({"vendor": "zoo"}, "already_configured"),
        ({"ip": "9.9.9.9"}, "already_configured"),
        ({"ip": "7.7.7.7"}, "no_match"),  # ignored
        # The next two data sets ensure options or data match
        # as options previously shadowed data when matching.
        ({"vendor": "data"}, "already_configured"),
        (
            {"vendor": "options"},
            "already_configured",
        ),
    ],
)
async def test_async_abort_entries_match_options_flow(
    hass: HomeAssistant,
    manager: config_entries.ConfigEntries,
    matchers: dict[str, str],
    reason: str,
) -> None:
    """Test aborting if matching config entries exist."""
    MockConfigEntry(
        domain="test_abort", data={"ip": "1.2.3.4", "host": "4.5.6.7", "port": 23}
    ).add_to_hass(hass)
    MockConfigEntry(
        domain="test_abort", data={"ip": "9.9.9.9", "host": "4.5.6.7", "port": 23}
    ).add_to_hass(hass)
    MockConfigEntry(
        domain="test_abort", data={"ip": "1.2.3.4", "host": "3.4.5.6", "port": 23}
    ).add_to_hass(hass)
    MockConfigEntry(
        domain="test_abort",
        source=config_entries.SOURCE_IGNORE,
        data={"ip": "7.7.7.7", "host": "4.5.6.7", "port": 23},
    ).add_to_hass(hass)
    MockConfigEntry(
        domain="test_abort",
        data={"ip": "6.6.6.6", "host": "9.9.9.9", "port": 12},
        options={"vendor": "zoo"},
    ).add_to_hass(hass)
    MockConfigEntry(
        domain="test_abort",
        data={"vendor": "data"},
        options={"vendor": "options"},
    ).add_to_hass(hass)

    original_entry = MockConfigEntry(domain="test_abort", data={})
    original_entry.add_to_hass(hass)

    mock_setup_entry = AsyncMock(return_value=True)

    mock_integration(hass, MockModule("test_abort", async_setup_entry=mock_setup_entry))
    mock_platform(hass, "test_abort.config_flow", None)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        @staticmethod
        @callback
        def async_get_options_flow(config_entry):
            """Test options flow."""

            class _OptionsFlow(config_entries.OptionsFlow):
                """Test flow."""

                async def async_step_init(self, user_input=None):
                    """Test user step."""
                    if errors := self._async_abort_entries_match(user_input):
                        return self.async_abort(reason=errors["base"])
                    return self.async_abort(reason="no_match")

            return _OptionsFlow()

    with mock_config_flow("test_abort", TestFlow):
        result = await hass.config_entries.options.async_init(
            original_entry.entry_id, data=matchers
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == reason


async def test_loading_old_data(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test automatically migrating old data."""
    hass_storage[config_entries.STORAGE_KEY] = {
        "version": 1,
        "data": {
            "entries": [
                {
                    "version": 5,
                    "domain": "my_domain",
                    "entry_id": "mock-id",
                    "data": {"my": "data"},
                    "source": "user",
                    "title": "Mock title",
                    "system_options": {"disable_new_entities": True},
                }
            ]
        },
    }
    manager = config_entries.ConfigEntries(hass, {})
    await manager.async_initialize()

    entries = manager.async_entries()
    assert len(entries) == 1
    entry = entries[0]
    assert entry.version == 5
    assert entry.domain == "my_domain"
    assert entry.entry_id == "mock-id"
    assert entry.title == "Mock title"
    assert entry.data == {"my": "data"}
    assert entry.pref_disable_new_entities is True


async def test_deprecated_disabled_by_str_ctor() -> None:
    """Test deprecated str disabled_by constructor enumizes and logs a warning."""
    with pytest.raises(
        TypeError, match="disabled_by must be a ConfigEntryDisabler value, got user"
    ):
        MockConfigEntry(disabled_by=config_entries.ConfigEntryDisabler.USER.value)


async def test_deprecated_disabled_by_str_set(
    hass: HomeAssistant,
    manager: config_entries.ConfigEntries,
) -> None:
    """Test deprecated str set disabled_by enumizes and logs a warning."""
    entry = MockConfigEntry(domain="comp")
    entry.add_to_manager(manager)
    hass.config.components.add("comp")
    with pytest.raises(
        TypeError, match="disabled_by must be a ConfigEntryDisabler value, got user"
    ):
        await manager.async_set_disabled_by(
            entry.entry_id, config_entries.ConfigEntryDisabler.USER.value
        )


async def test_entry_reload_concurrency(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test multiple reload calls do not cause a reload race."""
    entry = MockConfigEntry(domain="comp", state=config_entries.ConfigEntryState.LOADED)
    entry.add_to_hass(hass)

    async_setup = AsyncMock(return_value=True)
    loaded = 1

    async def _async_setup_entry(*args, **kwargs):
        await asyncio.sleep(0)
        nonlocal loaded
        loaded += 1
        return loaded == 1

    async def _async_unload_entry(*args, **kwargs):
        await asyncio.sleep(0)
        nonlocal loaded
        loaded -= 1
        return loaded == 0

    mock_integration(
        hass,
        MockModule(
            "comp",
            async_setup=async_setup,
            async_setup_entry=_async_setup_entry,
            async_unload_entry=_async_unload_entry,
        ),
    )
    mock_platform(hass, "comp.config_flow", None)
    hass.config.components.add("comp")
    tasks = [
        asyncio.create_task(manager.async_reload(entry.entry_id)) for _ in range(15)
    ]
    await asyncio.gather(*tasks)
    assert entry.state is config_entries.ConfigEntryState.LOADED
    assert loaded == 1


async def test_entry_reload_concurrency_not_setup_setup(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test multiple reload calls do not cause a reload race."""
    entry = MockConfigEntry(
        domain="comp", state=config_entries.ConfigEntryState.NOT_LOADED
    )
    entry.add_to_hass(hass)

    async_setup = AsyncMock(return_value=True)
    loaded = 0

    async def _async_setup_entry(*args, **kwargs):
        await asyncio.sleep(0)
        nonlocal loaded
        loaded += 1
        return loaded == 1

    async def _async_unload_entry(*args, **kwargs):
        await asyncio.sleep(0)
        nonlocal loaded
        loaded -= 1
        return loaded == 0

    mock_integration(
        hass,
        MockModule(
            "comp",
            async_setup=async_setup,
            async_setup_entry=_async_setup_entry,
            async_unload_entry=_async_unload_entry,
        ),
    )
    mock_platform(hass, "comp.config_flow", None)
    tasks = [
        asyncio.create_task(manager.async_reload(entry.entry_id)) for _ in range(15)
    ]
    await asyncio.gather(*tasks)
    assert entry.state is config_entries.ConfigEntryState.LOADED
    assert loaded == 1


async def test_unique_id_update_while_setup_in_progress(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test we handle the case where the config entry is updated while setup is in progress."""

    async def mock_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
        """Mock setting up entry."""
        await asyncio.sleep(0.1)
        return True

    async def mock_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
        """Mock unloading an entry."""
        return True

    hass.config.components.add("comp")
    entry = MockConfigEntry(
        domain="comp",
        data={"additional": "data", "host": "0.0.0.0"},
        unique_id="mock-unique-id",
        state=config_entries.ConfigEntryState.SETUP_RETRY,
    )
    entry.add_to_hass(hass)

    mock_integration(
        hass,
        MockModule(
            "comp",
            async_setup_entry=mock_setup_entry,
            async_unload_entry=mock_unload_entry,
        ),
    )
    mock_platform(hass, "comp.config_flow", None)
    updates = {"host": "1.1.1.1"}

    hass.async_create_task(hass.config_entries.async_reload(entry.entry_id))
    await asyncio.sleep(0)
    assert entry.state is config_entries.ConfigEntryState.SETUP_IN_PROGRESS

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 1

        async def async_step_user(self, user_input=None):
            """Test user step."""
            await self.async_set_unique_id("mock-unique-id")
            await self._abort_if_unique_id_configured(
                updates=updates, reload_on_update=True
            )

    with (
        mock_config_flow("comp", TestFlow),
        patch(
            "homeassistant.config_entries.ConfigEntries.async_reload"
        ) as async_reload,
    ):
        result = await manager.flow.async_init(
            "comp", context={"source": config_entries.SOURCE_USER}
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data["host"] == "1.1.1.1"
    assert entry.data["additional"] == "data"

    # Setup is already in progress, we should not reload
    # if it fails it will go into a retry state and try again
    assert len(async_reload.mock_calls) == 0
    await hass.async_block_till_done()
    assert entry.state is config_entries.ConfigEntryState.LOADED


async def test_disallow_entry_reload_with_setup_in_progress(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test we do not allow reload while the config entry is still setting up."""
    entry = MockConfigEntry(
        domain="comp", state=config_entries.ConfigEntryState.SETUP_IN_PROGRESS
    )
    entry.add_to_hass(hass)
    hass.config.components.add("comp")

    with pytest.raises(
        config_entries.OperationNotAllowed,
        match=str(config_entries.ConfigEntryState.SETUP_IN_PROGRESS),
    ):
        assert await manager.async_reload(entry.entry_id)
    assert entry.state is config_entries.ConfigEntryState.SETUP_IN_PROGRESS


async def test_reauth(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test the async_reauth_helper."""
    entry = MockConfigEntry(title="test_title", domain="test")
    entry.add_to_hass(hass)
    entry2 = MockConfigEntry(title="test_title", domain="test")
    entry2.add_to_hass(hass)

    mock_setup_entry = AsyncMock(return_value=True)
    mock_integration(hass, MockModule("test", async_setup_entry=mock_setup_entry))
    mock_platform(hass, "test.config_flow", None)

    await manager.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    flow = hass.config_entries.flow
    with patch.object(flow, "async_init", wraps=flow.async_init) as mock_init:
        entry.async_start_reauth(
            hass,
            context={"extra_context": "some_extra_context"},
            data={"extra_data": 1234},
        )
        await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["entry_id"] == entry.entry_id
    assert flows[0]["context"]["source"] == config_entries.SOURCE_REAUTH
    assert flows[0]["context"]["title_placeholders"] == {"name": "test_title"}
    assert flows[0]["context"]["extra_context"] == "some_extra_context"

    assert mock_init.call_args.kwargs["data"]["extra_data"] == 1234

    assert entry.entry_id != entry2.entry_id

    # Check that we can't start duplicate reauth flows
    entry.async_start_reauth(hass, {"extra_context": "some_extra_context"})
    await hass.async_block_till_done()
    assert len(hass.config_entries.flow.async_progress()) == 1

    # Check that we can't start duplicate reauth flows when the context is different
    entry.async_start_reauth(hass, {"diff": "diff"})
    await hass.async_block_till_done()
    assert len(hass.config_entries.flow.async_progress()) == 1

    # Check that we can start a reauth flow for a different entry
    entry2.async_start_reauth(hass, {"extra_context": "some_extra_context"})
    await hass.async_block_till_done()
    assert len(hass.config_entries.flow.async_progress()) == 2

    # Abort all existing flows
    for flow in hass.config_entries.flow.async_progress():
        hass.config_entries.flow.async_abort(flow["flow_id"])
    await hass.async_block_till_done()

    # Check that we can't start duplicate reauth flows
    # without blocking between flows
    entry.async_start_reauth(hass, {"extra_context": "some_extra_context"})
    entry.async_start_reauth(hass, {"extra_context": "some_extra_context"})
    entry.async_start_reauth(hass, {"extra_context": "some_extra_context"})
    entry.async_start_reauth(hass, {"extra_context": "some_extra_context"})
    await hass.async_block_till_done()
    assert len(hass.config_entries.flow.async_progress()) == 1


@pytest.mark.parametrize(
    "source", [config_entries.SOURCE_REAUTH, config_entries.SOURCE_RECONFIGURE]
)
async def test_reauth_reconfigure_missing_entry(
    hass: HomeAssistant,
    manager: config_entries.ConfigEntries,
    source: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the async_reauth_helper."""
    entry = MockConfigEntry(title="test_title", domain="test")
    entry.add_to_hass(hass)

    mock_setup_entry = AsyncMock(return_value=True)
    mock_integration(hass, MockModule("test", async_setup_entry=mock_setup_entry))
    mock_platform(hass, "test.config_flow", None)

    await manager.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(
        RuntimeError,
        match=f"Detected code that initialises a {source} flow without a link "
        "to the config entry. Please report this issue",
    ):
        await manager.flow.async_init("test", context={"source": source})
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 0


@pytest.mark.usefixtures("mock_integration_frame")
@pytest.mark.parametrize(
    "source", [config_entries.SOURCE_REAUTH, config_entries.SOURCE_RECONFIGURE]
)
async def test_reauth_reconfigure_missing_entry_component(
    hass: HomeAssistant,
    manager: config_entries.ConfigEntries,
    source: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the async_reauth_helper."""
    entry = MockConfigEntry(title="test_title", domain="test")
    entry.add_to_hass(hass)

    mock_setup_entry = AsyncMock(return_value=True)
    mock_integration(hass, MockModule("test", async_setup_entry=mock_setup_entry))
    mock_platform(hass, "test.config_flow", None)

    await manager.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with patch.object(frame, "_REPORTED_INTEGRATIONS", set()):
        await manager.flow.async_init("test", context={"source": source})
        await hass.async_block_till_done()

    # Flow still created, but deprecation logged
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == source

    assert (
        f"Detected that integration 'hue' initialises a {source} flow"
        " without a link to the config entry at homeassistant/components" in caplog.text
    )


async def test_reconfigure(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test the async_reconfigure_helper."""
    entry = MockConfigEntry(title="test_title", domain="test")
    entry.add_to_hass(hass)
    entry2 = MockConfigEntry(title="test_title", domain="test")
    entry2.add_to_hass(hass)

    mock_setup_entry = AsyncMock(return_value=True)
    mock_integration(hass, MockModule("test", async_setup_entry=mock_setup_entry))
    mock_platform(hass, "test.config_flow", None)

    await manager.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    def _async_start_reconfigure(config_entry: MockConfigEntry) -> None:
        hass.async_create_task(
            manager.flow.async_init(
                config_entry.domain,
                context={
                    "source": config_entries.SOURCE_RECONFIGURE,
                    "entry_id": config_entry.entry_id,
                },
            ),
            f"config entry reconfigure {config_entry.title} "
            f"{config_entry.domain} {config_entry.entry_id}",
        )

    _async_start_reconfigure(entry)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["entry_id"] == entry.entry_id
    assert flows[0]["context"]["source"] == config_entries.SOURCE_RECONFIGURE

    assert entry.entry_id != entry2.entry_id

    # Check that we can start duplicate reconfigure flows
    # (may need revisiting)
    _async_start_reconfigure(entry)
    await hass.async_block_till_done()
    assert len(hass.config_entries.flow.async_progress()) == 2

    # Check that we can start a reconfigure flow for a different entry
    _async_start_reconfigure(entry2)
    await hass.async_block_till_done()
    assert len(hass.config_entries.flow.async_progress()) == 3

    # Abort all existing flows
    for flow in hass.config_entries.flow.async_progress():
        hass.config_entries.flow.async_abort(flow["flow_id"])
    await hass.async_block_till_done()

    # Check that we can start duplicate reconfigure flows
    # without blocking between flows
    # (may need revisiting)
    _async_start_reconfigure(entry)
    _async_start_reconfigure(entry)
    _async_start_reconfigure(entry)
    _async_start_reconfigure(entry)
    await hass.async_block_till_done()
    assert len(hass.config_entries.flow.async_progress()) == 4

    # Abort all existing flows
    for flow in hass.config_entries.flow.async_progress():
        hass.config_entries.flow.async_abort(flow["flow_id"])
    await hass.async_block_till_done()

    # Check that we can start reconfigure flows with active reauth flow
    # (may need revisiting)
    entry.async_start_reauth(hass, {"extra_context": "some_extra_context"})
    await hass.async_block_till_done()
    assert len(hass.config_entries.flow.async_progress()) == 1
    _async_start_reconfigure(entry)
    await hass.async_block_till_done()
    assert len(hass.config_entries.flow.async_progress()) == 2

    # Abort all existing flows
    for flow in hass.config_entries.flow.async_progress():
        hass.config_entries.flow.async_abort(flow["flow_id"])
    await hass.async_block_till_done()

    # Check that we can't start reauth flows with active reconfigure flow
    _async_start_reconfigure(entry)
    await hass.async_block_till_done()
    assert len(hass.config_entries.flow.async_progress()) == 1
    entry.async_start_reauth(hass, {"extra_context": "some_extra_context"})
    await hass.async_block_till_done()
    assert len(hass.config_entries.flow.async_progress()) == 1


async def test_get_active_flows(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test the async_get_active_flows helper."""
    entry = MockConfigEntry(title="test_title", domain="test")
    entry.add_to_hass(hass)
    mock_setup_entry = AsyncMock(return_value=True)
    mock_integration(hass, MockModule("test", async_setup_entry=mock_setup_entry))
    mock_platform(hass, "test.config_flow", None)

    await manager.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    flow = hass.config_entries.flow
    with patch.object(flow, "async_init", wraps=flow.async_init):
        entry.async_start_reauth(
            hass,
            context={"extra_context": "some_extra_context"},
            data={"extra_data": 1234},
        )
        await hass.async_block_till_done()

    # Check that there's an active reauth flow:
    active_reauth_flow = next(
        iter(entry.async_get_active_flows(hass, {config_entries.SOURCE_REAUTH})), None
    )
    assert active_reauth_flow is not None

    # Check that there isn't any other flow (in this case, a user flow):
    active_user_flow = next(
        iter(entry.async_get_active_flows(hass, {config_entries.SOURCE_USER})), None
    )
    assert active_user_flow is None


async def test_async_wait_component_dynamic(hass: HomeAssistant) -> None:
    """Test async_wait_component for a config entry which is dynamically loaded."""
    entry = MockConfigEntry(title="test_title", domain="test")

    mock_setup_entry = AsyncMock(return_value=True)
    mock_integration(hass, MockModule("test", async_setup_entry=mock_setup_entry))
    mock_platform(hass, "test.config_flow", None)

    entry.add_to_hass(hass)

    # The config entry is not loaded, and is also not scheduled to load
    assert await hass.config_entries.async_wait_component(entry) is False

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # The config entry is loaded
    assert await hass.config_entries.async_wait_component(entry) is True


async def test_async_wait_component_startup(hass: HomeAssistant) -> None:
    """Test async_wait_component for a config entry which is loaded at startup."""
    entry = MockConfigEntry(title="test_title", domain="test")

    setup_stall = asyncio.Event()
    setup_started = asyncio.Event()

    async def mock_setup(hass: HomeAssistant, _) -> bool:
        setup_started.set()
        await setup_stall.wait()
        return True

    mock_setup_entry = AsyncMock(return_value=True)
    mock_integration(
        hass,
        MockModule("test", async_setup=mock_setup, async_setup_entry=mock_setup_entry),
    )
    mock_platform(hass, "test.config_flow", None)

    entry.add_to_hass(hass)

    # The config entry is not loaded, and is also not scheduled to load
    assert await hass.config_entries.async_wait_component(entry) is False

    # Mark the component as scheduled to be loaded
    async_set_domains_to_be_loaded(hass, {"test"})

    # Start loading the component, including its config entries
    hass.async_create_task(async_setup_component(hass, "test", {}))
    await setup_started.wait()

    # The component is not yet loaded
    assert "test" not in hass.config.components

    # Allow setup to proceed
    setup_stall.set()

    # The component is scheduled to load, this will block until the config entry is loaded
    assert await hass.config_entries.async_wait_component(entry) is True

    # The component has been loaded
    assert "test" in hass.config.components


@pytest.mark.parametrize(
    "integration_frame_path",
    ["homeassistant/components/my_integration", "homeassistant.core"],
)
@pytest.mark.usefixtures("hass", "mock_integration_frame")
async def test_options_flow_with_config_entry_core() -> None:
    """Test that OptionsFlowWithConfigEntry cannot be used in core."""
    entry = MockConfigEntry(
        domain="hue",
        data={"first": True},
        options={"sub_dict": {"1": "one"}, "sub_list": ["one"]},
    )

    with pytest.raises(RuntimeError, match="inherits from OptionsFlowWithConfigEntry"):
        _ = config_entries.OptionsFlowWithConfigEntry(entry)


@pytest.mark.parametrize("integration_frame_path", ["custom_components/my_integration"])
@pytest.mark.usefixtures("hass", "mock_integration_frame")
async def test_options_flow_with_config_entry(caplog: pytest.LogCaptureFixture) -> None:
    """Test that OptionsFlowWithConfigEntry doesn't mutate entry options."""
    entry = MockConfigEntry(
        domain="hue",
        data={"first": True},
        options={"sub_dict": {"1": "one"}, "sub_list": ["one"]},
    )

    options_flow = config_entries.OptionsFlowWithConfigEntry(entry)
    assert caplog.text == ""  # No deprecation warning for custom components

    # Ensure available at startup
    assert options_flow.config_entry is entry
    assert options_flow.options == entry.options

    options_flow.options["sub_dict"]["2"] = "two"
    options_flow.options["sub_list"].append("two")

    # Ensure it does not mutate the entry options
    assert options_flow.options == {
        "sub_dict": {"1": "one", "2": "two"},
        "sub_list": ["one", "two"],
    }
    assert entry.options == {"sub_dict": {"1": "one"}, "sub_list": ["one"]}


async def test_initializing_flows_canceled_on_shutdown(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test that initializing flows are canceled on shutdown."""

    class MockFlowHandler(config_entries.ConfigFlow):
        """Define a mock flow handler."""

        VERSION = 1

        async def async_step_reauth(self, data):
            """Mock Reauth."""
            await asyncio.sleep(1)

    mock_integration(hass, MockModule("test"))
    mock_platform(hass, "test.config_flow", None)

    with patch.dict(
        config_entries.HANDLERS, {"comp": MockFlowHandler, "test": MockFlowHandler}
    ):
        task = asyncio.create_task(
            manager.flow.async_init(
                "test", context={"source": "reauth", "entry_id": "abc"}
            )
        )
        await hass.async_block_till_done()
        manager.flow.async_shutdown()

        with pytest.raises(asyncio.exceptions.CancelledError):
            await task


async def test_task_tracking(hass: HomeAssistant) -> None:
    """Test task tracking for a config entry."""
    entry = MockConfigEntry(title="test_title", domain="test")

    event = asyncio.Event()
    results = []

    async def test_task() -> None:
        try:
            await event.wait()
            results.append("normal")
        except asyncio.CancelledError:
            results.append("background")
            raise

    async def test_unload() -> None:
        await event.wait()
        results.append("on_unload")

    entry.async_on_unload(test_unload)
    entry.async_create_task(hass, test_task())
    entry.async_create_background_task(
        hass, test_task(), "background-task-name", eager_start=True
    )
    entry.async_create_background_task(
        hass, test_task(), "background-task-name", eager_start=False
    )
    await asyncio.sleep(0)
    hass.loop.call_soon(event.set)
    await entry._async_process_on_unload(hass)
    assert results == [
        "background",
        "background",
        "normal",
        "on_unload",
    ]


async def test_preview_supported(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test preview support."""

    preview_calls = []

    class MockFlowHandler(config_entries.ConfigFlow):
        """Define a mock flow handler."""

        VERSION = 1

        async def async_step_test1(self, data):
            """Mock Reauth."""
            return self.async_show_form(step_id="next")

        async def async_step_test2(self, data):
            """Mock Reauth."""
            return self.async_show_form(step_id="next", preview="test")

        async def async_step_next(self, user_input=None):
            raise NotImplementedError

        @staticmethod
        async def async_setup_preview(hass: HomeAssistant) -> None:
            """Set up preview."""
            preview_calls.append(None)

    mock_integration(hass, MockModule("test"))
    mock_platform(hass, "test.config_flow", None)

    assert len(preview_calls) == 0

    with patch.dict(
        config_entries.HANDLERS, {"comp": MockFlowHandler, "test": MockFlowHandler}
    ):
        result = await manager.flow.async_init("test", context={"source": "test1"})

        assert len(preview_calls) == 0
        assert result["preview"] is None

        result = await manager.flow.async_init("test", context={"source": "test2"})

        assert len(preview_calls) == 1
        assert result["preview"] == "test"


async def test_preview_not_supported(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test preview support."""

    class MockFlowHandler(config_entries.ConfigFlow):
        """Define a mock flow handler."""

        VERSION = 1

        async def async_step_user(self, user_input):
            """Mock Reauth."""
            return self.async_show_form(step_id="user_confirm")

        async def async_step_user_confirm(self, user_input=None):
            raise NotImplementedError

    mock_integration(hass, MockModule("test"))
    mock_platform(hass, "test.config_flow", None)

    with patch.dict(
        config_entries.HANDLERS, {"comp": MockFlowHandler, "test": MockFlowHandler}
    ):
        result = await manager.flow.async_init(
            "test", context={"source": config_entries.SOURCE_USER}
        )

    assert result["preview"] is None


def test_raise_trying_to_add_same_config_entry_twice(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test we log an error if trying to add same config entry twice."""
    entry = MockConfigEntry(domain="test")
    entry.add_to_hass(hass)
    entry.add_to_hass(hass)
    assert f"An entry with the id {entry.entry_id} already exists" in caplog.text


@pytest.mark.parametrize(
    (
        "kwargs",
        "expected_title",
        "expected_unique_id",
        "expected_data",
        "expected_options",
        "calls_entry_load_unload",
        "raises",
    ),
    [
        (
            {
                "unique_id": "5678",
                "title": "Updated title",
                "data": {"vendor": "data2"},
                "options": {"vendor": "options2"},
            },
            "Updated title",
            "5678",
            {"vendor": "data2"},
            {"vendor": "options2"},
            (2, 1),
            None,
        ),
        (
            {
                "unique_id": "1234",
                "title": "Test",
                "data": {"vendor": "data"},
                "options": {"vendor": "options"},
            },
            "Test",
            "1234",
            {"vendor": "data"},
            {"vendor": "options"},
            (2, 1),
            None,
        ),
        (
            {
                "unique_id": "5678",
                "title": "Updated title",
                "data": {"vendor": "data2"},
                "options": {"vendor": "options2"},
                "reload_even_if_entry_is_unchanged": True,
            },
            "Updated title",
            "5678",
            {"vendor": "data2"},
            {"vendor": "options2"},
            (2, 1),
            None,
        ),
        (
            {
                "unique_id": "1234",
                "title": "Test",
                "data": {"vendor": "data"},
                "options": {"vendor": "options"},
                "reload_even_if_entry_is_unchanged": False,
            },
            "Test",
            "1234",
            {"vendor": "data"},
            {"vendor": "options"},
            (1, 0),
            None,
        ),
        (
            {},
            "Test",
            "1234",
            {"vendor": "data"},
            {"vendor": "options"},
            (2, 1),
            None,
        ),
        (
            {"data": {"buyer": "me"}, "options": {}},
            "Test",
            "1234",
            {"buyer": "me"},
            {},
            (2, 1),
            None,
        ),
        (
            {"data_updates": {"buyer": "me"}},
            "Test",
            "1234",
            {"vendor": "data", "buyer": "me"},
            {"vendor": "options"},
            (2, 1),
            None,
        ),
        (
            {
                "unique_id": "5678",
                "title": "Updated title",
                "data": {"vendor": "data2"},
                "options": {"vendor": "options2"},
                "data_updates": {"buyer": "me"},
            },
            "Test",
            "1234",
            {"vendor": "data"},
            {"vendor": "options"},
            (1, 0),
            ValueError,
        ),
    ],
    ids=[
        "changed_entry_default",
        "unchanged_entry_default",
        "changed_entry_explicit_reload",
        "unchanged_entry_no_reload",
        "no_kwargs",
        "replace_data",
        "update_data",
        "update_and_data_raises",
    ],
)
@pytest.mark.parametrize(
    ("source", "reason"),
    [
        (config_entries.SOURCE_REAUTH, "reauth_successful"),
        (config_entries.SOURCE_RECONFIGURE, "reconfigure_successful"),
    ],
)
async def test_update_entry_and_reload(
    hass: HomeAssistant,
    source: str,
    reason: str,
    expected_title: str,
    expected_unique_id: str,
    expected_data: dict[str, Any],
    expected_options: dict[str, Any],
    kwargs: dict[str, Any],
    calls_entry_load_unload: tuple[int, int],
    raises: type[Exception] | None,
) -> None:
    """Test updating an entry and reloading."""
    entry = MockConfigEntry(
        domain="comp",
        unique_id="1234",
        title="Test",
        data={"vendor": "data"},
        options={"vendor": "options"},
    )
    entry.add_to_hass(hass)

    comp = MockModule(
        "comp",
        async_setup_entry=AsyncMock(return_value=True),
        async_unload_entry=AsyncMock(return_value=True),
    )
    mock_integration(hass, comp)
    mock_platform(hass, "comp.config_flow", None)

    await hass.config_entries.async_setup(entry.entry_id)

    class MockFlowHandler(config_entries.ConfigFlow):
        """Define a mock flow handler."""

        VERSION = 1

        async def async_step_reauth(self, data):
            """Mock Reauth."""
            return self.async_update_reload_and_abort(entry, **kwargs)

        async def async_step_reconfigure(self, data):
            """Mock Reconfigure."""
            return self.async_update_reload_and_abort(entry, **kwargs)

    err: Exception
    with mock_config_flow("comp", MockFlowHandler):
        try:
            if source == config_entries.SOURCE_REAUTH:
                result = await entry.start_reauth_flow(hass)
            elif source == config_entries.SOURCE_RECONFIGURE:
                result = await entry.start_reconfigure_flow(hass)
        except Exception as ex:  # noqa: BLE001
            err = ex

    await hass.async_block_till_done()

    assert entry.title == expected_title
    assert entry.unique_id == expected_unique_id
    assert entry.data == expected_data
    assert entry.options == expected_options
    assert entry.state == config_entries.ConfigEntryState.LOADED
    if raises:
        assert isinstance(err, raises)
    else:
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == reason
    # Assert entry was reloaded
    assert len(comp.async_setup_entry.mock_calls) == calls_entry_load_unload[0]
    assert len(comp.async_unload_entry.mock_calls) == calls_entry_load_unload[1]


@pytest.mark.parametrize(
    (
        "kwargs",
        "expected_title",
        "expected_unique_id",
        "expected_data",
        "raises",
    ),
    [
        (
            {
                "unique_id": "5678",
                "title": "Updated title",
                "data": {"vendor": "data2"},
            },
            "Updated title",
            "5678",
            {"vendor": "data2"},
            None,
        ),
        (
            {
                "unique_id": "1234",
                "title": "Test",
                "data": {"vendor": "data"},
            },
            "Test",
            "1234",
            {"vendor": "data"},
            None,
        ),
        (
            {},
            "Test",
            "1234",
            {"vendor": "data"},
            None,
        ),
        (
            {
                "data": {"buyer": "me"},
            },
            "Test",
            "1234",
            {"buyer": "me"},
            None,
        ),
        (
            {"data_updates": {"buyer": "me"}},
            "Test",
            "1234",
            {"vendor": "data", "buyer": "me"},
            None,
        ),
        (
            {
                "unique_id": "5678",
                "title": "Updated title",
                "data": {"vendor": "data2"},
                "data_updates": {"buyer": "me"},
            },
            "Test",
            "1234",
            {"vendor": "data"},
            ValueError,
        ),
    ],
    ids=[
        "changed_entry_default",
        "unchanged_entry_default",
        "no_kwargs",
        "replace_data",
        "update_data",
        "update_and_data_raises",
    ],
)
async def test_update_subentry_and_abort(
    hass: HomeAssistant,
    expected_title: str,
    expected_unique_id: str,
    expected_data: dict[str, Any],
    kwargs: dict[str, Any],
    raises: type[Exception] | None,
) -> None:
    """Test updating an entry and reloading."""
    subentry_id = "blabla"
    entry = MockConfigEntry(
        domain="comp",
        unique_id="entry_unique_id",
        title="entry_title",
        data={},
        subentries_data=[
            config_entries.ConfigSubentryData(
                data={"vendor": "data"},
                subentry_id=subentry_id,
                subentry_type="test",
                unique_id="1234",
                title="Test",
            )
        ],
    )
    entry.add_to_hass(hass)
    subentry = entry.subentries[subentry_id]

    comp = MockModule("comp")
    mock_integration(hass, comp)
    mock_platform(hass, "comp.config_flow", None)

    class TestFlow(config_entries.ConfigFlow):
        class SubentryFlowHandler(config_entries.ConfigSubentryFlow):
            async def async_step_reconfigure(self, user_input=None):
                return self.async_update_and_abort(
                    self._get_entry(),
                    self._get_reconfigure_subentry(),
                    **kwargs,
                )

        @classmethod
        @callback
        def async_get_supported_subentry_types(
            cls, config_entry: config_entries.ConfigEntry
        ) -> dict[str, type[config_entries.ConfigSubentryFlow]]:
            return {"test": TestFlow.SubentryFlowHandler}

    err: Exception
    with mock_config_flow("comp", TestFlow):
        try:
            result = await entry.start_subentry_reconfigure_flow(
                hass, "test", subentry_id
            )
        except Exception as ex:  # noqa: BLE001
            err = ex

    await hass.async_block_till_done()

    subentry = entry.subentries[subentry_id]
    assert subentry.title == expected_title
    assert subentry.unique_id == expected_unique_id
    assert subentry.data == expected_data
    if raises:
        assert isinstance(err, raises)
    else:
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"


async def test_reconfigure_subentry_create_subentry(hass: HomeAssistant) -> None:
    """Test it's not allowed to create a subentry from a subentry reconfigure flow."""
    subentry_id = "blabla"
    entry = MockConfigEntry(
        domain="comp",
        unique_id="entry_unique_id",
        title="entry_title",
        data={},
        subentries_data=[
            config_entries.ConfigSubentryData(
                data={"vendor": "data"},
                subentry_id=subentry_id,
                subentry_type="test",
                unique_id="1234",
                title="Test",
            )
        ],
    )
    entry.add_to_hass(hass)

    comp = MockModule("comp")
    mock_integration(hass, comp)
    mock_platform(hass, "comp.config_flow", None)

    class TestFlow(config_entries.ConfigFlow):
        class SubentryFlowHandler(config_entries.ConfigSubentryFlow):
            async def async_step_reconfigure(self, user_input=None):
                return self.async_create_entry(title="New Subentry", data={})

        @classmethod
        @callback
        def async_get_supported_subentry_types(
            cls, config_entry: config_entries.ConfigEntry
        ) -> dict[str, type[config_entries.ConfigSubentryFlow]]:
            return {"test": TestFlow.SubentryFlowHandler}

    with (
        mock_config_flow("comp", TestFlow),
        pytest.raises(ValueError, match="Source is reconfigure, expected user"),
    ):
        await entry.start_subentry_reconfigure_flow(hass, "test", subentry_id)

    await hass.async_block_till_done()

    assert entry.subentries == {
        subentry_id: config_entries.ConfigSubentry(
            data={"vendor": "data"},
            subentry_id=subentry_id,
            subentry_type="test",
            title="Test",
            unique_id="1234",
        )
    }


@pytest.mark.parametrize("unique_id", [["blah", "bleh"], {"key": "value"}])
async def test_unhashable_unique_id_fails(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, unique_id: Any
) -> None:
    """Test the ConfigEntryItems user dict fails unhashable unique_id."""
    entries = config_entries.ConfigEntryItems(hass)
    entry = config_entries.ConfigEntry(
        data={},
        discovery_keys={},
        domain="test",
        entry_id="mock_id",
        minor_version=1,
        options={},
        source="test",
        subentries_data=(),
        title="title",
        unique_id=unique_id,
        version=1,
    )

    unique_id_string = re.escape(str(unique_id))
    with pytest.raises(
        HomeAssistantError,
        match=f"The entry unique id {unique_id_string} is not a string.",
    ):
        entries[entry.entry_id] = entry

    assert entry.entry_id not in entries

    with pytest.raises(
        HomeAssistantError,
        match=f"The entry unique id {unique_id_string} is not a string.",
    ):
        entries.get_entry_by_domain_and_unique_id("test", unique_id)


@pytest.mark.parametrize("unique_id", [["blah", "bleh"], {"key": "value"}])
async def test_unhashable_unique_id_fails_on_update(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, unique_id: Any
) -> None:
    """Test the ConfigEntryItems user dict fails non-hashable unique_id on update."""
    entries = config_entries.ConfigEntryItems(hass)
    entry = config_entries.ConfigEntry(
        data={},
        discovery_keys={},
        domain="test",
        entry_id="mock_id",
        minor_version=1,
        options={},
        source="test",
        subentries_data=(),
        title="title",
        unique_id="123",
        version=1,
    )

    entries[entry.entry_id] = entry
    assert entry.entry_id in entries

    unique_id_string = re.escape(str(unique_id))
    with pytest.raises(
        HomeAssistantError,
        match=f"The entry unique id {unique_id_string} is not a string.",
    ):
        entries.update_unique_id(entry, unique_id)


async def test_string_unique_id_no_warning(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the ConfigEntryItems user dict string unique id doesn't log warning."""
    entries = config_entries.ConfigEntryItems(hass)
    entry = config_entries.ConfigEntry(
        data={},
        discovery_keys={},
        domain="test",
        entry_id="mock_id",
        minor_version=1,
        options={},
        source="test",
        subentries_data=(),
        title="title",
        unique_id="123",
        version=1,
    )

    entries[entry.entry_id] = entry

    assert (
        "Config entry 'title' from integration test has an invalid unique_id"
    ) not in caplog.text

    assert entry.entry_id in entries
    assert entries[entry.entry_id] is entry
    assert entries.get_entry_by_domain_and_unique_id("test", "123") == entry
    del entries[entry.entry_id]
    assert not entries
    assert entries.get_entry_by_domain_and_unique_id("test", "123") is None


@pytest.mark.parametrize(
    ("unique_id", "type_name"),
    [
        (123, "int"),
        (2.3, "float"),
    ],
)
async def test_hashable_unique_id(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    unique_id: Any,
    type_name: str,
) -> None:
    """Test the ConfigEntryItems user dict handles hashable non string unique_id."""
    entries = config_entries.ConfigEntryItems(hass)
    entry = config_entries.ConfigEntry(
        data={},
        discovery_keys={},
        domain="test",
        entry_id="mock_id",
        minor_version=1,
        options={},
        source="test",
        subentries_data=(),
        title="title",
        unique_id=unique_id,
        version=1,
    )

    entries[entry.entry_id] = entry

    assert (
        "Config entry 'title' from integration test has an invalid unique_id"
        f" '{unique_id}' of type {type_name} when a string is expected"
    ) in caplog.text

    assert entry.entry_id in entries
    assert entries[entry.entry_id] is entry
    assert entries.get_entry_by_domain_and_unique_id("test", unique_id) == entry
    del entries[entry.entry_id]
    assert not entries
    assert entries.get_entry_by_domain_and_unique_id("test", unique_id) is None


async def test_no_unique_id_no_warning(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the ConfigEntryItems user dict don't log warning with no unique id."""
    entries = config_entries.ConfigEntryItems(hass)
    entry = config_entries.ConfigEntry(
        data={},
        discovery_keys={},
        domain="test",
        entry_id="mock_id",
        minor_version=1,
        options={},
        source="test",
        subentries_data=(),
        title="title",
        unique_id=None,
        version=1,
    )

    entries[entry.entry_id] = entry

    assert (
        "Config entry 'title' from integration test has an invalid unique_id"
    ) not in caplog.text

    assert entry.entry_id in entries
    assert entries[entry.entry_id] is entry


@pytest.mark.parametrize(
    ("context", "user_input", "expected_result"),
    [
        (
            {"source": config_entries.SOURCE_IGNORE},
            {"unique_id": "blah", "title": "blah"},
            {"type": data_entry_flow.FlowResultType.CREATE_ENTRY},
        ),
        (
            {"source": config_entries.SOURCE_REAUTH, "entry_id": "1234"},
            None,
            {"type": data_entry_flow.FlowResultType.FORM, "step_id": "reauth_confirm"},
        ),
        (
            {"source": config_entries.SOURCE_RECONFIGURE, "entry_id": "1234"},
            None,
            {"type": data_entry_flow.FlowResultType.FORM, "step_id": "reauth_confirm"},
        ),
        (
            {"source": config_entries.SOURCE_USER},
            None,
            {
                "type": data_entry_flow.FlowResultType.ABORT,
                "reason": "single_instance_allowed",
                "translation_domain": HOMEASSISTANT_DOMAIN,
            },
        ),
    ],
)
async def test_starting_config_flow_on_single_config_entry(
    hass: HomeAssistant,
    manager: config_entries.ConfigEntries,
    context: dict[str, Any],
    user_input: dict,
    expected_result: dict,
) -> None:
    """Test starting a config flow for a single config entry integration.

    In this test, the integration has one ignored flow and one entry added by user.
    """
    integration = loader.Integration(
        hass,
        "components.comp",
        None,
        {
            "name": "Comp",
            "dependencies": [],
            "requirements": [],
            "domain": "comp",
            "single_config_entry": True,
        },
    )
    entry = MockConfigEntry(
        domain="comp",
        unique_id="1234",
        entry_id="1234",
        title="Test",
        data={"vendor": "data"},
        options={"vendor": "options"},
    )
    entry.add_to_hass(hass)
    ignored_entry = MockConfigEntry(
        domain="comp",
        unique_id="2345",
        entry_id="2345",
        title="Test",
        data={"vendor": "data"},
        options={"vendor": "options"},
        source=config_entries.SOURCE_IGNORE,
    )
    ignored_entry.add_to_hass(hass)

    mock_platform(hass, "comp.config_flow", None)

    with patch(
        "homeassistant.loader.async_get_integration",
        return_value=integration,
    ):
        result = await hass.config_entries.flow.async_init(
            "comp", context=context, data=user_input
        )

    for key, value in expected_result.items():
        assert result[key] == value


@pytest.mark.parametrize(
    ("context", "user_input", "expected_result"),
    [
        (
            {"source": config_entries.SOURCE_IGNORE},
            {"unique_id": "blah", "title": "blah"},
            {"type": data_entry_flow.FlowResultType.CREATE_ENTRY},
        ),
        (
            {"source": config_entries.SOURCE_REAUTH, "entry_id": "2345"},
            None,
            {"type": data_entry_flow.FlowResultType.FORM, "step_id": "reauth_confirm"},
        ),
        (
            {"source": config_entries.SOURCE_RECONFIGURE, "entry_id": "2345"},
            None,
            {"type": data_entry_flow.FlowResultType.FORM, "step_id": "reauth_confirm"},
        ),
        (
            {"source": config_entries.SOURCE_USER},
            None,
            {"type": data_entry_flow.FlowResultType.ABORT, "reason": "not_implemented"},
        ),
        (
            {"source": config_entries.SOURCE_ZEROCONF},
            None,
            {
                "type": data_entry_flow.FlowResultType.ABORT,
                "reason": "single_instance_allowed",
            },
        ),
    ],
)
async def test_starting_config_flow_on_single_config_entry_2(
    hass: HomeAssistant,
    manager: config_entries.ConfigEntries,
    context: dict[str, Any],
    user_input: dict,
    expected_result: dict,
) -> None:
    """Test starting a config flow for a single config entry integration.

    In this test, the integration has one ignored flow but no entry added by user.
    """
    integration = loader.Integration(
        hass,
        "components.comp",
        None,
        {
            "name": "Comp",
            "dependencies": [],
            "requirements": [],
            "domain": "comp",
            "single_config_entry": True,
        },
    )
    ignored_entry = MockConfigEntry(
        domain="comp",
        unique_id="2345",
        entry_id="2345",
        title="Test",
        data={"vendor": "data"},
        options={"vendor": "options"},
        source=config_entries.SOURCE_IGNORE,
    )
    ignored_entry.add_to_hass(hass)

    mock_platform(hass, "comp.config_flow", None)

    with patch(
        "homeassistant.loader.async_get_integration",
        return_value=integration,
    ):
        result = await hass.config_entries.flow.async_init(
            "comp", context=context, data=user_input
        )

    for key, value in expected_result.items():
        assert result[key] == value


async def test_avoid_adding_second_config_entry_on_single_config_entry(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test that we cannot add a second entry for a single config entry integration."""

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 1

        async def async_step_user(self, user_input=None):
            """Test user step."""
            if user_input is None:
                return self.async_show_form(step_id="user")

            return self.async_create_entry(title="yo", data={})

    integration = loader.Integration(
        hass,
        "components.comp",
        None,
        {
            "name": "Comp",
            "dependencies": [],
            "requirements": [],
            "domain": "comp",
            "single_config_entry": True,
        },
    )
    mock_integration(hass, MockModule("comp"))
    mock_platform(hass, "comp.config_flow", None)

    with (
        patch(
            "homeassistant.loader.async_get_integration",
            return_value=integration,
        ),
        mock_config_flow("comp", TestFlow),
    ):
        # Start a flow
        result = await manager.flow.async_init(
            "comp", context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM

        # Add a config entry
        entry = MockConfigEntry(
            domain="comp",
            unique_id="1234",
            title="Test",
            data={"vendor": "data"},
            options={"vendor": "options"},
        )
        entry.add_to_hass(hass)

        # Finish the in progress flow
        result = await manager.flow.async_configure(
            result["flow_id"], user_input={"host": "127.0.0.1"}
        )
        assert result["type"] == data_entry_flow.FlowResultType.ABORT
        assert result["reason"] == "single_instance_allowed"
        assert result["translation_domain"] == HOMEASSISTANT_DOMAIN


@pytest.mark.parametrize(
    ("flow_1_unique_id", "flow_2_unique_id"),
    [
        (None, None),
        ("very_unique", "very_unique"),
        (None, config_entries.DEFAULT_DISCOVERY_UNIQUE_ID),
        ("very_unique", config_entries.DEFAULT_DISCOVERY_UNIQUE_ID),
    ],
)
async def test_in_progress_get_canceled_when_entry_is_created(
    hass: HomeAssistant,
    manager: config_entries.ConfigEntries,
    flow_1_unique_id: str | None,
    flow_2_unique_id: str | None,
) -> None:
    """Test that we abort all in progress flows when a new entry is created on a single instance only integration."""
    integration = loader.Integration(
        hass,
        "components.comp",
        None,
        {
            "name": "Comp",
            "dependencies": [],
            "requirements": [],
            "domain": "comp",
            "single_config_entry": True,
        },
    )
    mock_integration(hass, MockModule("comp"))
    mock_platform(hass, "comp.config_flow", None)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 1

        async def async_step_user(self, user_input=None):
            """Test user step."""
            if user_input is not None:
                return self.async_create_entry(title="Test Title", data=user_input)

            await self.async_set_unique_id(flow_1_unique_id, raise_on_progress=False)
            return self.async_show_form(step_id="user")

        async def async_step_zeroconfg(self, user_input=None):
            """Test user step."""
            if user_input is not None:
                return self.async_create_entry(title="Test Title", data=user_input)

            await self.async_set_unique_id(flow_2_unique_id, raise_on_progress=False)
            return self.async_show_form(step_id="user")

    with (
        mock_config_flow("comp", TestFlow),
        patch(
            "homeassistant.loader.async_get_integration",
            return_value=integration,
        ),
    ):
        # Create one to be in progress
        result = await manager.flow.async_init(
            "comp", context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM

        # Will be canceled
        result2 = await manager.flow.async_init(
            "comp", context={"source": config_entries.SOURCE_USER}
        )
        assert result2["type"] == data_entry_flow.FlowResultType.FORM

        result = await manager.flow.async_configure(
            result["flow_id"], user_input={"host": "127.0.0.1"}
        )
        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY

    assert len(manager.flow.async_progress()) == 0
    assert len(manager.async_entries()) == 1


async def test_directly_mutating_blocked(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test directly mutating a ConfigEntry is blocked."""
    entry = MockConfigEntry(domain="test")
    entry.add_to_hass(hass)

    with pytest.raises(AttributeError, match="entry_id cannot be changed"):
        entry.entry_id = "new_entry_id"

    with pytest.raises(AttributeError, match="domain cannot be changed"):
        entry.domain = "new_domain"

    with pytest.raises(AttributeError, match="state cannot be changed"):
        entry.state = config_entries.ConfigEntryState.FAILED_UNLOAD

    with pytest.raises(AttributeError, match="reason cannot be changed"):
        entry.reason = "new_reason"

    with pytest.raises(
        AttributeError,
        match="unique_id cannot be changed directly, use async_update_entry instead",
    ):
        entry.unique_id = "new_id"


@pytest.mark.parametrize(
    "field",
    [
        "data",
        "options",
        "title",
        "pref_disable_new_entities",
        "pref_disable_polling",
        "minor_version",
        "version",
    ],
)
async def test_report_direct_mutation_of_config_entry(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, field: str
) -> None:
    """Test directly mutating a ConfigEntry is reported."""
    entry = MockConfigEntry(domain="test")
    entry.add_to_hass(hass)

    with pytest.raises(AttributeError):
        setattr(entry, field, "new_value")


async def test_updating_non_added_entry_raises(hass: HomeAssistant) -> None:
    """Test updating a non added entry raises UnknownEntry."""
    entry = MockConfigEntry(domain="test")

    with pytest.raises(config_entries.UnknownEntry, match=entry.entry_id):
        hass.config_entries.async_update_entry(entry, unique_id="new_id")


async def test_updating_non_added_subentry_raises(hass: HomeAssistant) -> None:
    """Test updating a non added entry raises UnknownEntry."""
    entry = MockConfigEntry(domain="test")
    subentry = config_entries.ConfigSubentry(
        data={},
        subentry_type="test",
        title="Mock title",
        unique_id="unique",
    )

    with pytest.raises(config_entries.UnknownEntry, match=entry.entry_id):
        hass.config_entries.async_update_subentry(entry, subentry, unique_id="new_id")
    entry.add_to_hass(hass)
    with pytest.raises(config_entries.UnknownSubEntry, match=subentry.subentry_id):
        hass.config_entries.async_update_subentry(entry, subentry, unique_id="new_id")


async def test_reload_during_setup(hass: HomeAssistant) -> None:
    """Test reload during setup waits."""
    entry = MockConfigEntry(domain="comp", data={"value": "initial"})
    entry.add_to_hass(hass)

    setup_start_future = hass.loop.create_future()
    setup_finish_future = hass.loop.create_future()
    in_setup = False
    setup_calls = 0

    async def mock_async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
        """Mock setting up an entry."""
        nonlocal in_setup
        nonlocal setup_calls
        setup_calls += 1
        assert not in_setup
        in_setup = True
        setup_start_future.set_result(None)
        await setup_finish_future
        in_setup = False
        return True

    mock_integration(
        hass,
        MockModule(
            "comp",
            async_setup_entry=mock_async_setup_entry,
            async_unload_entry=AsyncMock(return_value=True),
        ),
    )
    mock_platform(hass, "comp.config_flow", None)

    setup_task = hass.async_create_task(async_setup_component(hass, "comp", {}))

    await setup_start_future  # ensure we are in the setup
    reload_task = hass.async_create_task(
        hass.config_entries.async_reload(entry.entry_id)
    )
    await asyncio.sleep(0)
    setup_finish_future.set_result(None)
    await setup_task
    await reload_task
    assert setup_calls == 2


@pytest.mark.parametrize(
    "exc",
    [
        ConfigEntryError,
        ConfigEntryAuthFailed,
        ConfigEntryNotReady,
    ],
)
async def test_raise_wrong_exception_in_forwarded_platform(
    hass: HomeAssistant,
    manager: config_entries.ConfigEntries,
    exc: Exception,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that we can remove an entry."""

    async def mock_setup_entry(
        hass: HomeAssistant, entry: config_entries.ConfigEntry
    ) -> bool:
        """Mock setting up entry."""
        await hass.config_entries.async_forward_entry_setups(entry, ["light"])
        return True

    async def mock_unload_entry(
        hass: HomeAssistant, entry: config_entries.ConfigEntry
    ) -> bool:
        """Mock unloading an entry."""
        result = await hass.config_entries.async_unload_platforms(entry, ["light"])
        assert result
        return result

    mock_remove_entry = AsyncMock(return_value=None)

    async def mock_setup_entry_platform(
        hass: HomeAssistant,
        entry: config_entries.ConfigEntry,
        async_add_entities: AddConfigEntryEntitiesCallback,
    ) -> None:
        """Mock setting up platform."""
        raise exc

    mock_integration(
        hass,
        MockModule(
            "test",
            async_setup_entry=mock_setup_entry,
            async_unload_entry=mock_unload_entry,
            async_remove_entry=mock_remove_entry,
        ),
    )
    mock_platform(
        hass, "test.light", MockPlatform(async_setup_entry=mock_setup_entry_platform)
    )
    mock_platform(hass, "test.config_flow", None)

    entry = MockConfigEntry(domain="test", entry_id="test2")
    entry.add_to_manager(manager)

    # Setup entry
    await manager.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    exc_type_name = type(exc()).__name__
    assert (
        f"test raises exception {exc_type_name} in forwarded platform light;"
        in caplog.text
    )
    assert (
        f"Instead raise {exc_type_name} before calling async_forward_entry_setups"
        in caplog.text
    )


async def test_config_entry_unloaded_during_platform_setups(
    hass: HomeAssistant,
    manager: config_entries.ConfigEntries,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test async_forward_entry_setups not being awaited."""
    task = None

    async def mock_setup_entry(
        hass: HomeAssistant, entry: config_entries.ConfigEntry
    ) -> bool:
        """Mock setting up entry."""

        # Call async_forward_entry_setups in a non-tracked task
        # so we can unload the config entry during the setup
        def _late_setup():
            nonlocal task
            task = asyncio.create_task(
                hass.config_entries.async_forward_entry_setups(entry, ["light"])
            )

        hass.loop.call_soon(_late_setup)
        return True

    async def mock_unload_entry(
        hass: HomeAssistant, entry: config_entries.ConfigEntry
    ) -> bool:
        """Mock unloading an entry."""
        result = await hass.config_entries.async_unload_platforms(entry, ["light"])
        assert result
        return result

    mock_remove_entry = AsyncMock(return_value=None)

    async def mock_setup_entry_platform(
        hass: HomeAssistant,
        entry: config_entries.ConfigEntry,
        async_add_entities: AddConfigEntryEntitiesCallback,
    ) -> None:
        """Mock setting up platform."""
        await asyncio.sleep(0)
        await asyncio.sleep(0)

    mock_integration(
        hass,
        MockModule(
            "test",
            async_setup_entry=mock_setup_entry,
            async_unload_entry=mock_unload_entry,
            async_remove_entry=mock_remove_entry,
        ),
    )
    mock_platform(
        hass, "test.light", MockPlatform(async_setup_entry=mock_setup_entry_platform)
    )
    mock_platform(hass, "test.config_flow", None)

    entry = MockConfigEntry(domain="test", entry_id="test2")
    entry.add_to_manager(manager)

    # Setup entry
    await manager.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await manager.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    del task

    assert (
        "OperationNotAllowed: The config entry 'Mock Title' (test) with "
        "entry_id 'test2' cannot forward setup for ['light'] because it is "
        "in state ConfigEntryState.NOT_LOADED, but needs to be in the "
        "ConfigEntryState.LOADED state"
    ) in caplog.text


async def test_non_awaited_async_forward_entry_setups(
    hass: HomeAssistant,
    manager: config_entries.ConfigEntries,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test async_forward_entry_setups not being awaited."""
    forward_event = asyncio.Event()
    task: asyncio.Task | None = None

    async def mock_setup_entry(
        hass: HomeAssistant, entry: config_entries.ConfigEntry
    ) -> bool:
        """Mock setting up entry."""
        # Call async_forward_entry_setups without awaiting it
        # This is not allowed and will raise a warning
        nonlocal task
        task = create_eager_task(
            hass.config_entries.async_forward_entry_setups(entry, ["light"])
        )
        return True

    async def mock_unload_entry(
        hass: HomeAssistant, entry: config_entries.ConfigEntry
    ) -> bool:
        """Mock unloading an entry."""
        result = await hass.config_entries.async_unload_platforms(entry, ["light"])
        assert result
        return result

    mock_remove_entry = AsyncMock(return_value=None)

    async def mock_setup_entry_platform(
        hass: HomeAssistant,
        entry: config_entries.ConfigEntry,
        async_add_entities: AddConfigEntryEntitiesCallback,
    ) -> None:
        """Mock setting up platform."""
        await forward_event.wait()

    mock_integration(
        hass,
        MockModule(
            "test",
            async_setup_entry=mock_setup_entry,
            async_unload_entry=mock_unload_entry,
            async_remove_entry=mock_remove_entry,
        ),
    )
    mock_platform(
        hass, "test.light", MockPlatform(async_setup_entry=mock_setup_entry_platform)
    )
    mock_platform(hass, "test.config_flow", None)

    entry = MockConfigEntry(domain="test", entry_id="test2")
    entry.add_to_manager(manager)

    # Setup entry
    await manager.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    forward_event.set()
    await hass.async_block_till_done()
    await task

    assert (
        "Detected code that calls async_forward_entry_setups for integration "
        "test with title: Mock Title and entry_id: test2, during setup without "
        "awaiting async_forward_entry_setups, which can cause the setup lock "
        "to be released before the setup is done. This will stop working in "
        "Home Assistant 2025.1, please report this issue"
    ) in caplog.text


async def test_non_awaited_async_forward_entry_setup(
    hass: HomeAssistant,
    manager: config_entries.ConfigEntries,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test async_forward_entry_setup not being awaited."""
    forward_event = asyncio.Event()
    task: asyncio.Task | None = None

    async def mock_setup_entry(
        hass: HomeAssistant, entry: config_entries.ConfigEntry
    ) -> bool:
        """Mock setting up entry."""
        # Call async_forward_entry_setup without awaiting it
        # This is not allowed and will raise a warning
        nonlocal task
        task = create_eager_task(
            hass.config_entries.async_forward_entry_setup(entry, "light")
        )
        return True

    async def mock_unload_entry(
        hass: HomeAssistant, entry: config_entries.ConfigEntry
    ) -> bool:
        """Mock unloading an entry."""
        result = await hass.config_entries.async_unload_platforms(entry, ["light"])
        assert result
        return result

    mock_remove_entry = AsyncMock(return_value=None)

    async def mock_setup_entry_platform(
        hass: HomeAssistant,
        entry: config_entries.ConfigEntry,
        async_add_entities: AddConfigEntryEntitiesCallback,
    ) -> None:
        """Mock setting up platform."""
        await forward_event.wait()

    mock_integration(
        hass,
        MockModule(
            "test",
            async_setup_entry=mock_setup_entry,
            async_unload_entry=mock_unload_entry,
            async_remove_entry=mock_remove_entry,
        ),
    )
    mock_platform(
        hass, "test.light", MockPlatform(async_setup_entry=mock_setup_entry_platform)
    )
    mock_platform(hass, "test.config_flow", None)

    entry = MockConfigEntry(domain="test", entry_id="test2")
    entry.add_to_manager(manager)

    # Setup entry
    await manager.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    forward_event.set()
    await hass.async_block_till_done()
    await task

    assert (
        "Detected code that calls async_forward_entry_setup for integration "
        "test with title: Mock Title and entry_id: test2, during setup without "
        "awaiting async_forward_entry_setup, which can cause the setup lock "
        "to be released before the setup is done. This will stop working in "
        "Home Assistant 2025.1, please report this issue"
    ) in caplog.text


async def test_config_entry_unloaded_during_platform_setup(
    hass: HomeAssistant,
    manager: config_entries.ConfigEntries,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test async_forward_entry_setup not being awaited."""
    task = None

    async def mock_setup_entry(
        hass: HomeAssistant, entry: config_entries.ConfigEntry
    ) -> bool:
        """Mock setting up entry."""

        # Call async_forward_entry_setup in a non-tracked task
        # so we can unload the config entry during the setup
        def _late_setup():
            nonlocal task
            task = asyncio.create_task(
                hass.config_entries.async_forward_entry_setup(entry, "light")
            )

        hass.loop.call_soon(_late_setup)
        return True

    async def mock_unload_entry(
        hass: HomeAssistant, entry: config_entries.ConfigEntry
    ) -> bool:
        """Mock unloading an entry."""
        result = await hass.config_entries.async_unload_platforms(entry, ["light"])
        assert result
        return result

    mock_remove_entry = AsyncMock(return_value=None)

    async def mock_setup_entry_platform(
        hass: HomeAssistant,
        entry: config_entries.ConfigEntry,
        async_add_entities: AddConfigEntryEntitiesCallback,
    ) -> None:
        """Mock setting up platform."""
        await asyncio.sleep(0)
        await asyncio.sleep(0)

    mock_integration(
        hass,
        MockModule(
            "test",
            async_setup_entry=mock_setup_entry,
            async_unload_entry=mock_unload_entry,
            async_remove_entry=mock_remove_entry,
        ),
    )
    mock_platform(
        hass, "test.light", MockPlatform(async_setup_entry=mock_setup_entry_platform)
    )
    mock_platform(hass, "test.config_flow", None)

    entry = MockConfigEntry(domain="test", entry_id="test2")
    entry.add_to_manager(manager)

    # Setup entry
    await manager.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await manager.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    del task

    assert (
        "OperationNotAllowed: The config entry 'Mock Title' (test) with "
        "entry_id 'test2' cannot forward setup for light because it is "
        "in state ConfigEntryState.NOT_LOADED, but needs to be in the "
        "ConfigEntryState.LOADED state"
    ) in caplog.text


async def test_config_entry_late_platform_setup(
    hass: HomeAssistant,
    manager: config_entries.ConfigEntries,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test async_forward_entry_setup not being awaited."""
    task = None

    async def mock_setup_entry(
        hass: HomeAssistant, entry: config_entries.ConfigEntry
    ) -> bool:
        """Mock setting up entry."""

        # Call async_forward_entry_setup in a non-tracked task
        # so we can unload the config entry during the setup
        def _late_setup():
            nonlocal task
            task = asyncio.create_task(
                hass.config_entries.async_forward_entry_setup(entry, "light")
            )

        hass.loop.call_soon(_late_setup)
        return True

    async def mock_unload_entry(
        hass: HomeAssistant, entry: config_entries.ConfigEntry
    ) -> bool:
        """Mock unloading an entry."""
        result = await hass.config_entries.async_unload_platforms(entry, ["light"])
        assert result
        return result

    mock_remove_entry = AsyncMock(return_value=None)

    async def mock_setup_entry_platform(
        hass: HomeAssistant,
        entry: config_entries.ConfigEntry,
        async_add_entities: AddConfigEntryEntitiesCallback,
    ) -> None:
        """Mock setting up platform."""
        await asyncio.sleep(0)
        await asyncio.sleep(0)

    mock_integration(
        hass,
        MockModule(
            "test",
            async_setup_entry=mock_setup_entry,
            async_unload_entry=mock_unload_entry,
            async_remove_entry=mock_remove_entry,
        ),
    )
    mock_platform(
        hass, "test.light", MockPlatform(async_setup_entry=mock_setup_entry_platform)
    )
    mock_platform(hass, "test.config_flow", None)

    entry = MockConfigEntry(domain="test", entry_id="test2")
    entry.add_to_manager(manager)

    # Setup entry
    await manager.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await task
    await hass.async_block_till_done()

    assert (
        "OperationNotAllowed: The config entry Mock Title (test) with "
        "entry_id test2 cannot forward setup for light because it is "
        "not loaded in the ConfigEntryState.NOT_LOADED state"
    ) not in caplog.text


@pytest.mark.parametrize("load_registries", [False])
async def test_migration_from_1_2(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test migration from version 1.2."""
    hass_storage[config_entries.STORAGE_KEY] = {
        "version": 1,
        "minor_version": 2,
        "data": {
            "entries": [
                {
                    "data": {},
                    "disabled_by": None,
                    "domain": "sun",
                    "entry_id": "0a8bd02d0d58c7debf5daf7941c9afe2",
                    "minor_version": 1,
                    "options": {},
                    "pref_disable_new_entities": False,
                    "pref_disable_polling": False,
                    "source": "import",
                    "title": "Sun",
                    "unique_id": None,
                    "version": 1,
                },
            ]
        },
    }

    manager = config_entries.ConfigEntries(hass, {})
    await manager.async_initialize()

    # Test data was loaded
    entries = manager.async_entries()
    assert len(entries) == 1

    # Check we store migrated data
    await flush_store(manager._store)
    assert hass_storage[config_entries.STORAGE_KEY] == {
        "version": config_entries.STORAGE_VERSION,
        "minor_version": config_entries.STORAGE_VERSION_MINOR,
        "key": config_entries.STORAGE_KEY,
        "data": {
            "entries": [
                {
                    "created_at": "1970-01-01T00:00:00+00:00",
                    "data": {},
                    "disabled_by": None,
                    "discovery_keys": {},
                    "domain": "sun",
                    "entry_id": "0a8bd02d0d58c7debf5daf7941c9afe2",
                    "minor_version": 1,
                    "modified_at": "1970-01-01T00:00:00+00:00",
                    "options": {},
                    "pref_disable_new_entities": False,
                    "pref_disable_polling": False,
                    "source": "import",
                    "subentries": {},
                    "title": "Sun",
                    "unique_id": None,
                    "version": 1,
                },
            ]
        },
    }


async def test_async_loaded_entries(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test that we can get loaded config entries."""
    entry1 = MockConfigEntry(domain="comp")
    entry1.add_to_hass(hass)
    entry2 = MockConfigEntry(domain="comp", source=config_entries.SOURCE_IGNORE)
    entry2.add_to_hass(hass)
    entry3 = MockConfigEntry(
        domain="comp", disabled_by=config_entries.ConfigEntryDisabler.USER
    )
    entry3.add_to_hass(hass)

    mock_setup = AsyncMock(return_value=True)
    mock_setup_entry = AsyncMock(return_value=True)
    mock_unload_entry = AsyncMock(return_value=True)

    mock_integration(
        hass,
        MockModule(
            "comp",
            async_setup=mock_setup,
            async_setup_entry=mock_setup_entry,
            async_unload_entry=mock_unload_entry,
        ),
    )
    mock_platform(hass, "comp.config_flow", None)

    assert hass.config_entries.async_loaded_entries("comp") == []

    assert await manager.async_setup(entry1.entry_id)
    assert not await manager.async_setup(entry2.entry_id)
    assert not await manager.async_setup(entry3.entry_id)

    assert hass.config_entries.async_loaded_entries("comp") == [entry1]

    assert await hass.config_entries.async_unload(entry1.entry_id)

    assert hass.config_entries.async_loaded_entries("comp") == []


async def test_async_has_matching_discovery_flow(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test we can check for matching discovery flows."""
    assert (
        manager.flow.async_has_matching_discovery_flow(
            "test",
            {"source": config_entries.SOURCE_HOMEKIT},
            {"properties": {"id": "aa:bb:cc:dd:ee:ff"}},
        )
        is False
    )

    mock_integration(hass, MockModule("test"))
    mock_platform(hass, "test.config_flow", None)

    class TestFlow(config_entries.ConfigFlow):
        VERSION = 5

        async def async_step_init(self, user_input=None):
            return self.async_show_progress(
                step_id="init",
                progress_action="task_one",
            )

        async def async_step_homekit(self, discovery_info=None):
            return await self.async_step_init(discovery_info)

    with mock_config_flow("test", TestFlow):
        result = await manager.flow.async_init(
            "test",
            context={"source": config_entries.SOURCE_HOMEKIT},
            data={"properties": {"id": "aa:bb:cc:dd:ee:ff"}},
        )
    assert result["type"] == data_entry_flow.FlowResultType.SHOW_PROGRESS
    assert result["progress_action"] == "task_one"
    assert len(manager.flow.async_progress()) == 1
    assert len(manager.flow.async_progress_by_handler("test")) == 1
    assert (
        len(
            manager.flow.async_progress_by_handler(
                "test", match_context={"source": config_entries.SOURCE_HOMEKIT}
            )
        )
        == 1
    )
    assert (
        len(
            manager.flow.async_progress_by_handler(
                "test", match_context={"source": config_entries.SOURCE_BLUETOOTH}
            )
        )
        == 0
    )
    assert manager.flow.async_get(result["flow_id"])["handler"] == "test"

    assert (
        manager.flow.async_has_matching_discovery_flow(
            "test",
            {"source": config_entries.SOURCE_HOMEKIT},
            {"properties": {"id": "aa:bb:cc:dd:ee:ff"}},
        )
        is True
    )
    assert (
        manager.flow.async_has_matching_discovery_flow(
            "test",
            {"source": config_entries.SOURCE_SSDP},
            {"properties": {"id": "aa:bb:cc:dd:ee:ff"}},
        )
        is False
    )
    assert (
        manager.flow.async_has_matching_discovery_flow(
            "other",
            {"source": config_entries.SOURCE_HOMEKIT},
            {"properties": {"id": "aa:bb:cc:dd:ee:ff"}},
        )
        is False
    )


async def test_async_has_matching_flow(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test check for matching flows when there is no active flow."""
    mock_integration(hass, MockModule("test"))
    mock_platform(hass, "test.config_flow", None)

    class TestFlow(config_entries.ConfigFlow):
        VERSION = 5

        async def async_step_init(self, user_input=None):
            return self.async_show_progress(
                step_id="init",
                progress_action="task_one",
            )

        async def async_step_homekit(self, discovery_info=None):
            return await self.async_step_init(discovery_info)

        def is_matching(self, other_flow: Self) -> bool:
            """Return True if other_flow is matching this flow."""
            return True

    # Initiate a flow
    with mock_config_flow("test", TestFlow):
        await manager.flow.async_init(
            "test",
            context={"source": config_entries.SOURCE_HOMEKIT},
            data={"properties": {"id": "aa:bb:cc:dd:ee:ff"}},
        )
    flow = list(manager.flow._handler_progress_index.get("test"))[0]

    assert manager.flow.async_has_matching_flow(flow) is False

    # Initiate another flow
    with mock_config_flow("test", TestFlow):
        await manager.flow.async_init(
            "test",
            context={"source": config_entries.SOURCE_HOMEKIT},
            data={"properties": {"id": "aa:bb:cc:dd:ee:ff"}},
        )

    assert manager.flow.async_has_matching_flow(flow) is True


async def test_async_has_matching_flow_no_flows(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test check for matching flows when there is no active flow."""
    mock_integration(hass, MockModule("test"))
    mock_platform(hass, "test.config_flow", None)

    class TestFlow(config_entries.ConfigFlow):
        VERSION = 5

        async def async_step_init(self, user_input=None):
            return self.async_show_progress(
                step_id="init",
                progress_action="task_one",
            )

        async def async_step_homekit(self, discovery_info=None):
            return await self.async_step_init(discovery_info)

    with mock_config_flow("test", TestFlow):
        result = await manager.flow.async_init(
            "test",
            context={"source": config_entries.SOURCE_HOMEKIT},
            data={"properties": {"id": "aa:bb:cc:dd:ee:ff"}},
        )
    flow = list(manager.flow._handler_progress_index.get("test"))[0]

    # Abort the flow before checking for matching flows
    manager.flow.async_abort(result["flow_id"])

    assert manager.flow.async_has_matching_flow(flow) is False


async def test_async_has_matching_flow_not_implemented(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test check for matching flows when there is no active flow."""
    mock_integration(hass, MockModule("test"))
    mock_platform(hass, "test.config_flow", None)

    class TestFlow(config_entries.ConfigFlow):
        VERSION = 5

        async def async_step_init(self, user_input=None):
            return self.async_show_progress(
                step_id="init",
                progress_action="task_one",
            )

        async def async_step_homekit(self, discovery_info=None):
            return await self.async_step_init(discovery_info)

    # Initiate a flow
    with mock_config_flow("test", TestFlow):
        await manager.flow.async_init(
            "test",
            context={"source": config_entries.SOURCE_HOMEKIT},
            data={"properties": {"id": "aa:bb:cc:dd:ee:ff"}},
        )
    flow = list(manager.flow._handler_progress_index.get("test"))[0]

    # Initiate another flow
    with mock_config_flow("test", TestFlow):
        await manager.flow.async_init(
            "test",
            context={"source": config_entries.SOURCE_HOMEKIT},
            data={"properties": {"id": "aa:bb:cc:dd:ee:ff"}},
        )

    # The flow does not implement is_matching
    with pytest.raises(NotImplementedError):
        manager.flow.async_has_matching_flow(flow)


async def test_get_reauth_entry(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test _get_context_entry behavior."""
    entry = MockConfigEntry(
        title="test_title",
        domain="test",
        entry_id="01J915Q6T9F6G5V0QJX6HBC94T",
        data={"host": "any", "port": 123},
        unique_id=None,
    )
    entry.add_to_hass(hass)

    mock_integration(hass, MockModule("test"))
    mock_platform(hass, "test.config_flow", None)

    class TestFlow(config_entries.ConfigFlow):
        VERSION = 1

        async def async_step_user(self, user_input=None):
            """Test user step."""
            return await self._async_step_confirm()

        async def async_step_reauth(self, entry_data):
            """Test reauth step."""
            return await self._async_step_confirm()

        async def async_step_reconfigure(self, user_input=None):
            """Test reauth step."""
            return await self._async_step_confirm()

        async def _async_step_confirm(self):
            """Confirm input."""
            try:
                entry = self._get_reauth_entry()
            except ValueError as err:
                reason = str(err)
            except config_entries.UnknownEntry:
                reason = "Entry not found"
            else:
                reason = f"Found entry {entry.title}"
            try:
                entry_id = self._reauth_entry_id
            except ValueError:
                reason = f"{reason}: -"
            else:
                reason = f"{reason}: {entry_id}"
            return self.async_abort(reason=reason)

    # A reauth flow finds the config entry from context
    with mock_config_flow("test", TestFlow):
        result = await entry.start_reauth_flow(hass)
        assert result["reason"] == "Found entry test_title: 01J915Q6T9F6G5V0QJX6HBC94T"

    # The config entry is removed before the reauth flow is aborted
    with mock_config_flow("test", TestFlow):
        result = await entry.start_reauth_flow(hass, context={"entry_id": "01JRemoved"})
        assert result["reason"] == "Entry not found: 01JRemoved"

    # A reconfigure flow does not have access to the config entry
    with mock_config_flow("test", TestFlow):
        result = await entry.start_reconfigure_flow(hass)
        assert result["reason"] == "Source is reconfigure, expected reauth: -"

    # A user flow does not have access to the config entry
    with mock_config_flow("test", TestFlow):
        result = await manager.flow.async_init(
            "test", context={"source": config_entries.SOURCE_USER}
        )
        assert result["reason"] == "Source is user, expected reauth: -"


async def test_get_reconfigure_entry(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test _get_reconfigure_entry behavior."""
    entry = MockConfigEntry(
        title="test_title",
        domain="test",
        entry_id="01J915Q6T9F6G5V0QJX6HBC94T",
        data={"host": "any", "port": 123},
        unique_id=None,
    )
    entry.add_to_hass(hass)

    mock_integration(hass, MockModule("test"))
    mock_platform(hass, "test.config_flow", None)

    class TestFlow(config_entries.ConfigFlow):
        VERSION = 1

        async def async_step_user(self, user_input=None):
            """Test user step."""
            return await self._async_step_confirm()

        async def async_step_reauth(self, entry_data):
            """Test reauth step."""
            return await self._async_step_confirm()

        async def async_step_reconfigure(self, user_input=None):
            """Test reauth step."""
            return await self._async_step_confirm()

        async def _async_step_confirm(self):
            """Confirm input."""
            try:
                entry = self._get_reconfigure_entry()
            except ValueError as err:
                reason = str(err)
            except config_entries.UnknownEntry:
                reason = "Entry not found"
            else:
                reason = f"Found entry {entry.title}"
            try:
                entry_id = self._reconfigure_entry_id
            except ValueError:
                reason = f"{reason}: -"
            else:
                reason = f"{reason}: {entry_id}"
            return self.async_abort(reason=reason)

    # A reauth flow does not have access to the config entry from context
    with mock_config_flow("test", TestFlow):
        result = await entry.start_reauth_flow(hass)
        assert result["reason"] == "Source is reauth, expected reconfigure: -"

    # A reconfigure flow finds the config entry
    with mock_config_flow("test", TestFlow):
        result = await entry.start_reconfigure_flow(hass)
        assert result["reason"] == "Found entry test_title: 01J915Q6T9F6G5V0QJX6HBC94T"

    # The entry_id no longer exists
    with mock_config_flow("test", TestFlow):
        result = await manager.flow.async_init(
            "test",
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "entry_id": "01JRemoved",
            },
        )
        assert result["reason"] == "Entry not found: 01JRemoved"

    # A user flow does not have access to the config entry
    with mock_config_flow("test", TestFlow):
        result = await manager.flow.async_init(
            "test", context={"source": config_entries.SOURCE_USER}
        )
        assert result["reason"] == "Source is user, expected reconfigure: -"


async def test_subentry_get_entry(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test subentry _get_entry and _get_reconfigure_subentry behavior."""
    subentry_id = "mock_subentry_id"
    entry = MockConfigEntry(
        data={},
        domain="test",
        entry_id="mock_entry_id",
        title="entry_title",
        unique_id="entry_unique_id",
        subentries_data=[
            config_entries.ConfigSubentryData(
                data={"vendor": "data"},
                subentry_id=subentry_id,
                subentry_type="test",
                unique_id="1234",
                title="Test",
            )
        ],
    )

    entry.add_to_hass(hass)

    mock_integration(hass, MockModule("test"))
    mock_platform(hass, "test.config_flow", None)

    class TestFlow(config_entries.ConfigFlow):
        class SubentryFlowHandler(config_entries.ConfigSubentryFlow):
            async def async_step_user(self, user_input=None):
                """Test user step."""
                return await self._async_step_confirm()

            async def async_step_reconfigure(self, user_input=None):
                """Test reauth step."""
                return await self._async_step_confirm()

            async def _async_step_confirm(self):
                """Confirm input."""
                try:
                    entry = self._get_entry()
                except ValueError as err:
                    reason = str(err)
                else:
                    reason = f"Found entry {entry.title}"
                try:
                    entry_id = self._entry_id
                except ValueError:
                    reason = f"{reason}: -"
                else:
                    reason = f"{reason}: {entry_id}"

                try:
                    subentry = self._get_reconfigure_subentry()
                except ValueError as err:
                    reason = f"{reason}/{err}"
                except config_entries.UnknownSubEntry:
                    reason = f"{reason}/Subentry not found"
                else:
                    reason = f"{reason}/Found subentry {subentry.title}"
                try:
                    subentry_id = self._reconfigure_subentry_id
                except ValueError:
                    reason = f"{reason}: -"
                else:
                    reason = f"{reason}: {subentry_id}"
                return self.async_abort(reason=reason)

        @classmethod
        @callback
        def async_get_supported_subentry_types(
            cls, config_entry: config_entries.ConfigEntry
        ) -> dict[str, type[config_entries.ConfigSubentryFlow]]:
            return {"test": TestFlow.SubentryFlowHandler}

    # A reconfigure flow finds the config entry and subentry
    with mock_config_flow("test", TestFlow):
        result = await entry.start_subentry_reconfigure_flow(hass, "test", subentry_id)
        assert (
            result["reason"]
            == "Found entry entry_title: mock_entry_id/Found subentry Test: mock_subentry_id"
        )

    # The subentry_id does not exist
    with mock_config_flow("test", TestFlow):
        result = await manager.subentries.async_init(
            (entry.entry_id, "test"),
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "subentry_id": "01JRemoved",
            },
        )
        assert (
            result["reason"]
            == "Found entry entry_title: mock_entry_id/Subentry not found: 01JRemoved"
        )

    # A user flow finds the config entry but not the subentry
    with mock_config_flow("test", TestFlow):
        result = await manager.subentries.async_init(
            (entry.entry_id, "test"), context={"source": config_entries.SOURCE_USER}
        )
        assert (
            result["reason"]
            == "Found entry entry_title: mock_entry_id/Source is user, expected reconfigure: -"
        )


async def test_reauth_helper_alignment(
    hass: HomeAssistant,
    manager: config_entries.ConfigEntries,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test `start_reauth_flow` helper alignment.

    It should be aligned with `ConfigEntry._async_init_reauth`.
    """
    entry = MockConfigEntry(
        title="test_title",
        domain="test",
        entry_id="01J915Q6T9F6G5V0QJX6HBC94T",
        data={"host": "any", "port": 123},
        unique_id=None,
    )
    entry.add_to_hass(hass)

    mock_setup_entry = AsyncMock(
        side_effect=ConfigEntryAuthFailed("The password is no longer valid")
    )
    mock_integration(hass, MockModule("test", async_setup_entry=mock_setup_entry))
    mock_platform(hass, "test.config_flow", None)

    # Check context via auto-generated reauth
    await manager.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert "could not authenticate: The password is no longer valid" in caplog.text

    assert entry.state is config_entries.ConfigEntryState.SETUP_ERROR
    assert entry.reason == "The password is no longer valid"

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    reauth_flow_context = flows[0]["context"]
    reauth_flow_init_data = hass.config_entries.flow._progress[
        flows[0]["flow_id"]
    ].init_data

    # Clear to make way for `start_reauth_flow` helper
    manager.flow.async_abort(flows[0]["flow_id"])
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 0

    # Check context via `start_reauth_flow` helper
    await entry.start_reauth_flow(hass)
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    helper_flow_context = flows[0]["context"]
    helper_flow_init_data = hass.config_entries.flow._progress[
        flows[0]["flow_id"]
    ].init_data

    # Ensure context and init data are aligned
    assert helper_flow_context == reauth_flow_context
    assert helper_flow_init_data == reauth_flow_init_data


@pytest.mark.parametrize(
    ("original_unique_id", "new_unique_id", "reason"),
    [
        ("unique", "unique", "success"),
        (None, None, "success"),
        ("unique", "new", "unique_id_mismatch"),
        ("unique", None, "unique_id_mismatch"),
        (None, "new", "unique_id_mismatch"),
    ],
)
@pytest.mark.parametrize(
    "source",
    [config_entries.SOURCE_REAUTH, config_entries.SOURCE_RECONFIGURE],
)
async def test_abort_if_unique_id_mismatch(
    hass: HomeAssistant,
    source: str,
    original_unique_id: str | None,
    new_unique_id: str | None,
    reason: str,
) -> None:
    """Test to check if_unique_id_mismatch behavior."""
    entry = MockConfigEntry(
        title="From config flow",
        domain="test",
        entry_id="01J915Q6T9F6G5V0QJX6HBC94T",
        data={"host": "any", "port": 123},
        unique_id=original_unique_id,
    )
    entry.add_to_hass(hass)

    mock_setup_entry = AsyncMock(return_value=True)

    mock_integration(hass, MockModule("test", async_setup_entry=mock_setup_entry))
    mock_platform(hass, "test.config_flow", None)

    class TestFlow(config_entries.ConfigFlow):
        VERSION = 1

        async def async_step_user(self, user_input=None):
            """Test user step."""
            return await self._async_step_confirm()

        async def async_step_reauth(self, entry_data):
            """Test reauth step."""
            return await self._async_step_confirm()

        async def async_step_reconfigure(self, user_input=None):
            """Test reauth step."""
            return await self._async_step_confirm()

        async def _async_step_confirm(self):
            """Confirm input."""
            await self.async_set_unique_id(new_unique_id)
            self._abort_if_unique_id_mismatch()
            return self.async_abort(reason="success")

    with mock_config_flow("test", TestFlow):
        if source == config_entries.SOURCE_REAUTH:
            result = await entry.start_reauth_flow(hass)
        elif source == config_entries.SOURCE_RECONFIGURE:
            result = await entry.start_reconfigure_flow(hass)
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


def test_state_not_stored_in_storage() -> None:
    """Test that state is not stored in storage.

    Verify we don't start accidentally storing state in storage.
    """
    entry = MockConfigEntry(domain="test")
    loaded = json_loads(json_dumps(entry.as_storage_fragment))
    for key in config_entries.STATE_KEYS:
        assert key not in loaded


def test_storage_cache_is_cleared_on_entry_update(hass: HomeAssistant) -> None:
    """Test that the storage cache is cleared when an entry is updated."""
    entry = MockConfigEntry(domain="test")
    entry.add_to_hass(hass)
    _ = entry.as_storage_fragment
    hass.config_entries.async_update_entry(entry, data={"new": "data"})
    loaded = json_loads(json_dumps(entry.as_storage_fragment))
    assert "new" in loaded["data"]


async def test_storage_cache_is_cleared_on_entry_disable(hass: HomeAssistant) -> None:
    """Test that the storage cache is cleared when an entry is disabled."""
    entry = MockConfigEntry(domain="test")
    entry.add_to_hass(hass)
    _ = entry.as_storage_fragment
    await hass.config_entries.async_set_disabled_by(
        entry.entry_id, config_entries.ConfigEntryDisabler.USER
    )
    loaded = json_loads(json_dumps(entry.as_storage_fragment))
    assert loaded["disabled_by"] == "user"


async def test_state_cache_is_cleared_on_entry_disable(hass: HomeAssistant) -> None:
    """Test that the state cache is cleared when an entry is disabled."""
    entry = MockConfigEntry(domain="test")
    entry.add_to_hass(hass)
    _ = entry.as_storage_fragment
    await hass.config_entries.async_set_disabled_by(
        entry.entry_id, config_entries.ConfigEntryDisabler.USER
    )
    loaded = json_loads(json_dumps(entry.as_json_fragment))
    assert loaded["disabled_by"] == "user"


@pytest.mark.parametrize(
    ("original_unique_id", "new_unique_id", "count"),
    [
        ("unique", "unique", 1),
        ("unique", "new", 2),
        ("unique", None, 2),
        (None, "unique", 2),
    ],
)
@pytest.mark.parametrize(
    "source",
    [config_entries.SOURCE_REAUTH, config_entries.SOURCE_RECONFIGURE],
)
async def test_create_entry_reauth_reconfigure(
    hass: HomeAssistant,
    source: str,
    original_unique_id: str | None,
    new_unique_id: str | None,
    count: int,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test to highlight unexpected behavior on create_entry."""
    entry = MockConfigEntry(
        title="From config flow",
        domain="test",
        entry_id="01J915Q6T9F6G5V0QJX6HBC94T",
        data={"host": "any", "port": 123},
        unique_id=original_unique_id,
    )
    entry.add_to_hass(hass)

    mock_setup_entry = AsyncMock(return_value=True)

    mock_integration(hass, MockModule("test", async_setup_entry=mock_setup_entry))
    mock_platform(hass, "test.config_flow", None)

    class TestFlow(config_entries.ConfigFlow):
        VERSION = 1

        async def async_step_user(self, user_input=None):
            """Test user step."""
            return await self._async_step_confirm()

        async def async_step_reauth(self, entry_data):
            """Test reauth step."""
            return await self._async_step_confirm()

        async def async_step_reconfigure(self, user_input=None):
            """Test reauth step."""
            return await self._async_step_confirm()

        async def _async_step_confirm(self):
            """Confirm input."""
            await self.async_set_unique_id(new_unique_id)
            return self.async_create_entry(
                title="From config flow",
                data={"token": "supersecret"},
            )

    assert len(hass.config_entries.async_entries("test")) == 1

    with (
        mock_config_flow("test", TestFlow),
        patch.object(frame, "_REPORTED_INTEGRATIONS", set()),
    ):
        result = await getattr(entry, f"start_{source}_flow")(hass)
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY

    entries = hass.config_entries.async_entries("test")
    assert len(entries) == count
    if count == 1:
        # Show that the previous entry got binned and recreated
        assert entries[0].entry_id != entry.entry_id

    assert (
        f"Detected that integration 'test' creates a new entry in a '{source}' flow, "
        "when it is expected to update an existing entry and abort. This will stop "
        "working in Home Assistant 2025.11, please create a bug report at "
        "https://github.com/home-assistant/core/issues?q=is%3Aopen+is%3Aissue+"
        "label%3A%22integration%3A+test%22"
    ) in caplog.text


async def test_async_update_entry_unique_id_collision(
    hass: HomeAssistant,
    manager: config_entries.ConfigEntries,
    caplog: pytest.LogCaptureFixture,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test we warn when async_update_entry creates a unique_id collision.

    Also test an issue registry issue is created.
    """
    assert len(issue_registry.issues) == 0

    entry1 = MockConfigEntry(domain="test", unique_id=None)
    entry2 = MockConfigEntry(domain="test", unique_id="not none")
    entry3 = MockConfigEntry(domain="test", unique_id="very unique")
    entry4 = MockConfigEntry(domain="test", unique_id="also very unique")
    entry1.add_to_manager(manager)
    entry2.add_to_manager(manager)
    entry3.add_to_manager(manager)
    entry4.add_to_manager(manager)

    manager.async_update_entry(entry2, unique_id=None)
    assert len(issue_registry.issues) == 0
    assert len(caplog.record_tuples) == 0

    manager.async_update_entry(entry4, unique_id="very unique")
    assert len(issue_registry.issues) == 1
    assert len(caplog.record_tuples) == 1

    assert (
        "Unique id of config entry 'Mock Title' from integration test changed to "
        "'very unique' which is already in use"
    ) in caplog.text

    issue_id = "config_entry_unique_id_collision_test_very unique"
    assert issue_registry.async_get_issue(HOMEASSISTANT_DOMAIN, issue_id)


async def test_unique_id_collision_issues(
    hass: HomeAssistant,
    manager: config_entries.ConfigEntries,
    caplog: pytest.LogCaptureFixture,
    issue_registry: ir.IssueRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test issue registry issues are created and remove on unique id collision."""
    assert len(issue_registry.issues) == 0

    mock_setup_entry = AsyncMock(return_value=True)
    for i in range(3):
        mock_integration(
            hass, MockModule(f"test{i + 1}", async_setup_entry=mock_setup_entry)
        )
        mock_platform(hass, f"test{i + 1}.config_flow", None)

    test2_group_1: list[MockConfigEntry] = []
    test2_group_2: list[MockConfigEntry] = []
    test3: list[MockConfigEntry] = []
    for _ in range(3):
        await manager.async_add(MockConfigEntry(domain="test1", unique_id=None))
        test2_group_1.append(MockConfigEntry(domain="test2", unique_id="group_1"))
        test2_group_2.append(MockConfigEntry(domain="test2", unique_id="group_2"))
        await manager.async_add(test2_group_1[-1])
        await manager.async_add(test2_group_2[-1])
    for _ in range(6):
        test3.append(MockConfigEntry(domain="test3", unique_id="not_unique"))
        await manager.async_add(test3[-1])
    # Add an ignored config entry
    await manager.async_add(
        MockConfigEntry(
            domain="test2", unique_id="group_1", source=config_entries.SOURCE_IGNORE
        )
    )

    # Check we get one issue for domain test2 and one issue for domain test3
    assert len(issue_registry.issues) == 2
    issue_id = "config_entry_unique_id_collision_test2_group_1"
    assert issue_registry.async_get_issue(HOMEASSISTANT_DOMAIN, issue_id) == snapshot
    issue_id = "config_entry_unique_id_collision_test3_not_unique"
    assert issue_registry.async_get_issue(HOMEASSISTANT_DOMAIN, issue_id) == snapshot

    # Remove one config entry for domain test3, the translations should be updated
    await manager.async_remove(test3[0].entry_id)
    assert set(issue_registry.issues) == {
        (HOMEASSISTANT_DOMAIN, "config_entry_unique_id_collision_test2_group_1"),
        (HOMEASSISTANT_DOMAIN, "config_entry_unique_id_collision_test3_not_unique"),
    }
    assert issue_registry.async_get_issue(HOMEASSISTANT_DOMAIN, issue_id) == snapshot

    # Remove all but two config entries for domain test 3
    for i in range(3):
        await manager.async_remove(test3[1 + i].entry_id)
        assert set(issue_registry.issues) == {
            (HOMEASSISTANT_DOMAIN, "config_entry_unique_id_collision_test2_group_1"),
            (HOMEASSISTANT_DOMAIN, "config_entry_unique_id_collision_test3_not_unique"),
        }

    # Remove the last test3 duplicate, the issue is cleared
    await manager.async_remove(test3[-1].entry_id)
    assert set(issue_registry.issues) == {
        (HOMEASSISTANT_DOMAIN, "config_entry_unique_id_collision_test2_group_1"),
    }

    await manager.async_remove(test2_group_1[0].entry_id)
    assert set(issue_registry.issues) == {
        (HOMEASSISTANT_DOMAIN, "config_entry_unique_id_collision_test2_group_1"),
    }

    # Remove the last test2 group1 duplicate, a new issue is created
    await manager.async_remove(test2_group_1[1].entry_id)
    assert set(issue_registry.issues) == {
        (HOMEASSISTANT_DOMAIN, "config_entry_unique_id_collision_test2_group_2"),
    }

    await manager.async_remove(test2_group_2[0].entry_id)
    assert set(issue_registry.issues) == {
        (HOMEASSISTANT_DOMAIN, "config_entry_unique_id_collision_test2_group_2"),
    }

    # Remove the last test2 group2 duplicate, the issue is cleared
    await manager.async_remove(test2_group_2[1].entry_id)
    assert not issue_registry.issues


async def test_context_no_leak(hass: HomeAssistant) -> None:
    """Test ensure that config entry context does not leak.

    Unlikely to happen in real world, but occurs often in tests.
    """

    connected_future = asyncio.Future()
    bg_tasks = []

    async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
        """Mock setup entry."""

        async def _async_set_runtime_data():
            # Show that config_entries.current_entry is preserved for child tasks
            await connected_future
            entry.runtime_data = config_entries.current_entry.get()

        bg_tasks.append(hass.loop.create_task(_async_set_runtime_data()))

        return True

    async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
        """Mock unload entry."""
        return True

    mock_integration(
        hass,
        MockModule(
            "comp",
            async_setup_entry=async_setup_entry,
            async_unload_entry=async_unload_entry,
        ),
    )
    mock_platform(hass, "comp.config_flow", None)

    entry1 = MockConfigEntry(domain="comp")
    entry1.add_to_hass(hass)

    await hass.config_entries.async_setup(entry1.entry_id)
    assert entry1.state is config_entries.ConfigEntryState.LOADED
    assert config_entries.current_entry.get() is None

    # Load an existing config entry
    entry2 = MockConfigEntry(domain="comp")
    entry2.add_to_hass(hass)
    await hass.config_entries.async_setup(entry2.entry_id)
    assert entry2.state is config_entries.ConfigEntryState.LOADED
    assert config_entries.current_entry.get() is None

    # Add a new config entry (eg. from config flow)
    entry3 = MockConfigEntry(domain="comp")
    await hass.config_entries.async_add(entry3)
    assert entry3.state is config_entries.ConfigEntryState.LOADED
    assert config_entries.current_entry.get() is None

    for entry in (entry1, entry2, entry3):
        assert entry.state is config_entries.ConfigEntryState.LOADED
        assert not hasattr(entry, "runtime_data")
    assert config_entries.current_entry.get() is None

    connected_future.set_result(None)
    await asyncio.gather(*bg_tasks)

    for entry in (entry1, entry2, entry3):
        assert entry.state is config_entries.ConfigEntryState.LOADED
        assert entry.runtime_data is entry
    assert config_entries.current_entry.get() is None


async def test_options_flow_config_entry(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test _config_entry_id and config_entry properties in options flow."""
    original_entry = MockConfigEntry(domain="test", data={})
    original_entry.add_to_hass(hass)

    mock_setup_entry = AsyncMock(return_value=True)

    mock_integration(hass, MockModule("test", async_setup_entry=mock_setup_entry))
    mock_platform(hass, "test.config_flow", None)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        @staticmethod
        @callback
        def async_get_options_flow(config_entry):
            """Test options flow."""

            class _OptionsFlow(config_entries.OptionsFlow):
                """Test flow."""

                def __init__(self) -> None:
                    """Test initialisation."""
                    try:
                        self.init_entry_id = self._config_entry_id
                    except ValueError as err:
                        self.init_entry_id = err
                    try:
                        self.init_entry = self.config_entry
                    except ValueError as err:
                        self.init_entry = err

                async def async_step_init(self, user_input=None):
                    """Test user step."""
                    errors = {}
                    if user_input is not None:
                        if user_input.get("abort"):
                            return self.async_abort(reason="abort")

                        errors["entry_id"] = self._config_entry_id
                        try:
                            errors["entry"] = self.config_entry
                        except config_entries.UnknownEntry as err:
                            errors["entry"] = err

                    return self.async_show_form(step_id="init", errors=errors)

            return _OptionsFlow()

    with mock_config_flow("test", TestFlow):
        result = await hass.config_entries.options.async_init(original_entry.entry_id)

    options_flow = hass.config_entries.options._progress.get(result["flow_id"])
    assert isinstance(options_flow, config_entries.OptionsFlow)
    assert options_flow.handler == original_entry.entry_id
    assert isinstance(options_flow.init_entry_id, ValueError)
    assert (
        str(options_flow.init_entry_id)
        == "The config entry id is not available during initialisation"
    )
    assert isinstance(options_flow.init_entry, ValueError)
    assert (
        str(options_flow.init_entry)
        == "The config entry is not available during initialisation"
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["errors"] == {}

    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["errors"]["entry_id"] == original_entry.entry_id
    assert result["errors"]["entry"] is original_entry

    # Bad handler - not linked to a config entry
    options_flow.handler = "123"
    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["errors"]["entry_id"] == "123"
    assert isinstance(result["errors"]["entry"], config_entries.UnknownEntry)
    # Reset handler
    options_flow.handler = original_entry.entry_id

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"abort": True}
    )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "abort"


@pytest.mark.parametrize("integration_frame_path", ["custom_components/my_integration"])
@pytest.mark.usefixtures("mock_integration_frame")
async def test_options_flow_deprecated_config_entry_setter(
    hass: HomeAssistant,
    manager: config_entries.ConfigEntries,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that setting config_entry explicitly still works."""
    original_entry = MockConfigEntry(domain="my_integration", data={})
    original_entry.add_to_hass(hass)

    mock_setup_entry = AsyncMock(return_value=True)

    mock_integration(
        hass, MockModule("my_integration", async_setup_entry=mock_setup_entry)
    )
    mock_platform(hass, "my_integration.config_flow", None)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        @staticmethod
        @callback
        def async_get_options_flow(config_entry):
            """Test options flow."""

            class _OptionsFlow(config_entries.OptionsFlow):
                """Test flow."""

                def __init__(self, entry) -> None:
                    """Test initialisation."""
                    self.config_entry = entry

                async def async_step_init(self, user_input=None):
                    """Test user step."""
                    errors = {}
                    if user_input is not None:
                        if user_input.get("abort"):
                            return self.async_abort(reason="abort")

                        errors["entry_id"] = self._config_entry_id
                        try:
                            errors["entry"] = self.config_entry
                        except config_entries.UnknownEntry as err:
                            errors["entry"] = err

                    return self.async_show_form(step_id="init", errors=errors)

            return _OptionsFlow(config_entry)

    with mock_config_flow("my_integration", TestFlow):
        result = await hass.config_entries.options.async_init(original_entry.entry_id)

    options_flow = hass.config_entries.options._progress.get(result["flow_id"])
    assert options_flow.config_entry is original_entry

    assert (
        "Detected that custom integration 'my_integration' sets option flow "
        "config_entry explicitly, which is deprecated at "
        "custom_components/my_integration/light.py, line 23: "
        "self.light.is_on. This will stop working in Home Assistant 2025.12, please "
        "report it to the author of the 'my_integration' custom integration"
        in caplog.text
    )


async def test_add_description_placeholder_automatically(
    hass: HomeAssistant,
    manager: config_entries.ConfigEntries,
) -> None:
    """Test entry title is added automatically to reauth flows description placeholder."""

    entry = MockConfigEntry(title="test_title", domain="test")

    mock_setup_entry = AsyncMock(side_effect=ConfigEntryAuthFailed())
    mock_integration(hass, MockModule("test", async_setup_entry=mock_setup_entry))
    mock_platform(hass, "test.config_flow", None)

    entry.add_to_hass(hass)
    await manager.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress_by_handler("test")
    assert len(flows) == 1

    result = await hass.config_entries.flow.async_configure(flows[0]["flow_id"], None)
    assert result["type"] == FlowResultType.FORM
    assert result["description_placeholders"] == {"name": "test_title"}


async def test_add_description_placeholder_automatically_not_overwrites(
    hass: HomeAssistant,
    manager: config_entries.ConfigEntries,
) -> None:
    """Test entry title is not added automatically to reauth flows when custom name exist."""

    entry = MockConfigEntry(title="test_title", domain="test2")

    mock_setup_entry = AsyncMock(side_effect=ConfigEntryAuthFailed())
    mock_integration(hass, MockModule("test2", async_setup_entry=mock_setup_entry))
    mock_platform(hass, "test2.config_flow", None)

    entry.add_to_hass(hass)
    await manager.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress_by_handler("test2")
    assert len(flows) == 1

    result = await hass.config_entries.flow.async_configure(flows[0]["flow_id"], None)
    assert result["type"] == FlowResultType.FORM
    assert result["description_placeholders"] == {"name": "Custom title"}


@pytest.mark.parametrize(
    ("domain", "source", "expected_log"),
    [
        ("some_integration", config_entries.SOURCE_USER, True),
        ("some_integration", config_entries.SOURCE_IGNORE, False),
        ("mobile_app", config_entries.SOURCE_USER, False),
    ],
)
async def test_create_entry_existing_unique_id(
    hass: HomeAssistant,
    domain: str,
    source: str,
    expected_log: bool,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test to highlight unexpected behavior on create_entry."""
    entry = MockConfigEntry(
        title="From config flow",
        domain=domain,
        entry_id="01J915Q6T9F6G5V0QJX6HBC94T",
        data={"host": "any", "port": 123},
        unique_id="mock-unique-id",
        source=source,
    )
    entry.add_to_hass(hass)

    assert len(hass.config_entries.async_entries(domain)) == 1

    mock_setup_entry = AsyncMock(return_value=True)

    mock_integration(hass, MockModule(domain, async_setup_entry=mock_setup_entry))
    mock_platform(hass, f"{domain}.config_flow", None)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 1

        async def async_step_user(self, user_input=None):
            """Test user step."""
            await self.async_set_unique_id("mock-unique-id")
            return self.async_create_entry(title="mock-title", data={})

    with (
        mock_config_flow(domain, TestFlow),
        patch.object(frame, "_REPORTED_INTEGRATIONS", set()),
    ):
        result = await hass.config_entries.flow.async_init(
            domain, context={"source": config_entries.SOURCE_USER}
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY

    assert len(hass.config_entries.async_entries(domain)) == 1

    log_text = (
        f"Detected that integration '{domain}' creates a config entry "
        "when another entry with the same unique ID exists. Please "
        "create a bug report at https:"
    )
    assert (log_text in caplog.text) == expected_log
