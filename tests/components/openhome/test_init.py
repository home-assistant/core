"""Tests for the Openhome integration setup."""

from unittest.mock import AsyncMock, MagicMock, patch

from openhomedevice.exceptions import OpenhomeConnectionError

from homeassistant.components.openhome.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from tests.common import MockConfigEntry

HOST = "http://localhost"
ENTITY_ID = "media_player.friendly_name"


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


async def setup_integration(
    hass: HomeAssistant, init: AsyncMock, platforms: list[Platform]
) -> MockConfigEntry:
    """Set up the config entry with the given platforms loaded."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: HOST}, unique_id="uuid")
    entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.openhome.PLATFORMS", platforms),
        patch("homeassistant.components.openhome.Device", MagicMock()) as mock_device,
    ):
        device = mock_device.return_value
        device.init = init
        device.uuid = MagicMock(return_value="uuid")
        device.manufacturer = MagicMock(return_value="manufacturer")
        device.model_name = MagicMock(return_value="model_name")
        device.friendly_name = MagicMock(return_value="friendly_name")

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry


async def test_setup_retries_when_device_unreachable(hass: HomeAssistant) -> None:
    """Test setup is retried when the device cannot be reached."""
    init = AsyncMock(side_effect=OpenhomeConnectionError("device unreachable"))

    entry = await setup_integration(hass, init, [])

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test unloading the config entry also unloads its platforms."""
    entry = await setup_integration(hass, AsyncMock(), [Platform.MEDIA_PLAYER])

    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get(ENTITY_ID).state != STATE_UNAVAILABLE

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
