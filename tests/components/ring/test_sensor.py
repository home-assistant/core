"""The tests for the Ring sensor platform."""

import logging

from freezegun.api import FrozenDateTimeFactory
import requests_mock

from homeassistant.components.ring.const import SCAN_INTERVAL
from homeassistant.components.sensor import ATTR_STATE_CLASS, SensorStateClass
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .common import setup_platform

from tests.common import async_fire_time_changed, load_fixture

WIFI_ENABLED = False


async def test_sensor(hass: HomeAssistant, requests_mock: requests_mock.Mocker) -> None:
    """Test the Ring sensors."""
    await setup_platform(hass, "sensor")

    front_battery_state = hass.states.get("sensor.front_battery")
    assert front_battery_state is not None
    assert front_battery_state.state == "80"
    assert (
        front_battery_state.attributes[ATTR_STATE_CLASS] == SensorStateClass.MEASUREMENT
    )

    front_door_battery_state = hass.states.get("sensor.front_door_battery")
    assert front_door_battery_state is not None
    assert front_door_battery_state.state == "100"
    assert (
        front_door_battery_state.attributes[ATTR_STATE_CLASS]
        == SensorStateClass.MEASUREMENT
    )

    downstairs_volume_state = hass.states.get("sensor.downstairs_volume")
    assert downstairs_volume_state is not None
    assert downstairs_volume_state.state == "2"

    downstairs_wifi_signal_strength_state = hass.states.get(
        "sensor.downstairs_wifi_signal_strength"
    )

    ingress_mic_volume_state = hass.states.get("sensor.ingress_mic_volume")
    assert ingress_mic_volume_state.state == "11"

    ingress_doorbell_volume_state = hass.states.get("sensor.ingress_doorbell_volume")
    assert ingress_doorbell_volume_state.state == "8"

    ingress_voice_volume_state = hass.states.get("sensor.ingress_voice_volume")
    assert ingress_voice_volume_state.state == "11"

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


async def test_history(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    requests_mock: requests_mock.Mocker,
) -> None:
    """Test history derived sensors."""
    await setup_platform(hass, Platform.SENSOR)
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(True)

    front_door_last_activity_state = hass.states.get("sensor.front_door_last_activity")
    assert front_door_last_activity_state.state == "2017-03-05T15:03:40+00:00"

    ingress_last_activity_state = hass.states.get("sensor.ingress_last_activity")
    assert ingress_last_activity_state.state == "2024-02-02T11:21:24+00:00"


async def test_only_chime_devices(
    hass: HomeAssistant,
    requests_mock: requests_mock.Mocker,
    freezer: FrozenDateTimeFactory,
    caplog,
) -> None:
    """Tests the update service works correctly if only chimes are returned."""
    await hass.config.async_set_time_zone("UTC")
    freezer.move_to("2021-01-09 12:00:00+00:00")
    requests_mock.get(
        "https://api.ring.com/clients_api/ring_devices",
        text=load_fixture("chime_devices.json", "ring"),
    )
    await setup_platform(hass, Platform.SENSOR)
    await hass.async_block_till_done()
    caplog.set_level(logging.DEBUG)
    caplog.clear()
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert "UnboundLocalError" not in caplog.text  # For issue #109210
