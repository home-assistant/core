"""Define tests for device-related endpoints."""
from datetime import timedelta
from unittest.mock import patch

from aioflo.errors import RequestError
import pytest

from homeassistant.components.flo.const import DOMAIN as FLO_DOMAIN
from homeassistant.components.flo.device import FloDeviceDataUpdateCoordinator
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.setup import async_setup_component
from homeassistant.util import dt

from .common import TEST_PASSWORD, TEST_USER_ID

from tests.common import async_fire_time_changed


async def test_device(hass, config_entry, aioclient_mock_fixture, aioclient_mock):
    """Test Flo by Moen devices."""
    config_entry.add_to_hass(hass)
    assert await async_setup_component(
        hass, FLO_DOMAIN, {CONF_USERNAME: TEST_USER_ID, CONF_PASSWORD: TEST_PASSWORD}
    )
    await hass.async_block_till_done()
    assert len(hass.data[FLO_DOMAIN][config_entry.entry_id]["devices"]) == 2

    valve: FloDeviceDataUpdateCoordinator = hass.data[FLO_DOMAIN][
        config_entry.entry_id
    ]["devices"][0]
    assert valve.api_client is not None
    assert valve.available
    assert valve.consumption_today == 3.674
    assert valve.current_flow_rate == 0
    assert valve.current_psi == 54.20000076293945
    assert valve.current_system_mode == "home"
    assert valve.target_system_mode == "home"
    assert valve.firmware_version == "6.1.1"
    assert valve.device_type == "flo_device_v2"
    assert valve.id == "98765"
    assert valve.last_heard_from_time == "2020-07-24T12:45:00Z"
    assert valve.location_id == "mmnnoopp"
    assert valve.hass is not None
    assert valve.temperature == 70
    assert valve.mac_address == "111111111111"
    assert valve.model == "flo_device_075_v2"
    assert valve.manufacturer == "Flo by Moen"
    assert valve.device_name == "Smart Water Shutoff"
    assert valve.rssi == -47
    assert valve.pending_info_alerts_count == 0
    assert valve.pending_critical_alerts_count == 0
    assert valve.pending_warning_alerts_count == 2
    assert valve.has_alerts is True
    assert valve.last_known_valve_state == "open"
    assert valve.target_valve_state == "open"

    detector: FloDeviceDataUpdateCoordinator = hass.data[FLO_DOMAIN][
        config_entry.entry_id
    ]["devices"][1]
    assert detector.api_client is not None
    assert detector.available
    assert detector.device_type == "puck_oem"
    assert detector.id == "32839"
    assert detector.last_heard_from_time == "2021-03-07T14:05:00Z"
    assert detector.location_id == "mmnnoopp"
    assert detector.hass is not None
    assert detector.temperature == 61
    assert detector.humidity == 43
    assert detector.water_detected is False
    assert detector.mac_address == "1a2b3c4d5e6f"
    assert detector.model == "puck_v1"
    assert detector.manufacturer == "Flo by Moen"
    assert detector.device_name == "Kitchen Sink"
    assert detector.serial_number == "111111111112"

    call_count = aioclient_mock.call_count

    async_fire_time_changed(hass, dt.utcnow() + timedelta(seconds=90))
    await hass.async_block_till_done()

    assert aioclient_mock.call_count == call_count + 6

    # test error sending device ping
    with patch(
        "homeassistant.components.flo.device.FloDeviceDataUpdateCoordinator.send_presence_ping",
        side_effect=RequestError,
    ):
        with pytest.raises(UpdateFailed):
            await valve._async_update_data()
