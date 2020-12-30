"""Tests for the WLED integration."""
from wled import WLEDConnectionError

from homeassistant.components.wled import wled_get_title_base_for_config_entry
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


async def test_base_title_no_device(hass, aioclient_mock) -> None:
    """Test if the base title will be based on the config entry if no device exists."""
    # Do not pass the DeviceRegistry, so no device is created
    entry = await init_integration(hass, aioclient_mock, skip_setup=True)

    base_title = await wled_get_title_base_for_config_entry(entry, hass)

    assert base_title == "WLED Mock Config Entry"


async def test_base_title_with_device(hass, aioclient_mock, device_registry) -> None:
    """Test if the base title will be based on the device name with both ConfigEntry and Device existing."""
    entry = await init_integration(
        hass, aioclient_mock, skip_setup=True, device_registry=device_registry
    )

    base_title = await wled_get_title_base_for_config_entry(entry, hass)

    assert base_title == "WLED RGB Light"


async def test_base_title_with_device_and_name_by_user(
    hass, aioclient_mock, device_registry
) -> None:
    """Test if the base title will be based on the user defined device name with both ConfigEntry and Device existing."""
    entry = await init_integration(
        hass, aioclient_mock, skip_setup=True, device_registry=device_registry
    )

    device = device_registry.async_get_device({(DOMAIN, entry.data.get("mac"))}, set())
    device = device_registry.async_update_device(
        device.id, name_by_user="WLED RGB Light User Name"
    )

    base_title = await wled_get_title_base_for_config_entry(entry, hass)

    assert base_title == "WLED RGB Light User Name"
