"""Test the qingping_mqtt sensors."""

from datetime import timedelta
from unittest.mock import patch

from homeassistant.components.qingping_mqtt.const import DOMAIN, MQTT_TOPIC_PREFIX
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_MAC,
    CONF_MODEL,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceRegistry,
    format_mac,
)
from homeassistant.util import dt as dt_util

from . import MQTT_MAC, MQTT_TLV_PAYLOAD

from tests.common import (
    MockConfigEntry,
    async_fire_mqtt_message,
    async_fire_time_changed,
)
from tests.typing import MqttMockHAClient

MQTT_TEMPERATURE_ENTITY = "sensor.qingping_indoor_environment_monitor_temperature"
MQTT_HUMIDITY_ENTITY = "sensor.qingping_indoor_environment_monitor_humidity"


async def _async_setup_mqtt_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Set up a config entry for an MQTT connected device."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MQTT_MAC,
        data={CONF_MAC: MQTT_MAC, CONF_MODEL: "cgr1w"},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_mqtt_sensors(
    hass: HomeAssistant,
    device_registry: DeviceRegistry,
    mqtt_mock: MqttMockHAClient,
) -> None:
    """Test MQTT sensors are created and update from device messages."""
    entry = await _async_setup_mqtt_entry(hass)

    temperature = hass.states.get(MQTT_TEMPERATURE_ENTITY)
    assert temperature is not None
    assert temperature.state == STATE_UNKNOWN
    assert temperature.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfTemperature.CELSIUS

    async_fire_mqtt_message(
        hass, f"{MQTT_TOPIC_PREFIX}/{MQTT_MAC}/up", MQTT_TLV_PAYLOAD
    )
    await hass.async_block_till_done()

    temperature = hass.states.get(MQTT_TEMPERATURE_ENTITY)
    assert temperature.state == "25.8"
    humidity = hass.states.get(MQTT_HUMIDITY_ENTITY)
    assert humidity.state == "65.3"

    device = device_registry.async_get_device_by_connection(
        (CONNECTION_NETWORK_MAC, format_mac(MQTT_MAC)), entry.entry_id
    )
    assert device is not None
    assert device.sw_version == "1.3.6"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(MQTT_TEMPERATURE_ENTITY).state == STATE_UNAVAILABLE


async def test_mqtt_sensors_offline(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test MQTT sensors become unavailable when the device stops publishing."""
    with patch(
        "homeassistant.components.qingping_mqtt.coordinator.OFFLINE_TIMEOUT",
        0,
    ):
        entry = await _async_setup_mqtt_entry(hass)

        async_fire_mqtt_message(
            hass, f"{MQTT_TOPIC_PREFIX}/{MQTT_MAC}/up", MQTT_TLV_PAYLOAD
        )
        await hass.async_block_till_done()
        assert hass.states.get(MQTT_TEMPERATURE_ENTITY).state == "25.8"

        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=90))
        await hass.async_block_till_done()
        assert hass.states.get(MQTT_TEMPERATURE_ENTITY).state == STATE_UNAVAILABLE

        # A later check while already offline does not retrigger an update
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=90))
        await hass.async_block_till_done()
        assert hass.states.get(MQTT_TEMPERATURE_ENTITY).state == STATE_UNAVAILABLE

        async_fire_mqtt_message(
            hass, f"{MQTT_TOPIC_PREFIX}/{MQTT_MAC}/up", MQTT_TLV_PAYLOAD
        )
        await hass.async_block_till_done()
        assert hass.states.get(MQTT_TEMPERATURE_ENTITY).state == "25.8"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
