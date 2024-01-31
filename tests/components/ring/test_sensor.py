"""The tests for the Ring sensor platform."""
import requests_mock

from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .common import setup_platform

from tests.common import load_fixture

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


async def test_only_chime_devices(
    hass: HomeAssistant, requests_mock: requests_mock.Mocker, caplog
) -> None:
    """Tests the update service works correctly if only chimes are returned."""
    requests_mock.get(
        "https://api.ring.com/clients_api/ring_devices",
        text=load_fixture("chime_devices.json", "ring"),
    )
    await setup_platform(hass, Platform.SENSOR)
    await hass.async_block_till_done()

    await async_setup_component(hass, "homeassistant", {})
    await hass.services.async_call(
        "homeassistant",
        "update_entity",
        {ATTR_ENTITY_ID: ["sensor.downstairs_volume"]},
        blocking=True,
    )
    await hass.async_block_till_done()
    error_logs = [record for record in caplog.records if record.levelname == "ERROR"]
    assert len(error_logs) == 0
