"""Test Senziio sensor entities."""

from unittest.mock import patch

from homeassistant.components.senziio.entity import DOMAIN
from homeassistant.config import async_process_ha_core_config
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_UNIT_SYSTEM,
    CONF_UNIT_SYSTEM_IMPERIAL,
    CONF_UNIT_SYSTEM_METRIC,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant

from . import assert_entity_state_is, when_message_received_is

from tests.common import MockConfigEntry
from tests.typing import MqttMockHAClient

TEMPERATURE_ENTITY = "sensor.temperature"
COUNTER_ENTITY = "sensor.person_counter"
ATM_PRESSURE_ENTITY = "sensor.atmospheric_pressure"
CO2_ENTITY = "sensor.co2"
HUMIDITY_ENTITY = "sensor.humidity"
ILLUMINANCE_ENTITY = "sensor.illuminance"


async def test_loading_sensor_entities(
    hass: HomeAssistant, config_entry: MockConfigEntry, mqtt_mock: MqttMockHAClient
):
    """Test creation of sensor entities."""
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.mqtt.async_wait_for_mqtt_client",
        return_value=True,
    ):
        result = await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert result is True
    assert config_entry.state == ConfigEntryState.LOADED

    # initial entity states should be unknown
    assert_entity_state_is(hass, TEMPERATURE_ENTITY, STATE_UNKNOWN)
    assert_entity_state_is(hass, COUNTER_ENTITY, STATE_UNKNOWN)
    assert_entity_state_is(hass, ATM_PRESSURE_ENTITY, STATE_UNKNOWN)
    assert_entity_state_is(hass, CO2_ENTITY, STATE_UNKNOWN)
    assert_entity_state_is(hass, HUMIDITY_ENTITY, STATE_UNKNOWN)
    assert_entity_state_is(hass, ILLUMINANCE_ENTITY, STATE_UNKNOWN)

    senziio_device = hass.data[DOMAIN][config_entry.entry_id]

    # check temperature entity
    topic_temperature = senziio_device.entity_topic("temperature")

    await set_ha_meassure_units(hass, CONF_UNIT_SYSTEM_IMPERIAL)
    await when_message_received_is(hass, topic_temperature, '{"temperature": 78}')
    assert_entity_state_is(hass, TEMPERATURE_ENTITY, "78")

    await set_ha_meassure_units(hass, CONF_UNIT_SYSTEM_METRIC)
    await when_message_received_is(hass, topic_temperature, '{"temperature": 78}')
    assert_entity_state_is(hass, TEMPERATURE_ENTITY, "26")  # converted to Celsius

    # person counter entity
    topic_counter = senziio_device.entity_topic("person-counter")
    await when_message_received_is(hass, topic_counter, '{"counter": 8}')
    assert_entity_state_is(hass, COUNTER_ENTITY, "8")

    # atmospheric pressure entity
    topic_pressure = senziio_device.entity_topic("atm-pressure")
    await when_message_received_is(hass, topic_pressure, '{"pressure": 1015.5}')
    assert_entity_state_is(hass, ATM_PRESSURE_ENTITY, "1015.5")

    # co2 entity
    topic_co2 = senziio_device.entity_topic("co2")
    await when_message_received_is(hass, topic_co2, '{"co2": 510}')
    assert_entity_state_is(hass, CO2_ENTITY, "510")

    # humidity entity
    topic_humidity = senziio_device.entity_topic("humidity")
    await when_message_received_is(hass, topic_humidity, '{"humidity": 36}')
    assert_entity_state_is(hass, HUMIDITY_ENTITY, "36")

    # illuminance entity
    topic_illuminance = senziio_device.entity_topic("illuminance")
    await when_message_received_is(hass, topic_illuminance, '{"light_level": 180}')
    assert_entity_state_is(hass, ILLUMINANCE_ENTITY, "180")


async def set_ha_meassure_units(hass: HomeAssistant, unit_system: str):
    """Set Home Assistant unit system."""
    await async_process_ha_core_config(hass, {CONF_UNIT_SYSTEM: unit_system})
    await hass.async_block_till_done()
