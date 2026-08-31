"""Test the Qingping sensors."""

from datetime import timedelta
import time
from unittest.mock import patch

from homeassistant.components.bluetooth import (
    FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS,
)
from homeassistant.components.qingping.const import (
    CONF_CONNECTION_TYPE,
    CONNECTION_MQTT,
    DOMAIN,
)
from homeassistant.components.sensor import ATTR_STATE_CLASS
from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
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

from . import LIGHT_SERVICE_INFO, MQTT_MAC, MQTT_TLV_PAYLOAD, NO_DATA_SERVICE_INFO

from tests.common import (
    MockConfigEntry,
    async_fire_mqtt_message,
    async_fire_time_changed,
)
from tests.components.bluetooth import (
    inject_bluetooth_service_info,
    patch_all_discovered_devices,
    patch_bluetooth_time,
)
from tests.typing import MqttMockHAClient


async def test_sensors(hass: HomeAssistant) -> None:
    """Test setting up creates the sensors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="aa:bb:cc:dd:ee:ff",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all("sensor")) == 0
    inject_bluetooth_service_info(hass, LIGHT_SERVICE_INFO)
    await hass.async_block_till_done()
    assert len(hass.states.async_all("sensor")) == 1

    lux_sensor = hass.states.get("sensor.motion_light_eeff_illuminance")
    lux_sensor_attrs = lux_sensor.attributes
    assert lux_sensor.state == "13"
    assert lux_sensor_attrs[ATTR_FRIENDLY_NAME] == "Motion & Light EEFF Illuminance"
    assert lux_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "lx"
    assert lux_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_binary_sensor_restore_state(hass: HomeAssistant) -> None:
    """Test setting up creates the binary sensors and restoring state."""
    start_monotonic = time.monotonic()
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="aa:bb:cc:dd:ee:ff",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all("sensor")) == 0
    inject_bluetooth_service_info(hass, LIGHT_SERVICE_INFO)
    await hass.async_block_till_done()
    assert len(hass.states.async_all("sensor")) == 1

    lux_sensor = hass.states.get("sensor.motion_light_eeff_illuminance")
    lux_sensor_attrs = lux_sensor.attributes
    assert lux_sensor.state == "13"
    assert lux_sensor_attrs[ATTR_FRIENDLY_NAME] == "Motion & Light EEFF Illuminance"
    assert lux_sensor_attrs[ATTR_UNIT_OF_MEASUREMENT] == "lx"
    assert lux_sensor_attrs[ATTR_STATE_CLASS] == "measurement"

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    # Fastforward time without BLE advertisements
    monotonic_now = start_monotonic + FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS + 1

    with (
        patch_bluetooth_time(
            monotonic_now,
        ),
        patch_all_discovered_devices([]),
    ):
        async_fire_time_changed(
            hass,
            dt_util.utcnow()
            + timedelta(seconds=FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS + 1),
        )
        await hass.async_block_till_done()

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Device is no longer available because its not in range

    lux_sensor = hass.states.get("sensor.motion_light_eeff_illuminance")
    assert lux_sensor.state == STATE_UNAVAILABLE

    # Device is back in range

    inject_bluetooth_service_info(hass, NO_DATA_SERVICE_INFO)

    lux_sensor = hass.states.get("sensor.motion_light_eeff_illuminance")
    assert lux_sensor.state == "13"


MQTT_TEMPERATURE_ENTITY = "sensor.qingping_indoor_environment_monitor_temperature"
MQTT_HUMIDITY_ENTITY = "sensor.qingping_indoor_environment_monitor_humidity"


async def _async_setup_mqtt_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Set up a config entry for an MQTT connected device."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MQTT_MAC,
        data={
            CONF_CONNECTION_TYPE: CONNECTION_MQTT,
            CONF_MAC: MQTT_MAC,
            CONF_MODEL: "cgr1w",
        },
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

    async_fire_mqtt_message(hass, f"qingping/{MQTT_MAC}/up", MQTT_TLV_PAYLOAD)
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


async def test_mqtt_sensors_offline(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test MQTT sensors become unavailable when the device stops publishing."""
    with patch(
        "homeassistant.components.qingping.coordinator.OFFLINE_TIMEOUT",
        0,
    ):
        await _async_setup_mqtt_entry(hass)

        async_fire_mqtt_message(hass, f"qingping/{MQTT_MAC}/up", MQTT_TLV_PAYLOAD)
        await hass.async_block_till_done()
        assert hass.states.get(MQTT_TEMPERATURE_ENTITY).state == "25.8"

        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=90))
        await hass.async_block_till_done()
        assert hass.states.get(MQTT_TEMPERATURE_ENTITY).state == STATE_UNAVAILABLE

        async_fire_mqtt_message(hass, f"qingping/{MQTT_MAC}/up", MQTT_TLV_PAYLOAD)
        await hass.async_block_till_done()
        assert hass.states.get(MQTT_TEMPERATURE_ENTITY).state == "25.8"
