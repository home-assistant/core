"""Test the qingpingiot sensor entities."""

import json
import time

from homeassistant.components.qingpingiot.const import DOMAIN
from homeassistant.const import CONF_MAC, CONF_MODEL, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_mqtt_message
from tests.typing import MqttMockHAClient

MAC = "AABBCCDDEEFF"


async def test_sensors_created_for_cgr1w(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
) -> None:
    """Test that expected sensors are created for CGR1W model."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MAC,
        data={
            CONF_MAC: MAC,
            CONF_MODEL: "cgr1w",
            CONF_NAME: "Test Device",
        },
        title="Test Device",
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_reg = er.async_get(hass)
    entities = er.async_entries_for_config_entry(entity_reg, entry.entry_id)

    entity_keys = {e.unique_id for e in entities}

    # Diagnostic sensors always present
    assert f"{MAC}_status" in entity_keys
    assert f"{MAC}_firmware" in entity_keys
    assert f"{MAC}_mac" in entity_keys

    # CGR1W capabilities: temperature, humidity, co2, pm25, pm10, noise, light, signal_strength
    assert f"{MAC}_temperature" in entity_keys
    assert f"{MAC}_humidity" in entity_keys
    assert f"{MAC}_co2" in entity_keys
    assert f"{MAC}_pm25" in entity_keys
    assert f"{MAC}_pm10" in entity_keys
    assert f"{MAC}_noise" in entity_keys
    assert f"{MAC}_light" in entity_keys
    assert f"{MAC}_signal_strength" in entity_keys


async def test_sensors_created_for_cgs2_with_battery(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
) -> None:
    """Test that battery state sensor is created for CGS2 which has battery capability."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="112233445566",
        data={
            CONF_MAC: "112233445566",
            CONF_MODEL: "cgs2",
            CONF_NAME: "Air Monitor",
        },
        title="Air Monitor",
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_reg = er.async_get(hass)
    entities = er.async_entries_for_config_entry(entity_reg, entry.entry_id)

    entity_keys = {e.unique_id for e in entities}

    assert "112233445566_battery_state" in entity_keys
    assert "112233445566_battery" in entity_keys


async def test_status_sensor_offline_by_default(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
) -> None:
    """Test status sensor shows offline when no data received."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MAC,
        data={
            CONF_MAC: MAC,
            CONF_MODEL: "cgr1w",
            CONF_NAME: "Test Device",
        },
        title="Test Device",
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_device_status")
    assert state is not None
    assert state.state == "offline"


async def test_temperature_sensor_updates_from_json(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
) -> None:
    """Test temperature sensor updates from JSON MQTT message."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="112233445566",
        data={
            CONF_MAC: "112233445566",
            CONF_MODEL: "cgs2",
            CONF_NAME: "Air Monitor",
        },
        title="Air Monitor",
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Send a non-type-17 message first to set online with last_timestamp
    online_payload = json.dumps({"type": 1}).encode()
    async_fire_mqtt_message(hass, "qingping/112233445566/up", online_payload)
    await hass.async_block_till_done()

    # Send JSON sensor data (type 17)
    payload = json.dumps(
        {
            "type": 17,
            "sensorData": [
                {
                    "temperature": 25.3,
                    "humidity": 55.1,
                }
            ],
        }
    ).encode()

    async_fire_mqtt_message(hass, "qingping/112233445566/up", payload)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.air_monitor_temperature")
    assert state is not None
    assert state.state == "25.3"

    state = hass.states.get("sensor.air_monitor_humidity")
    assert state is not None
    assert state.state == "55.1"


async def test_firmware_sensor_updates(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
) -> None:
    """Test firmware sensor updates from MQTT message."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MAC,
        data={
            CONF_MAC: MAC,
            CONF_MODEL: "cgr1w",
            CONF_NAME: "Test Device",
        },
        title="Test Device",
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Set online and send firmware version
    coordinator = entry.runtime_data.coordinator
    coordinator.data["online"] = True
    coordinator.data["last_timestamp"] = int(time.time())
    coordinator.data["firmware_version"] = "1.2.3"
    coordinator.async_set_updated_data(dict(coordinator.data))
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_device_firmware")
    assert state is not None
    assert state.state == "1.2.3"
