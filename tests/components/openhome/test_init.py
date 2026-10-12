"""Tests for the Openhome integration setup."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.openhome.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from tests.common import MockConfigEntry

HOST = "http://localhost"


async def test_device_uses_shared_session(hass: HomeAssistant) -> None:
    """Test the device is given Home Assistant's shared aiohttp session."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: HOST}, unique_id="uuid")
    entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.openhome.PLATFORMS", []),
        patch("homeassistant.components.openhome.Device", MagicMock()) as mock_device,
    ):
        mock_device.return_value.init = AsyncMock()
        mock_device.return_value.uuid = MagicMock(return_value="uuid")

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    mock_device.assert_called_once_with(HOST, session=async_get_clientsession(hass))
