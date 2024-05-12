"""Test the config manager."""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from datetime import timedelta
from functools import cached_property
import logging
from typing import Any
from unittest.mock import ANY, AsyncMock, Mock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant import config_entries, data_entry_flow, loader
from homeassistant.components import dhcp
from homeassistant.components.hassio import HassioServiceInfo
from homeassistant.const import (
    EVENT_COMPONENT_LOADED,
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import DOMAIN as HA_DOMAIN, CoreState, HomeAssistant, callback
from homeassistant.data_entry_flow import BaseServiceInfo, FlowResult, FlowResultType
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.setup import async_set_domains_to_be_loaded, async_setup_component
import homeassistant.util.dt as dt_util

from .common import (
    MockConfigEntry,
    MockEntity,
    MockModule,
    MockPlatform,
    async_capture_events,
    async_fire_time_changed,
    mock_config_flow,
    mock_integration,
    mock_platform,
)

from tests.common import async_get_persistent_notifications


@pytest.fixture(autouse=True)
def mock_handlers() -> Generator[None, None, None]:
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

    with patch.dict(
        config_entries.HANDLERS, {"comp": MockFlowHandler, "test": MockFlowHandler}
    ):
        yield


@pytest.fixture
async def manager(hass: HomeAssistant) -> config_entries.ConfigEntries:
    """Fixture of a loaded config manager."""
    manager = config_entries.ConfigEntries(hass, {})
    await manager.async_initialize()
    hass.config_entries = manager
    return manager


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

    mock_remove_entry = AsyncMock(return_value=None)

    entity = MockEntity(unique_id="1234", name="Test Entity")

    async def mock_setup_entry_platform(
        hass: HomeAssistant,
        entry: config_entries.ConfigEntry,
        async_add_entities: AddEntitiesCallback,
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

    # Remove entry
    result = await manager.async_remove("test2")
    await hass.async_block_till_done()

    # Check that unload went well and so no need to restart
    assert result == {"require_restart": False}

    # Check the remove callback was invoked.
    assert mock_remove_entry.call_count == 1

    # Check that config entry was removed.
    assert manager.async_entry_ids() == ["test1", "test3"]

    # Check that entity state has been removed
    assert hass.states.get("light.test_entity") is None
    assert len(hass.states.async_all()) == 0

    # Check that entity registry entry has been removed
    entity_entry_list = list(entity_registry.entities.values())
    assert not entity_entry_list


async def test_remove_entry_cancels_reauth(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Tests that removing a config entry, also aborts existing reauth flows."""
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

    issue_registry = ir.async_get(hass)
    issue_id = f"config_entry_reauth_test_{entry.entry_id}"
    assert issue_registry.async_get_issue(HA_DOMAIN, issue_id)

    await manager.async_remove(entry.entry_id)

    flows = hass.config_entries.flow.async_progress_by_handler("test")
    assert len(flows) == 0
    assert not issue_registry.async_get_issue(HA_DOMAIN, issue_id)


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

    async def mock_unload_entry(hass, entry):
        """Mock unload entry function."""
        raise Exception("BROKEN")

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

    with patch.dict(config_entries.HANDLERS, {"comp": TestFlow, "beer": 5}):
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
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
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
            return self.async_create_entry(title="Test Title", data={"token": "abcd"})

    with patch.dict(config_entries.HANDLERS, {"test": TestFlow}):
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
            "test", context={"source": config_entries.SOURCE_USER}
        )

    assert len(hass.config_entries.async_entries()) == 2
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

    # Now load written data in new config manager
    manager = config_entries.ConfigEntries(hass, {})
    await manager.async_initialize()

    assert len(manager.async_entries()) == 2

    # Ensure same order
    for orig, loaded in zip(
        hass.config_entries.async_entries(), manager.async_entries(), strict=False
    ):
        assert orig.as_dict() == loaded.as_dict()


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
        "_reconfigure_lock",
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
            or type(func) in (cached_property, property)
        ):
            continue
        assert key in dict_repr or key in excluded_from_dict
        assert not (key in dict_repr and key in excluded_from_dict)

    # Make sure the dict representation is as expected
    assert dict_repr == snapshot


async def test_forward_entry_sets_up_component(hass: HomeAssistant) -> None:
    """Test we setup the component entry is forwarded to."""
    entry = MockConfigEntry(domain="original")

    mock_original_setup_entry = AsyncMock(return_value=True)
    integration = mock_integration(
        hass, MockModule("original", async_setup_entry=mock_original_setup_entry)
    )

    mock_forwarded_setup_entry = AsyncMock(return_value=True)
    mock_integration(
        hass, MockModule("forwarded", async_setup_entry=mock_forwarded_setup_entry)
    )

    with patch.object(integration, "async_get_platform") as mock_async_get_platform:
        await hass.config_entries.async_forward_entry_setup(entry, "forwarded")

    mock_async_get_platform.assert_called_once_with("forwarded")
    assert len(mock_original_setup_entry.mock_calls) == 0
    assert len(mock_forwarded_setup_entry.mock_calls) == 1


async def test_forward_entry_does_not_setup_entry_if_setup_fails(
    hass: HomeAssistant,
) -> None:
    """Test we do not set up entry if component setup fails."""
    entry = MockConfigEntry(domain="original")

    mock_setup = AsyncMock(return_value=False)
    mock_setup_entry = AsyncMock()
    mock_integration(
        hass,
        MockModule(
            "forwarded", async_setup=mock_setup, async_setup_entry=mock_setup_entry
        ),
    )

    await hass.config_entries.async_forward_entry_setup(entry, "forwarded")
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 0


async def test_discovery_notification(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test that we create/dismiss a notification when source is discovery."""
    mock_integration(hass, MockModule("test"))
    mock_platform(hass, "test.config_flow", None)

    with patch.dict(config_entries.HANDLERS):

        class TestFlow(config_entries.ConfigFlow, domain="test"):
            """Test flow."""

            VERSION = 5

            async def async_step_discovery(self, discovery_info):
                """Test discovery step."""
                return self.async_show_form(step_id="discovery_confirm")

            async def async_step_discovery_confirm(self, discovery_info):
                """Test discovery confirm step."""
                return self.async_create_entry(
                    title="Test Title", data={"token": "abcd"}
                )

        notifications = async_get_persistent_notifications(hass)
        assert "config_entry_discovery" not in notifications

        # Start first discovery flow to assert that reconfigure notification fires
        flow1 = await hass.config_entries.flow.async_init(
            "test", context={"source": config_entries.SOURCE_DISCOVERY}
        )
        await hass.async_block_till_done()
        notifications = async_get_persistent_notifications(hass)
        assert "config_entry_discovery" in notifications

        # Start a second discovery flow so we can finish the first and assert that
        # the discovery notification persists until the second one is complete
        flow2 = await hass.config_entries.flow.async_init(
            "test", context={"source": config_entries.SOURCE_DISCOVERY}
        )

        flow1 = await hass.config_entries.flow.async_configure(flow1["flow_id"], {})
        assert flow1["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY

        await hass.async_block_till_done()
        notifications = async_get_persistent_notifications(hass)
        assert "config_entry_discovery" in notifications

        flow2 = await hass.config_entries.flow.async_configure(flow2["flow_id"], {})
        assert flow2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY

        await hass.async_block_till_done()
        notifications = async_get_persistent_notifications(hass)
        assert "config_entry_discovery" not in notifications


async def test_reauth_notification(hass: HomeAssistant) -> None:
    """Test that we create/dismiss a notification when source is reauth."""
    mock_integration(hass, MockModule("test"))
    mock_platform(hass, "test.config_flow", None)

    with patch.dict(config_entries.HANDLERS):

        class TestFlow(config_entries.ConfigFlow, domain="test"):
            """Test flow."""

            VERSION = 5

            async def async_step_user(self, user_input):
                """Test user step."""
                return self.async_show_form(step_id="user_confirm")

            async def async_step_user_confirm(self, user_input):
                """Test user confirm step."""
                return self.async_show_form(step_id="user_confirm")

            async def async_step_reauth(self, user_input):
                """Test reauth step."""
                return self.async_show_form(step_id="reauth_confirm")

            async def async_step_reauth_confirm(self, user_input):
                """Test reauth confirm step."""
                return self.async_abort(reason="test")

        # Start user flow to assert that reconfigure notification doesn't fire
        await hass.config_entries.flow.async_init(
            "test", context={"source": config_entries.SOURCE_USER}
        )

        await hass.async_block_till_done()
        notifications = async_get_persistent_notifications(hass)
        assert "config_entry_reconfigure" not in notifications

        # Start first reauth flow to assert that reconfigure notification fires
        flow1 = await hass.config_entries.flow.async_init(
            "test", context={"source": config_entries.SOURCE_REAUTH}
        )

        await hass.async_block_till_done()
        notifications = async_get_persistent_notifications(hass)
        assert "config_entry_reconfigure" in notifications

        # Start a second reauth flow so we can finish the first and assert that
        # the reconfigure notification persists until the second one is complete
        flow2 = await hass.config_entries.flow.async_init(
            "test", context={"source": config_entries.SOURCE_REAUTH}
        )

        flow1 = await hass.config_entries.flow.async_configure(flow1["flow_id"], {})
        assert flow1["type"] == data_entry_flow.FlowResultType.ABORT

        await hass.async_block_till_done()
        notifications = async_get_persistent_notifications(hass)
        assert "config_entry_reconfigure" in notifications

        flow2 = await hass.config_entries.flow.async_configure(flow2["flow_id"], {})
        assert flow2["type"] == data_entry_flow.FlowResultType.ABORT

        await hass.async_block_till_done()
        notifications = async_get_persistent_notifications(hass)
        assert "config_entry_reconfigure" not in notifications


async def test_reauth_issue(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test that we create/delete an issue when source is reauth."""
    issue_registry = ir.async_get(hass)
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
    issue = issue_registry.async_get_issue(HA_DOMAIN, issue_id)
    assert issue == ir.IssueEntry(
        active=True,
        breaks_in_ha_version=None,
        created=ANY,
        data={"flow_id": flows[0]["flow_id"]},
        dismissed_version=None,
        domain=HA_DOMAIN,
        is_fixable=False,
        is_persistent=False,
        issue_domain="test",
        issue_id=issue_id,
        learn_more_url=None,
        severity=ir.IssueSeverity.ERROR,
        translation_key="config_entry_reauth",
        translation_placeholders={"name": "test_title"},
    )

    result = await hass.config_entries.flow.async_configure(issue.data["flow_id"], {})
    assert result["type"] == FlowResultType.ABORT
    assert len(issue_registry.issues) == 0


async def test_discovery_notification_not_created(hass: HomeAssistant) -> None:
    """Test that we not create a notification when discovery is aborted."""
    mock_integration(hass, MockModule("test"))
    mock_platform(hass, "test.config_flow", None)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 5

        async def async_step_discovery(self, discovery_info):
            """Test discovery step."""
            return self.async_abort(reason="test")

    with patch.dict(config_entries.HANDLERS, {"test": TestFlow}):
        await hass.config_entries.flow.async_init(
            "test", context={"source": config_entries.SOURCE_DISCOVERY}
        )

    await hass.async_block_till_done()
    state = hass.states.get("persistent_notification.config_entry_discovery")
    assert state is None


async def test_loading_default_config(hass: HomeAssistant) -> None:
    """Test loading the default config."""
    manager = config_entries.ConfigEntries(hass, {})

    with patch("homeassistant.util.json.open", side_effect=FileNotFoundError):
        await manager.async_initialize()

    assert len(manager.async_entries()) == 0


async def test_updating_entry_data(manager: config_entries.ConfigEntries) -> None:
    """Test that we can update an entry data."""
    entry = MockConfigEntry(
        domain="test",
        data={"first": True},
        state=config_entries.ConfigEntryState.SETUP_ERROR,
    )
    entry.add_to_manager(manager)

    assert manager.async_update_entry(entry) is False
    assert entry.data == {"first": True}

    assert manager.async_update_entry(entry, data={"second": True}) is True
    assert entry.data == {"second": True}


async def test_updating_entry_system_options(
    manager: config_entries.ConfigEntries,
) -> None:
    """Test that we can update an entry data."""
    entry = MockConfigEntry(
        domain="test",
        data={"first": True},
        state=config_entries.ConfigEntryState.SETUP_ERROR,
        pref_disable_new_entities=True,
    )
    entry.add_to_manager(manager)

    assert entry.pref_disable_new_entities is True
    assert entry.pref_disable_polling is False

    manager.async_update_entry(
        entry, pref_disable_new_entities=False, pref_disable_polling=True
    )

    assert entry.pref_disable_new_entities is False
    assert entry.pref_disable_polling is True


async def test_update_entry_options_and_trigger_listener(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test that we can update entry options and trigger listener."""
    entry = MockConfigEntry(domain="test", options={"first": True})
    entry.add_to_manager(manager)
    update_listener_calls = []

    async def update_listener(hass, entry):
        """Test function."""
        assert entry.options == {"second": True}
        update_listener_calls.append(None)

    entry.add_update_listener(update_listener)

    assert manager.async_update_entry(entry, options={"second": True}) is True

    await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.options == {"second": True}
    assert len(update_listener_calls) == 1


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

    async def _mock_setup_entry(hass, entry):
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

    async def mock_async_setup(hass, config):
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

    with patch.dict(config_entries.HANDLERS, {"comp": TestFlow}):
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

    class TestFlow:
        """Test flow."""

        @staticmethod
        @callback
        def async_get_options_flow(config_entry):
            """Test options flow."""

    with pytest.raises(config_entries.UnknownEntry):
        await manager.options.async_create_flow(
            "blah", context={"source": "test"}, data=None
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


async def test_entry_unload_succeed(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test that we can unload an entry."""
    entry = MockConfigEntry(domain="comp", state=config_entries.ConfigEntryState.LOADED)
    entry.add_to_hass(hass)

    async_unload_entry = AsyncMock(return_value=True)

    mock_integration(hass, MockModule("comp", async_unload_entry=async_unload_entry))

    assert await manager.async_unload(entry.entry_id)
    assert len(async_unload_entry.mock_calls) == 1
    assert entry.state is config_entries.ConfigEntryState.NOT_LOADED


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

    with patch.dict(config_entries.HANDLERS, {"comp": TestFlow}):
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

    with patch.dict(config_entries.HANDLERS, {"comp": TestFlow}):
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
        patch.dict(config_entries.HANDLERS, {"comp": TestFlow}),
        patch(
            "homeassistant.config_entries.uuid_util.random_uuid_hex",
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
                updates={"host": "1.1.1.1"}, reload_on_update=False
            )

    with (
        patch.dict(config_entries.HANDLERS, {"comp": TestFlow}),
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
                updates=updates, reload_on_update=True
            )

    with (
        patch.dict(config_entries.HANDLERS, {"comp": TestFlow}),
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
    assert len(async_reload.mock_calls) == 1

    # Test we don't reload if entry not started
    updates["host"] = "2.2.2.2"
    entry._async_set_state(hass, config_entries.ConfigEntryState.NOT_LOADED, None)
    with (
        patch.dict(config_entries.HANDLERS, {"comp": TestFlow}),
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

        async def async_step_dhcp(
            self, discovery_info: dhcp.DhcpServiceInfo
        ) -> FlowResult:
            """Test dhcp step."""
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

        async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
            """Test user step."""
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

    # Verify we do not reload from a user source
    with (
        patch.dict(config_entries.HANDLERS, {"comp": TestFlow}),
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
        patch.dict(config_entries.HANDLERS, {"comp": TestFlow}),
        patch(
            "homeassistant.config_entries.ConfigEntries.async_reload"
        ) as async_reload,
    ):
        discovery_result = await manager.flow.async_init(
            "comp",
            context={"source": config_entries.SOURCE_DHCP},
            data=dhcp.DhcpServiceInfo(
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
        patch.dict(config_entries.HANDLERS, {"comp": TestFlow}),
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


async def test_unique_id_in_progress(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test that we abort if there is already a flow in progress with same unique id."""
    mock_integration(hass, MockModule("comp"))
    mock_platform(hass, "comp.config_flow", None)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 1

        async def async_step_user(self, user_input=None):
            """Test user step."""
            await self.async_set_unique_id("mock-unique-id")
            return self.async_show_form(step_id="discovery")

    with patch.dict(config_entries.HANDLERS, {"comp": TestFlow}):
        # Create one to be in progress
        result = await manager.flow.async_init(
            "comp", context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM

        # Will be canceled
        result2 = await manager.flow.async_init(
            "comp", context={"source": config_entries.SOURCE_USER}
        )

    assert result2["type"] == data_entry_flow.FlowResultType.ABORT
    assert result2["reason"] == "already_in_progress"


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

    with patch.dict(config_entries.HANDLERS, {"comp": TestFlow}):
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


async def test_unique_id_ignore(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
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

    with patch.dict(config_entries.HANDLERS, {"comp": TestFlow}):
        # Create one to be in progress
        result = await manager.flow.async_init(
            "comp", context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM

        result2 = await manager.flow.async_init(
            "comp",
            context={"source": config_entries.SOURCE_IGNORE},
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
        patch.dict(config_entries.HANDLERS, {"comp": TestFlow}),
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

    with patch.dict(config_entries.HANDLERS, {"comp": TestFlow, "beer": 5}):
        await manager.flow.async_init(
            "comp", context={"source": config_entries.SOURCE_USER}
        )
        await hass.async_block_till_done()

    assert len(mock_setup_entry.mock_calls) == 1
    p_hass, p_entry = mock_setup_entry.mock_calls[0][1]

    assert p_hass is hass
    assert p_entry.data == {"token": "supersecret"}


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

    with patch.dict(config_entries.HANDLERS, {"comp": TestFlow, "beer": 5}):
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

    with patch.dict(config_entries.HANDLERS, {"comp": TestFlow, "beer": 5}):
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

    with patch.dict(config_entries.HANDLERS, {"comp": TestFlow, "beer": 5}):
        await manager.flow.async_init(
            "comp", context={"source": config_entries.SOURCE_IMPORT}
        )
        await hass.async_block_till_done()

    assert len(mock_setup_entry.mock_calls) == 0


async def test_unignore_step_form(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test that we can ignore flows that are in progress and have a unique ID, then rediscover them."""
    async_setup_entry = AsyncMock(return_value=True)
    mock_integration(hass, MockModule("comp", async_setup_entry=async_setup_entry))
    mock_platform(hass, "comp.config_flow", None)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 1

        async def async_step_unignore(self, user_input):
            """Test unignore step."""
            unique_id = user_input["unique_id"]
            await self.async_set_unique_id(unique_id)
            return self.async_show_form(step_id="discovery")

    with patch.dict(config_entries.HANDLERS, {"comp": TestFlow}):
        result = await manager.flow.async_init(
            "comp",
            context={"source": config_entries.SOURCE_IGNORE},
            data={"unique_id": "mock-unique-id", "title": "Ignored Title"},
        )
        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY

        entry = hass.config_entries.async_entries("comp")[0]
        assert entry.source == "ignore"
        assert entry.unique_id == "mock-unique-id"
        assert entry.domain == "comp"
        assert entry.title == "Ignored Title"

        await manager.async_remove(entry.entry_id)

        # But after a 'tick' the unignore step has run and we can see an active flow again.
        await hass.async_block_till_done()
        assert len(hass.config_entries.flow.async_progress_by_handler("comp")) == 1

        # and still not config entries
        assert len(hass.config_entries.async_entries("comp")) == 0


async def test_unignore_create_entry(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test that we can ignore flows that are in progress and have a unique ID, then rediscover them."""
    async_setup_entry = AsyncMock(return_value=True)
    mock_integration(hass, MockModule("comp", async_setup_entry=async_setup_entry))
    mock_platform(hass, "comp.config_flow", None)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 1

        async def async_step_unignore(self, user_input):
            """Test unignore step."""
            unique_id = user_input["unique_id"]
            await self.async_set_unique_id(unique_id)
            return self.async_create_entry(title="yo", data={})

    with patch.dict(config_entries.HANDLERS, {"comp": TestFlow}):
        result = await manager.flow.async_init(
            "comp",
            context={"source": config_entries.SOURCE_IGNORE},
            data={"unique_id": "mock-unique-id", "title": "Ignored Title"},
        )
        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY

        entry = hass.config_entries.async_entries("comp")[0]
        assert entry.source == "ignore"
        assert entry.unique_id == "mock-unique-id"
        assert entry.domain == "comp"
        assert entry.title == "Ignored Title"

        await manager.async_remove(entry.entry_id)

        # But after a 'tick' the unignore step has run and we can see a config entry.
        await hass.async_block_till_done()
        entry = hass.config_entries.async_entries("comp")[0]
        assert entry.source == config_entries.SOURCE_UNIGNORE
        assert entry.unique_id == "mock-unique-id"
        assert entry.title == "yo"

        # And still no active flow
        assert len(hass.config_entries.flow.async_progress_by_handler("comp")) == 0


async def test_unignore_default_impl(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
) -> None:
    """Test that resdicovery is a no-op by default."""
    async_setup_entry = AsyncMock(return_value=True)
    mock_integration(hass, MockModule("comp", async_setup_entry=async_setup_entry))
    mock_platform(hass, "comp.config_flow", None)

    class TestFlow(config_entries.ConfigFlow):
        """Test flow."""

        VERSION = 1

    with patch.dict(config_entries.HANDLERS, {"comp": TestFlow}):
        result = await manager.flow.async_init(
            "comp",
            context={"source": config_entries.SOURCE_IGNORE},
            data={"unique_id": "mock-unique-id", "title": "Ignored Title"},
        )
        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY

        entry = hass.config_entries.async_entries("comp")[0]
        assert entry.source == "ignore"
        assert entry.unique_id == "mock-unique-id"
        assert entry.domain == "comp"
        assert entry.title == "Ignored Title"

        await manager.async_remove(entry.entry_id)
        await hass.async_block_till_done()

        assert len(hass.config_entries.async_entries("comp")) == 0
        assert len(hass.config_entries.flow.async_progress()) == 0


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

    with patch.dict(config_entries.HANDLERS, {"comp": TestFlow}):
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

        await hass.async_block_till_done()
        notifications = async_get_persistent_notifications(hass)
        assert "config_entry_discovery" not in notifications

        # Let the flow init complete
        pause_discovery.set()

        # When it's complete it should now be visible in async_progress and have triggered
        # discovery notifications
        result = await init_task
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert len(hass.config_entries.flow.async_progress()) == 1

        await hass.async_block_till_done()
        notifications = async_get_persistent_notifications(hass)
        assert "config_entry_discovery" in notifications


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

    with patch.dict(config_entries.HANDLERS, {"comp": TestFlow}):
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

    async def mock_async_setup(hass, config):
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
    with patch.dict(config_entries.HANDLERS, {"comp": TestFlow}):
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

    async def mock_async_setup(hass, config):
        """Mock setup."""
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                "comp",
                context={"source": config_entries.SOURCE_IMPORT},
                data={},
            )
        )
        return True

    async def mock_async_setup_entry(hass, entry):
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

    with patch.dict(config_entries.HANDLERS, {"comp": TestFlow}):
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

    with patch.dict(config_entries.HANDLERS, {"comp": TestFlow}):
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

    with patch.dict(config_entries.HANDLERS, {"comp": TestFlow}):
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

    with patch.dict(config_entries.HANDLERS, {"comp": TestFlow}):
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

    with patch.dict(config_entries.HANDLERS, {"comp": TestFlow}):
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

    with patch.dict(config_entries.HANDLERS, {"comp": TestFlow}):
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

    with patch.dict(config_entries.HANDLERS, {"comp": TestFlow}):
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

    with patch.dict(config_entries.HANDLERS, {"comp": TestFlow}):
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

    for change in (
        {"data": {"second": True, "third": 456}},
        {"data": {"second": True}},
        {"minor_version": 2},
        {"options": {"hello": True}},
        {"pref_disable_new_entities": True},
        {"pref_disable_polling": True},
        {"title": "sometitle"},
        {"unique_id": "abcd1234"},
        {"version": 2},
    ):
        assert manager.async_update_entry(entry, **change) is True
        key = next(iter(change))
        value = next(iter(change.values()))
        assert getattr(entry, key) == value
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

    async def async_setup_entry(hass, entry):
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

    async def async_setup_entry(hass, entry):
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

    async def async_setup_entry(hass, entry):
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

    async def async_setup_entry(hass, entry):
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

    with patch.dict(config_entries.HANDLERS, {"comp": TestFlow, "beer": 5}):
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


async def test_deprecated_disabled_by_str_ctor(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test deprecated str disabled_by constructor enumizes and logs a warning."""
    entry = MockConfigEntry(disabled_by=config_entries.ConfigEntryDisabler.USER.value)
    assert entry.disabled_by is config_entries.ConfigEntryDisabler.USER
    assert " str for config entry disabled_by. This is deprecated " in caplog.text


async def test_deprecated_disabled_by_str_set(
    hass: HomeAssistant,
    manager: config_entries.ConfigEntries,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test deprecated str set disabled_by enumizes and logs a warning."""
    entry = MockConfigEntry(domain="comp")
    entry.add_to_manager(manager)
    hass.config.components.add("comp")
    assert await manager.async_set_disabled_by(
        entry.entry_id, config_entries.ConfigEntryDisabler.USER.value
    )
    assert entry.disabled_by is config_entries.ConfigEntryDisabler.USER
    assert " str for config entry disabled_by. This is deprecated " in caplog.text


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

    async def mock_setup_entry(hass, entry):
        """Mock setting up entry."""
        await asyncio.sleep(0.1)
        return True

    async def mock_unload_entry(hass, entry):
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
        patch.dict(config_entries.HANDLERS, {"comp": TestFlow}),
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

    flow = hass.config_entries.flow
    with patch.object(flow, "async_init", wraps=flow.async_init) as mock_init:
        entry.async_start_reconfigure(
            hass,
            context={"extra_context": "some_extra_context"},
            data={"extra_data": 1234},
        )
        await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["entry_id"] == entry.entry_id
    assert flows[0]["context"]["source"] == config_entries.SOURCE_RECONFIGURE
    assert flows[0]["context"]["title_placeholders"] == {"name": "test_title"}
    assert flows[0]["context"]["extra_context"] == "some_extra_context"

    assert mock_init.call_args.kwargs["data"]["extra_data"] == 1234

    assert entry.entry_id != entry2.entry_id

    # Check that we can't start duplicate reconfigure flows
    entry.async_start_reconfigure(hass, {"extra_context": "some_extra_context"})
    await hass.async_block_till_done()
    assert len(hass.config_entries.flow.async_progress()) == 1

    # Check that we can't start duplicate reconfigure flows when the context is different
    entry.async_start_reconfigure(hass, {"diff": "diff"})
    await hass.async_block_till_done()
    assert len(hass.config_entries.flow.async_progress()) == 1

    # Check that we can start a reconfigure flow for a different entry
    entry2.async_start_reconfigure(hass, {"extra_context": "some_extra_context"})
    await hass.async_block_till_done()
    assert len(hass.config_entries.flow.async_progress()) == 2

    # Abort all existing flows
    for flow in hass.config_entries.flow.async_progress():
        hass.config_entries.flow.async_abort(flow["flow_id"])
    await hass.async_block_till_done()

    # Check that we can't start duplicate reconfigure flows
    # without blocking between flows
    entry.async_start_reconfigure(hass, {"extra_context": "some_extra_context"})
    entry.async_start_reconfigure(hass, {"extra_context": "some_extra_context"})
    entry.async_start_reconfigure(hass, {"extra_context": "some_extra_context"})
    entry.async_start_reconfigure(hass, {"extra_context": "some_extra_context"})
    await hass.async_block_till_done()
    assert len(hass.config_entries.flow.async_progress()) == 1

    # Abort all existing flows
    for flow in hass.config_entries.flow.async_progress():
        hass.config_entries.flow.async_abort(flow["flow_id"])
    await hass.async_block_till_done()

    # Check that we can't start reconfigure flows with active reauth flow
    entry.async_start_reauth(hass, {"extra_context": "some_extra_context"})
    await hass.async_block_till_done()
    assert len(hass.config_entries.flow.async_progress()) == 1
    entry.async_start_reconfigure(hass, {"extra_context": "some_extra_context"})
    await hass.async_block_till_done()
    assert len(hass.config_entries.flow.async_progress()) == 1

    # Abort all existing flows
    for flow in hass.config_entries.flow.async_progress():
        hass.config_entries.flow.async_abort(flow["flow_id"])
    await hass.async_block_till_done()

    # Check that we can't start reauth flows with active reconfigure flow
    entry.async_start_reconfigure(hass, {"extra_context": "some_extra_context"})
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


async def test_options_flow_options_not_mutated() -> None:
    """Test that OptionsFlowWithConfigEntry doesn't mutate entry options."""
    entry = MockConfigEntry(
        domain="test",
        data={"first": True},
        options={"sub_dict": {"1": "one"}, "sub_list": ["one"]},
    )

    options_flow = config_entries.OptionsFlowWithConfigEntry(entry)

    options_flow._options["sub_dict"]["2"] = "two"
    options_flow._options["sub_list"].append("two")

    assert options_flow._options == {
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
            manager.flow.async_init("test", context={"source": "reauth"})
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

        async def async_step_user(self, data):
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
        "title",
        "unique_id",
        "data_vendor",
        "options_vendor",
        "kwargs",
        "calls_entry_load_unload",
    ),
    [
        (
            ("Test", "Updated title"),
            ("1234", "5678"),
            ("data", "data2"),
            ("options", "options2"),
            {},
            (2, 1),
        ),
        (
            ("Test", "Test"),
            ("1234", "1234"),
            ("data", "data"),
            ("options", "options"),
            {},
            (2, 1),
        ),
        (
            ("Test", "Updated title"),
            ("1234", "5678"),
            ("data", "data2"),
            ("options", "options2"),
            {"reload_even_if_entry_is_unchanged": True},
            (2, 1),
        ),
        (
            ("Test", "Test"),
            ("1234", "1234"),
            ("data", "data"),
            ("options", "options"),
            {"reload_even_if_entry_is_unchanged": False},
            (1, 0),
        ),
    ],
    ids=[
        "changed_entry_default",
        "unchanged_entry_default",
        "changed_entry_explicit_reload",
        "changed_entry_no_reload",
    ],
)
async def test_update_entry_and_reload(
    hass: HomeAssistant,
    manager: config_entries.ConfigEntries,
    title: tuple[str, str],
    unique_id: tuple[str, str],
    data_vendor: tuple[str, str],
    options_vendor: tuple[str, str],
    kwargs: dict[str, Any],
    calls_entry_load_unload: tuple[int, int],
) -> None:
    """Test updating an entry and reloading."""
    entry = MockConfigEntry(
        domain="comp",
        unique_id=unique_id[0],
        title=title[0],
        data={"vendor": data_vendor[0]},
        options={"vendor": options_vendor[0]},
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
            return self.async_update_reload_and_abort(
                entry=entry,
                unique_id=unique_id[1],
                title=title[1],
                data={"vendor": data_vendor[1]},
                options={"vendor": options_vendor[1]},
                **kwargs,
            )

    with patch.dict(config_entries.HANDLERS, {"comp": MockFlowHandler}):
        task = await manager.flow.async_init("comp", context={"source": "reauth"})
        await hass.async_block_till_done()

        assert entry.title == title[1]
        assert entry.unique_id == unique_id[1]
        assert entry.data == {"vendor": data_vendor[1]}
        assert entry.options == {"vendor": options_vendor[1]}
        assert entry.state == config_entries.ConfigEntryState.LOADED
        assert task["type"] == FlowResultType.ABORT
        assert task["reason"] == "reauth_successful"
        # Assert entry was reloaded
        assert len(comp.async_setup_entry.mock_calls) == calls_entry_load_unload[0]
        assert len(comp.async_unload_entry.mock_calls) == calls_entry_load_unload[1]


@pytest.mark.parametrize("unique_id", [["blah", "bleh"], {"key": "value"}])
async def test_unhashable_unique_id(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, unique_id: Any
) -> None:
    """Test the ConfigEntryItems user dict handles unhashable unique_id."""
    entries = config_entries.ConfigEntryItems(hass)
    entry = config_entries.ConfigEntry(
        data={},
        domain="test",
        entry_id="mock_id",
        minor_version=1,
        options={},
        source="test",
        title="title",
        unique_id=unique_id,
        version=1,
    )

    entries[entry.entry_id] = entry
    assert (
        "Config entry 'title' from integration test has an invalid unique_id "
        f"'{unique_id!s}'"
    ) in caplog.text

    assert entry.entry_id in entries
    assert entries[entry.entry_id] is entry
    assert entries.get_entry_by_domain_and_unique_id("test", unique_id) == entry
    del entries[entry.entry_id]
    assert not entries
    assert entries.get_entry_by_domain_and_unique_id("test", unique_id) is None


@pytest.mark.parametrize("unique_id", [123])
async def test_hashable_non_string_unique_id(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, unique_id: Any
) -> None:
    """Test the ConfigEntryItems user dict handles hashable non string unique_id."""
    entries = config_entries.ConfigEntryItems(hass)
    entry = config_entries.ConfigEntry(
        data={},
        domain="test",
        entry_id="mock_id",
        minor_version=1,
        options={},
        source="test",
        title="title",
        unique_id=unique_id,
        version=1,
    )

    entries[entry.entry_id] = entry
    assert (
        "Config entry 'title' from integration test has an invalid unique_id"
    ) not in caplog.text

    assert entry.entry_id in entries
    assert entries[entry.entry_id] is entry
    assert entries.get_entry_by_domain_and_unique_id("test", unique_id) == entry
    del entries[entry.entry_id]
    assert not entries
    assert entries.get_entry_by_domain_and_unique_id("test", unique_id) is None


@pytest.mark.parametrize(
    ("source", "user_input", "expected_result"),
    [
        (
            config_entries.SOURCE_IGNORE,
            {"unique_id": "blah", "title": "blah"},
            {"type": data_entry_flow.FlowResultType.CREATE_ENTRY},
        ),
        (
            config_entries.SOURCE_REAUTH,
            None,
            {"type": data_entry_flow.FlowResultType.FORM, "step_id": "reauth_confirm"},
        ),
        (
            config_entries.SOURCE_UNIGNORE,
            None,
            {"type": data_entry_flow.FlowResultType.ABORT, "reason": "not_implemented"},
        ),
        (
            config_entries.SOURCE_USER,
            None,
            {
                "type": data_entry_flow.FlowResultType.ABORT,
                "reason": "single_instance_allowed",
                "translation_domain": HA_DOMAIN,
            },
        ),
    ],
)
async def test_starting_config_flow_on_single_config_entry(
    hass: HomeAssistant,
    manager: config_entries.ConfigEntries,
    source: str,
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
        title="Test",
        data={"vendor": "data"},
        options={"vendor": "options"},
    )
    entry.add_to_hass(hass)
    ignored_entry = MockConfigEntry(
        domain="comp",
        unique_id="2345",
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
            "comp", context={"source": source}, data=user_input
        )

    for key in expected_result:
        assert result[key] == expected_result[key]


@pytest.mark.parametrize(
    ("source", "user_input", "expected_result"),
    [
        (
            config_entries.SOURCE_IGNORE,
            {"unique_id": "blah", "title": "blah"},
            {"type": data_entry_flow.FlowResultType.CREATE_ENTRY},
        ),
        (
            config_entries.SOURCE_REAUTH,
            None,
            {"type": data_entry_flow.FlowResultType.FORM, "step_id": "reauth_confirm"},
        ),
        (
            config_entries.SOURCE_UNIGNORE,
            None,
            {"type": data_entry_flow.FlowResultType.ABORT, "reason": "not_implemented"},
        ),
        (
            config_entries.SOURCE_USER,
            None,
            {"type": data_entry_flow.FlowResultType.ABORT, "reason": "not_implemented"},
        ),
    ],
)
async def test_starting_config_flow_on_single_config_entry_2(
    hass: HomeAssistant,
    manager: config_entries.ConfigEntries,
    source: str,
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
            "comp", context={"source": source}, data=user_input
        )

    for key in expected_result:
        assert result[key] == expected_result[key]


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
        patch.dict(config_entries.HANDLERS, {"comp": TestFlow}),
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
        assert result["translation_domain"] == HA_DOMAIN


async def test_in_progress_get_canceled_when_entry_is_created(
    hass: HomeAssistant, manager: config_entries.ConfigEntries
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

            return self.async_show_form(step_id="user")

    with (
        patch.dict(config_entries.HANDLERS, {"comp": TestFlow}),
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

    setattr(entry, field, "new_value")

    assert (
        f'Detected code that sets "{field}" directly to update a config entry. '
        "This is deprecated and will stop working in Home Assistant 2024.9, "
        "it should be updated to use async_update_entry instead. Please report this issue."
    ) in caplog.text


async def test_updating_non_added_entry_raises(hass: HomeAssistant) -> None:
    """Test updating a non added entry raises UnknownEntry."""
    entry = MockConfigEntry(domain="test")

    with pytest.raises(config_entries.UnknownEntry, match=entry.entry_id):
        hass.config_entries.async_update_entry(entry, unique_id="new_id")


async def test_reload_during_setup(hass: HomeAssistant) -> None:
    """Test reload during setup waits."""
    entry = MockConfigEntry(domain="comp", data={"value": "initial"})
    entry.add_to_hass(hass)

    setup_start_future = hass.loop.create_future()
    setup_finish_future = hass.loop.create_future()
    in_setup = False
    setup_calls = 0

    async def mock_async_setup_entry(hass, entry):
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
