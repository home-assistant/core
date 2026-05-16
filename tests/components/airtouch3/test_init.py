"""Test AirTouch 3 integration setup."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.airtouch3 import (
    PLATFORMS,
    async_setup_entry,
    async_unload_entry,
)
from homeassistant.components.airtouch3.comms.airtouch_aircon import Aircon
from homeassistant.components.airtouch3.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_async_setup_entry(hass: HomeAssistant) -> None:
    """Test setting up the integration from a config entry."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "1.1.1.1"})
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.SETUP_IN_PROGRESS)
    aircon = Aircon(1)

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
    forward_entry_setups.assert_awaited_once_with(entry, PLATFORMS)


async def test_async_unload_entry(hass: HomeAssistant) -> None:
    """Test unloading the integration."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "1.1.1.1"})

    with patch.object(
        hass.config_entries, "async_unload_platforms", AsyncMock(return_value=True)
    ) as unload_platforms:
        assert await async_unload_entry(hass, entry)

    unload_platforms.assert_awaited_once_with(entry, PLATFORMS)
