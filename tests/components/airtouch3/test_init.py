"""Test AirTouch 3 integration setup."""

from unittest.mock import AsyncMock, patch

from pyairtouch3.airtouch_aircon import Aircon

from homeassistant.components.airtouch3 import PLATFORMS
from homeassistant.components.airtouch3.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

SYSTEM_ID = "35901813"


async def test_async_setup_entry(hass: HomeAssistant) -> None:
    """Test setting up the integration from a config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=SYSTEM_ID, data={CONF_HOST: "1.1.1.1"}
    )
    entry.add_to_hass(hass)
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
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.runtime_data.data.aircon is aircon
    assert entry.unique_id == SYSTEM_ID
    assert entry.state is ConfigEntryState.LOADED
    forward_entry_setups.assert_awaited_once_with(entry, PLATFORMS)


async def test_async_unload_entry(hass: HomeAssistant) -> None:
    """Test unloading the integration."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=SYSTEM_ID, data={CONF_HOST: "1.1.1.1"}
    )
    entry.add_to_hass(hass)
    aircon = Aircon(1)
    aircon.system_id = SYSTEM_ID

    with (
        patch(
            "homeassistant.components.airtouch3.coordinator.async_fetch_airtouch_data",
            AsyncMock(return_value=aircon),
        ),
        patch.object(hass.config_entries, "async_forward_entry_setups", AsyncMock()),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    with patch.object(
        hass.config_entries, "async_unload_platforms", AsyncMock(return_value=True)
    ) as unload_platforms:
        assert await hass.config_entries.async_unload(entry.entry_id)

    unload_platforms.assert_awaited_once_with(entry, PLATFORMS)
