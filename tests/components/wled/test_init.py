"""Tests for the WLED integration."""
from wled import WLEDConnectionError

from homeassistant.components.wled.const import DOMAIN
from homeassistant.config_entries import ENTRY_STATE_SETUP_RETRY
from homeassistant.core import HomeAssistant

from tests.async_mock import MagicMock, patch
from tests.components.wled import init_integration
from tests.test_util.aiohttp import AiohttpClientMocker


@patch("homeassistant.components.wled.WLED.update", side_effect=WLEDConnectionError)
async def test_config_entry_not_ready(
    mock_update: MagicMock, hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the WLED configuration entry not ready."""
    entry = await init_integration(hass, aioclient_mock)
    assert entry.state == ENTRY_STATE_SETUP_RETRY


async def test_unload_config_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the WLED configuration entry unloading."""
    entry = await init_integration(hass, aioclient_mock)
    assert hass.data[DOMAIN]

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert not hass.data.get(DOMAIN)


async def test_setting_unique_id(hass, aioclient_mock):
    """Test we set unique ID if not set yet."""
    entry = await init_integration(hass, aioclient_mock)

    assert hass.data[DOMAIN]
    assert entry.unique_id == "aabbccddeeff"
