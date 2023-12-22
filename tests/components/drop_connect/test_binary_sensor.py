"""Test DROP binary sensor entities."""

from homeassistant.components.drop_connect.const import DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

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
)

from tests.common import async_fire_mqtt_message
from tests.typing import MqttMockHAClient


async def test_binary_sensors_hub(
    hass: HomeAssistant, config_entry_hub, mqtt_mock: MqttMockHAClient
) -> None:
    """Test DROP binary sensors for hubs."""
    config_entry_hub.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    pending_notifications_sensor_name = (
        "binary_sensor.hub_drop_1_c0ffee_notification_unread"
    )
    hass.states.async_set(pending_notifications_sensor_name, STATE_UNKNOWN)
    leak_sensor_name = "binary_sensor.hub_drop_1_c0ffee_leak_detected"
    hass.states.async_set(leak_sensor_name, STATE_UNKNOWN)

    async_fire_mqtt_message(hass, TEST_DATA_HUB_TOPIC, TEST_DATA_HUB_RESET)
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, TEST_DATA_HUB_TOPIC, TEST_DATA_HUB)
    await hass.async_block_till_done()

    pending_notifications = hass.states.get(pending_notifications_sensor_name)
    assert pending_notifications.state == STATE_ON

    leak = hass.states.get(leak_sensor_name)
    assert leak.state == STATE_OFF


async def test_binary_sensors_salt(
    hass: HomeAssistant, config_entry_salt, mqtt_mock: MqttMockHAClient
) -> None:
    """Test DROP binary sensors for salt sensors."""
    config_entry_salt.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    salt_sensor_name = "binary_sensor.salt_sensor_salt_low"
    hass.states.async_set(salt_sensor_name, STATE_UNKNOWN)

    async_fire_mqtt_message(hass, TEST_DATA_SALT_TOPIC, TEST_DATA_SALT_RESET)
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, TEST_DATA_SALT_TOPIC, TEST_DATA_SALT)
    await hass.async_block_till_done()

    salt = hass.states.get(salt_sensor_name)
    assert salt.state == STATE_ON


async def test_binary_sensors_leak(
    hass: HomeAssistant, config_entry_leak, mqtt_mock: MqttMockHAClient
) -> None:
    """Test DROP binary sensors for leak detectors."""
    config_entry_leak.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    leak_sensor_name = "binary_sensor.leak_detector_leak_detected"
    hass.states.async_set(leak_sensor_name, STATE_UNKNOWN)

    async_fire_mqtt_message(hass, TEST_DATA_LEAK_TOPIC, TEST_DATA_LEAK_RESET)
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, TEST_DATA_LEAK_TOPIC, TEST_DATA_LEAK)
    await hass.async_block_till_done()

    leak = hass.states.get(leak_sensor_name)
    assert leak.state == STATE_ON


async def test_binary_sensors_softener(
    hass: HomeAssistant, config_entry_softener, mqtt_mock: MqttMockHAClient
) -> None:
    """Test DROP binary sensors for softeners."""
    config_entry_softener.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    reserve_in_use_sensor_name = "binary_sensor.softener_reserve_capacity_in_use"
    hass.states.async_set(reserve_in_use_sensor_name, STATE_UNKNOWN)

    async_fire_mqtt_message(hass, TEST_DATA_SOFTENER_TOPIC, TEST_DATA_SOFTENER_RESET)
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, TEST_DATA_SOFTENER_TOPIC, TEST_DATA_SOFTENER)
    await hass.async_block_till_done()

    reserve_in_use = hass.states.get(reserve_in_use_sensor_name)
    assert reserve_in_use.state == STATE_ON


async def test_binary_sensors_protection_valve(
    hass: HomeAssistant, config_entry_protection_valve, mqtt_mock: MqttMockHAClient
) -> None:
    """Test DROP binary sensors for protection valves."""
    config_entry_protection_valve.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    leak_sensor_name = "binary_sensor.protection_valve_leak_detected"
    hass.states.async_set(leak_sensor_name, STATE_UNKNOWN)

    async_fire_mqtt_message(
        hass, TEST_DATA_PROTECTION_VALVE_TOPIC, TEST_DATA_PROTECTION_VALVE_RESET
    )
    await hass.async_block_till_done()
    async_fire_mqtt_message(
        hass, TEST_DATA_PROTECTION_VALVE_TOPIC, TEST_DATA_PROTECTION_VALVE
    )
    await hass.async_block_till_done()

    leak = hass.states.get(leak_sensor_name)
    assert leak.state == STATE_ON


async def test_binary_sensors_pump_controller(
    hass: HomeAssistant, config_entry_pump_controller, mqtt_mock: MqttMockHAClient
) -> None:
    """Test DROP binary sensors for pump controllers."""
    config_entry_pump_controller.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    leak_sensor_name = "binary_sensor.pump_controller_leak_detected"
    hass.states.async_set(leak_sensor_name, STATE_UNKNOWN)
    pump_sensor_name = "binary_sensor.pump_controller_pump_status"
    hass.states.async_set(pump_sensor_name, STATE_UNKNOWN)

    async_fire_mqtt_message(
        hass, TEST_DATA_PUMP_CONTROLLER_TOPIC, TEST_DATA_PUMP_CONTROLLER_RESET
    )
    await hass.async_block_till_done()
    async_fire_mqtt_message(
        hass, TEST_DATA_PUMP_CONTROLLER_TOPIC, TEST_DATA_PUMP_CONTROLLER
    )
    await hass.async_block_till_done()

    leak = hass.states.get(leak_sensor_name)
    assert leak.state == STATE_ON
    pump = hass.states.get(pump_sensor_name)
    assert pump.state == STATE_ON


async def test_binary_sensors_ro_filter(
    hass: HomeAssistant, config_entry_ro_filter, mqtt_mock: MqttMockHAClient
) -> None:
    """Test DROP binary sensors for RO filters."""
    config_entry_ro_filter.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    leak_sensor_name = "binary_sensor.ro_filter_leak_detected"
    hass.states.async_set(leak_sensor_name, STATE_UNKNOWN)

    async_fire_mqtt_message(hass, TEST_DATA_RO_FILTER_TOPIC, TEST_DATA_RO_FILTER_RESET)
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, TEST_DATA_RO_FILTER_TOPIC, TEST_DATA_RO_FILTER)
    await hass.async_block_till_done()

    leak = hass.states.get(leak_sensor_name)
    assert leak.state == STATE_ON
