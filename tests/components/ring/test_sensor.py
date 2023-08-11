"""The tests for the Ring sensor platform."""
import requests_mock

from homeassistant.core import HomeAssistant

from .common import setup_platform

WIFI_ENABLED = False


async def test_sensor(hass: HomeAssistant, requests_mock: requests_mock.Mocker) -> None:
    """Test the Ring sensors."""
    await setup_platform(hass, "sensor")

    front_battery_state = hass.states.get("sensor.front_battery")
    assert front_battery_state is not None
    assert front_battery_state.state == "80"

    front_door_battery_state = hass.states.get("sensor.front_door_battery")
    assert front_door_battery_state is not None
    assert front_door_battery_state.state == "100"

    downstairs_volume_state = hass.states.get("sensor.downstairs_volume")
    assert downstairs_volume_state is not None
    assert downstairs_volume_state.state == "2"

    front_door_last_activity_state = hass.states.get("sensor.front_door_last_activity")
    assert front_door_last_activity_state is not None

    downstairs_wifi_signal_strength_state = hass.states.get(
        "sensor.downstairs_wifi_signal_strength"
    )

    if not WIFI_ENABLED:
        return

    assert downstairs_wifi_signal_strength_state is not None
    assert downstairs_wifi_signal_strength_state.state == "-39"

    front_door_wifi_signal_category_state = hass.states.get(
        "sensor.front_door_wifi_signal_category"
    )
    assert front_door_wifi_signal_category_state is not None
    assert front_door_wifi_signal_category_state.state == "good"

    front_door_wifi_signal_strength_state = hass.states.get(
        "sensor.front_door_wifi_signal_strength"
    )
    assert front_door_wifi_signal_strength_state is not None
    assert front_door_wifi_signal_strength_state.state == "-58"
