"""Test DROP binary sensor entities."""

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from .common import (
    TEST_DATA_HUB,
    TEST_DATA_HUB_RESET,
    TEST_DATA_HUB_TOPIC,
    TEST_DATA_LEAK,
    TEST_DATA_LEAK_RESET,
    TEST_DATA_LEAK_TOPIC,
    TEST_DATA_PROTECTION_VALVE,
    TEST_DATA_PROTECTION_VALVE_RESET,
    TEST_DATA_PROTECTION_VALVE_TOPIC,
    TEST_DATA_PUMP_CONTROLLER,
    TEST_DATA_PUMP_CONTROLLER_RESET,
    TEST_DATA_PUMP_CONTROLLER_TOPIC,
    TEST_DATA_RO_FILTER,
    TEST_DATA_RO_FILTER_RESET,
    TEST_DATA_RO_FILTER_TOPIC,
    TEST_DATA_SALT,
    TEST_DATA_SALT_RESET,
    TEST_DATA_SALT_TOPIC,
    TEST_DATA_SOFTENER,
    TEST_DATA_SOFTENER_RESET,
    TEST_DATA_SOFTENER_TOPIC,
    config_entry_hub,
    config_entry_leak,
    config_entry_protection_valve,
    config_entry_pump_controller,
    config_entry_ro_filter,
    config_entry_salt,
    config_entry_softener,
)

from tests.common import async_fire_mqtt_message
from tests.typing import MqttMockHAClient


async def test_binary_sensors_hub(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test DROP binary sensors for hubs."""
    entry = config_entry_hub()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)

    pending_notifications_sensor_name = (
        "binary_sensor.hub_drop_1_c0ffee_notification_unread"
    )
    assert hass.states.get(pending_notifications_sensor_name).state == STATE_OFF
    leak_sensor_name = "binary_sensor.hub_drop_1_c0ffee_leak_detected"
    assert hass.states.get(leak_sensor_name).state == STATE_OFF

    async_fire_mqtt_message(hass, TEST_DATA_HUB_TOPIC, TEST_DATA_HUB_RESET)
    await hass.async_block_till_done()
    assert hass.states.get(pending_notifications_sensor_name).state == STATE_OFF
    assert hass.states.get(leak_sensor_name).state == STATE_OFF

    async_fire_mqtt_message(hass, TEST_DATA_HUB_TOPIC, TEST_DATA_HUB)
    await hass.async_block_till_done()
    assert hass.states.get(pending_notifications_sensor_name).state == STATE_ON
    assert hass.states.get(leak_sensor_name).state == STATE_OFF


async def test_binary_sensors_salt(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test DROP binary sensors for salt sensors."""
    entry = config_entry_salt()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)

    salt_sensor_name = "binary_sensor.salt_sensor_salt_low"
    assert hass.states.get(salt_sensor_name).state == STATE_OFF

    async_fire_mqtt_message(hass, TEST_DATA_SALT_TOPIC, TEST_DATA_SALT_RESET)
    await hass.async_block_till_done()
    assert hass.states.get(salt_sensor_name).state == STATE_OFF

    async_fire_mqtt_message(hass, TEST_DATA_SALT_TOPIC, TEST_DATA_SALT)
    await hass.async_block_till_done()
    assert hass.states.get(salt_sensor_name).state == STATE_ON


async def test_binary_sensors_leak(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test DROP binary sensors for leak detectors."""
    entry = config_entry_leak()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)

    leak_sensor_name = "binary_sensor.leak_detector_leak_detected"
    assert hass.states.get(leak_sensor_name).state == STATE_OFF

    async_fire_mqtt_message(hass, TEST_DATA_LEAK_TOPIC, TEST_DATA_LEAK_RESET)
    await hass.async_block_till_done()
    assert hass.states.get(leak_sensor_name).state == STATE_OFF

    async_fire_mqtt_message(hass, TEST_DATA_LEAK_TOPIC, TEST_DATA_LEAK)
    await hass.async_block_till_done()
    assert hass.states.get(leak_sensor_name).state == STATE_ON


async def test_binary_sensors_softener(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test DROP binary sensors for softeners."""
    entry = config_entry_softener()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)

    reserve_in_use_sensor_name = "binary_sensor.softener_reserve_capacity_in_use"
    assert hass.states.get(reserve_in_use_sensor_name).state == STATE_OFF

    async_fire_mqtt_message(hass, TEST_DATA_SOFTENER_TOPIC, TEST_DATA_SOFTENER_RESET)
    await hass.async_block_till_done()
    assert hass.states.get(reserve_in_use_sensor_name).state == STATE_OFF

    async_fire_mqtt_message(hass, TEST_DATA_SOFTENER_TOPIC, TEST_DATA_SOFTENER)
    await hass.async_block_till_done()
    assert hass.states.get(reserve_in_use_sensor_name).state == STATE_ON


async def test_binary_sensors_protection_valve(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test DROP binary sensors for protection valves."""
    entry = config_entry_protection_valve()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)

    leak_sensor_name = "binary_sensor.protection_valve_leak_detected"
    assert hass.states.get(leak_sensor_name).state == STATE_OFF

    async_fire_mqtt_message(
        hass, TEST_DATA_PROTECTION_VALVE_TOPIC, TEST_DATA_PROTECTION_VALVE_RESET
    )
    await hass.async_block_till_done()
    assert hass.states.get(leak_sensor_name).state == STATE_OFF

    async_fire_mqtt_message(
        hass, TEST_DATA_PROTECTION_VALVE_TOPIC, TEST_DATA_PROTECTION_VALVE
    )
    await hass.async_block_till_done()
    assert hass.states.get(leak_sensor_name).state == STATE_ON


async def test_binary_sensors_pump_controller(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test DROP binary sensors for pump controllers."""
    entry = config_entry_pump_controller()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)

    leak_sensor_name = "binary_sensor.pump_controller_leak_detected"
    assert hass.states.get(leak_sensor_name).state == STATE_OFF
    pump_sensor_name = "binary_sensor.pump_controller_pump_status"
    assert hass.states.get(pump_sensor_name).state == STATE_OFF

    async_fire_mqtt_message(
        hass, TEST_DATA_PUMP_CONTROLLER_TOPIC, TEST_DATA_PUMP_CONTROLLER_RESET
    )
    await hass.async_block_till_done()
    assert hass.states.get(leak_sensor_name).state == STATE_OFF
    assert hass.states.get(pump_sensor_name).state == STATE_OFF

    async_fire_mqtt_message(
        hass, TEST_DATA_PUMP_CONTROLLER_TOPIC, TEST_DATA_PUMP_CONTROLLER
    )
    await hass.async_block_till_done()
    assert hass.states.get(leak_sensor_name).state == STATE_ON
    assert hass.states.get(pump_sensor_name).state == STATE_ON


async def test_binary_sensors_ro_filter(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test DROP binary sensors for RO filters."""
    entry = config_entry_ro_filter()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)

    leak_sensor_name = "binary_sensor.ro_filter_leak_detected"
    assert hass.states.get(leak_sensor_name).state == STATE_OFF

    async_fire_mqtt_message(hass, TEST_DATA_RO_FILTER_TOPIC, TEST_DATA_RO_FILTER_RESET)
    await hass.async_block_till_done()
    assert hass.states.get(leak_sensor_name).state == STATE_OFF

    async_fire_mqtt_message(hass, TEST_DATA_RO_FILTER_TOPIC, TEST_DATA_RO_FILTER)
    await hass.async_block_till_done()
    assert hass.states.get(leak_sensor_name).state == STATE_ON
