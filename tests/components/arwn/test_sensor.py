"""Tests for the ARWN sensor platform."""

import json

import pytest

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import async_fire_mqtt_message
from tests.typing import MqttMockHAClient


async def test_temperature_sensor_created(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
) -> None:
    """Test that a temperature MQTT message creates a sensor entity."""
    assert await async_setup_component(
        hass,
        "sensor",
        {"sensor": {"platform": "arwn"}},
    )
    await hass.async_block_till_done()

    async_fire_mqtt_message(
        hass,
        "arwn/temperature/BackYard",
        json.dumps({"temp": 22.5, "units": "C"}),
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.backyard_temperature")
    assert state is not None
    assert state.state == "22.5"
    assert state.attributes["device_class"] == SensorDeviceClass.TEMPERATURE
    assert state.attributes["state_class"] == SensorStateClass.MEASUREMENT


async def test_temperature_sensor_updates(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
) -> None:
    """Test that a second MQTT message updates an existing sensor."""
    assert await async_setup_component(
        hass,
        "sensor",
        {"sensor": {"platform": "arwn"}},
    )
    await hass.async_block_till_done()

    async_fire_mqtt_message(
        hass,
        "arwn/temperature/BackYard",
        json.dumps({"temp": 22.5, "units": "C"}),
    )
    await hass.async_block_till_done()

    async_fire_mqtt_message(
        hass,
        "arwn/temperature/BackYard",
        json.dumps({"temp": 25.0, "units": "C"}),
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.backyard_temperature")
    assert state is not None
    assert state.state == "25.0"


async def test_rain_rate_exposed_total_not(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
) -> None:
    """Test rain/rate is created but rain/total is suppressed (expose=False)."""
    assert await async_setup_component(
        hass,
        "sensor",
        {"sensor": {"platform": "arwn"}},
    )
    await hass.async_block_till_done()

    async_fire_mqtt_message(
        hass,
        "arwn/rain",
        json.dumps({"total": 1.2, "rate": 0.05, "units": "in"}),
    )
    await hass.async_block_till_done()

    assert hass.states.get("sensor.rainfall_rate") is not None
    assert hass.states.get("sensor.total_rainfall") is None


@pytest.mark.parametrize(
    ("topic", "payload", "entity_id", "expected_state"),
    [
        pytest.param(
            "arwn/temperature/BackYard",
            {"temp": 22.5, "units": "C"},
            "sensor.backyard_temperature",
            "22.5",
            id="temperature",
        ),
        pytest.param(
            "arwn/barometer",
            {"pressure": 1013.25, "units": "mb"},
            "sensor.barometer",
            "1013.25",
            id="barometer",
        ),
        pytest.param(
            "arwn/moisture/FrontLawn",
            {"moisture": 45.2, "units": "%"},
            "sensor.frontlawn_moisture",
            "45.2",
            id="moisture",
        ),
    ],
)
async def test_single_reading_sensor_created(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    topic: str,
    payload: dict,
    entity_id: str,
    expected_state: str,
) -> None:
    """Test single-reading sensor types are discovered and populated."""
    assert await async_setup_component(
        hass,
        "sensor",
        {"sensor": {"platform": "arwn"}},
    )
    await hass.async_block_till_done()

    async_fire_mqtt_message(hass, topic, json.dumps(payload))
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected_state


async def test_wind_sensors_created(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
) -> None:
    """Test wind message creates speed, gust, and direction sensors."""
    assert await async_setup_component(
        hass,
        "sensor",
        {"sensor": {"platform": "arwn"}},
    )
    await hass.async_block_till_done()

    async_fire_mqtt_message(
        hass,
        "arwn/wind",
        json.dumps({"speed": 12.3, "gust": 18.0, "direction": 270, "units": "mph"}),
    )
    await hass.async_block_till_done()

    assert hass.states.get("sensor.wind_speed") is not None
    assert hass.states.get("sensor.wind_gust") is not None
    assert hass.states.get("sensor.wind_direction") is not None
    assert hass.states.get("sensor.wind_direction").state == "270"


async def test_unknown_topic_ignored(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
) -> None:
    """Test that messages on unknown topics do not create sensors."""
    assert await async_setup_component(
        hass,
        "sensor",
        {"sensor": {"platform": "arwn"}},
    )
    await hass.async_block_till_done()

    async_fire_mqtt_message(
        hass, "arwn/unknown_domain", json.dumps({"value": 1.0})
    )
    await hass.async_block_till_done()

    assert hass.data.get("arwn") is None
