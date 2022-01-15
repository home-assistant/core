"""Tests for the coordinator."""
from homeassistant.components import tradfri

from .common import setup_integration
from .test_fan import mock_fan


async def test_coordinator_data(hass, mock_gateway, mock_api_factory):
    """Test that device coordinators are setup."""
    fan_device = mock_fan(test_state={"fan_speed": 10})
    # Enable as we add more platforms
    """
    switch_device = mock_switch(
        test_state={
            "state": True,
        }
    )
    cover_device = mock_cover(test_state={"current_cover_position": 40})
    light_device = mock_light(
        test_features={
            "can_set_dimmer": True,
            "can_set_color": True,
            "can_set_temp": True,
        },
        test_state={
            "state": True,
            "dimmer": 100,
            "color_temp": 250,
            "hsb_xy_color": (100, 100, 100, 100, 100),
        },
    )
    sensor_device = mock_sensor(state_name="battery_level", state_value="50")
    """
    mock_gateway.mock_devices.append(fan_device)

    # mock_gateway.mock_devices.append(switch_device)
    # mock_gateway.mock_devices.append(cover_device)
    # mock_gateway.mock_devices.append(light_device)
    # mock_gateway.mock_devices.append(sensor_device)

    entry = await setup_integration(hass)

    coordinator_list = [
        device_coordinator.device
        for device_coordinator in hass.data[tradfri.DOMAIN][entry.entry_id][
            tradfri.COORDINATOR
        ][tradfri.COORDINATOR_LIST]
    ]

    assert fan_device in coordinator_list
