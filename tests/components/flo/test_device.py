"""Define tests for device-related endpoints."""
from homeassistant.components.flo.const import DOMAIN as FLO_DOMAIN
from homeassistant.components.flo.device import FloDevice
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.setup import async_setup_component

from .common import TEST_PASSWORD, TEST_USER_ID


async def test_device(hass, config_entry):
    """Test Flo by Moen device."""
    config_entry.add_to_hass(hass)
    assert await async_setup_component(
        hass, FLO_DOMAIN, {CONF_USERNAME: TEST_USER_ID, CONF_PASSWORD: TEST_PASSWORD}
    )
    await hass.async_block_till_done()
    assert len(hass.data[FLO_DOMAIN]["devices"]) == 1

    device: FloDevice = hass.data[FLO_DOMAIN]["devices"][0]
    assert device.api_client is not None
    assert device.available
    assert device.consumption_today == 3.674
    assert device.current_flow_rate == 0
    assert device.current_psi == 54.20000076293945
    assert device.current_system_mode == "home"
    assert device.firmware_version == "6.1.1"
    assert device.device_type == "flo_device_v2"
    assert device.id == "xxxxx"
    assert device.last_heard_from_time == "2020-07-24T12:45:00Z"
    assert device.location_id == "xxxxx"
    assert device.hass is not None
    assert device.temperature == 70
    assert device.mac_address == "111111111111"
    assert device.model == "flo_device_075_v2"
    assert device.manufacturer == "Flo by Moen"
    assert device.name == "Flo by Moen flo_device_075_v2"
    assert device.rssi == -47
