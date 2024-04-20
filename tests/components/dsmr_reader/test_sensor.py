"""Tests for DSMR Reader sensor."""

from collections.abc import Callable
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.dsmr_reader.const import DOMAIN
from homeassistant.components.dsmr_reader.definitions import (
    DSMRReaderSensorEntityDescription,
)
from homeassistant.components.dsmr_reader.sensor import DSMRSensor
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_mqtt_message
from tests.typing import MqttMockHAClient


@pytest.mark.parametrize(
    ("payload", "state_function", "expected_native_value"),
    [
        # Test when message payload is empty
        ("", None, None),
        # Test when entity_description.state is not None
        ("test_payload", lambda x: x, "test_payload"),
        # Test when entity_description.state is None
        ("test_payload", None, "test_payload"),
    ],
)
@patch("homeassistant.components.dsmr_reader.sensor.mqtt.async_subscribe")
async def test_dsmr_sensor_async_added_to_hass(
    mock_mqtt_subscribe,
    hass: HomeAssistant,
    payload: str,
    state_function: Callable,
    expected_native_value: str,
) -> None:
    """Test the sensor via a typical unit test."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title=DOMAIN,
        options={},
        entry_id="TEST_ENTRY_ID",
        unique_id="UNIQUE_TEST_ID",
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    mock_mqtt_subscribe.side_effect = lambda hass, key, callback, qos: callback(message)
    message = MagicMock()
    message.payload = payload

    description = DSMRReaderSensorEntityDescription(
        key="DSMR_TEST_KEY",
        name="DSMR_TEST_NAME",
        state=state_function,
    )
    sensor = DSMRSensor(description, config_entry)
    sensor.hass = hass
    await sensor.async_added_to_hass()
    assert sensor.native_value == expected_native_value


async def test_dsmr_sensor_mqtt(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test the DSMRSensor class, via an emluated MQTT message."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title=DOMAIN,
        options={},
        entry_id="TEST_ENTRY_ID",
        unique_id="UNIQUE_TEST_ID",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    electricity_delivered_1 = "sensor.dsmr_reading_electricity_delivered_1"
    assert hass.states.get(electricity_delivered_1).state == STATE_UNKNOWN

    electricity_delivered_2 = "sensor.dsmr_reading_electricity_delivered_2"
    assert hass.states.get(electricity_delivered_2).state == STATE_UNKNOWN

    async_fire_mqtt_message(hass, "dsmr/reading/electricity_delivered_1", "1050.39")
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, "dsmr/reading/electricity_delivered_2", "2001.12")
    await hass.async_block_till_done()

    assert hass.states.get(electricity_delivered_1).state == "1050.39"
    assert hass.states.get(electricity_delivered_2).state == "2001.12"
