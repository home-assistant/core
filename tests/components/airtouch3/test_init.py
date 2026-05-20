"""Test AirTouch 3 integration setup."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from pyairtouch3.airtouch_aircon import Aircon

from homeassistant.components.airtouch3 import (
    PLATFORMS,
    _async_migrate_entity_unique_ids,
    async_setup,
    async_setup_entry,
    async_unload_entry,
)
from homeassistant.components.airtouch3.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry

SYSTEM_ID = "35901813"


async def test_async_setup_starts_discovery(hass: HomeAssistant) -> None:
    """Test setting up the integration starts discovery."""
    with (
        patch(
            "homeassistant.components.airtouch3.async_discover_devices",
            AsyncMock(return_value=[]),
        ) as discover_devices,
        patch("homeassistant.components.airtouch3.async_trigger_discovery") as trigger,
    ):
        assert await async_setup(hass, {})
        await hass.async_block_till_done()

    discover_devices.assert_awaited_once()
    trigger.assert_called_once_with(hass, [])


async def test_async_setup_entry(hass: HomeAssistant) -> None:
    """Test setting up the integration from a config entry."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "1.1.1.1"})
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.SETUP_IN_PROGRESS)
    aircon = Aircon(1)
    aircon.system_id = SYSTEM_ID

    with (
        patch(
            "homeassistant.components.airtouch3.coordinator.async_fetch_airtouch_data",
            AsyncMock(return_value=aircon),
        ),
        patch.object(
            hass.config_entries, "async_forward_entry_setups", AsyncMock()
        ) as forward_entry_setups,
    ):
        assert await async_setup_entry(hass, entry)

    assert entry.runtime_data.data is aircon
    assert entry.unique_id == SYSTEM_ID
    forward_entry_setups.assert_awaited_once_with(entry, PLATFORMS)


async def test_migrate_entity_unique_ids_no_data(hass: HomeAssistant) -> None:
    """Test migration does nothing when the entry has no runtime data."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "1.1.1.1"})
    entry.add_to_hass(hass)
    entry.runtime_data = SimpleNamespace(data=None)

    _async_migrate_entity_unique_ids(hass, entry, "1.1.1.1", SYSTEM_ID)


async def test_migrate_entity_unique_ids(hass: HomeAssistant) -> None:
    """Test host-based entity unique IDs migrate to the stable system id."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "1.1.1.1"})
    entry.add_to_hass(hass)
    aircon = Aircon(1)
    entry.runtime_data = SimpleNamespace(data=aircon)
    ent_reg = er.async_get(hass)
    entity_entry = ent_reg.async_get_or_create(
        Platform.CLIMATE,
        DOMAIN,
        "1.1.1.1_airtouch_ac_1",
        suggested_object_id="airtouch_3",
        config_entry=entry,
    )

    _async_migrate_entity_unique_ids(hass, entry, "1.1.1.1", SYSTEM_ID)

    assert (
        ent_reg.async_get(entity_entry.entity_id).unique_id
        == f"{SYSTEM_ID}_airtouch_ac_1"
    )


async def test_async_unload_entry(hass: HomeAssistant) -> None:
    """Test unloading the integration."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "1.1.1.1"})

    with patch.object(
        hass.config_entries, "async_unload_platforms", AsyncMock(return_value=True)
    ) as unload_platforms:
        assert await async_unload_entry(hass, entry)

    unload_platforms.assert_awaited_once_with(entry, PLATFORMS)
