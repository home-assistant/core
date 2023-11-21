"""Test DROP binary sensor entities."""

from homeassistant.components.drop.const import DOMAIN as DROP_DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .common import (
    TEST_DATA_HUB,
    TEST_DATA_HUB_TOPIC,
    TEST_DATA_LEAK,
    TEST_DATA_LEAK_TOPIC,
    TEST_DATA_PROTECTION_VALVE,
    TEST_DATA_PROTECTION_VALVE_TOPIC,
    TEST_DATA_PUMP_CONTROLLER,
    TEST_DATA_PUMP_CONTROLLER_TOPIC,
    TEST_DATA_RO_FILTER,
    TEST_DATA_RO_FILTER_TOPIC,
    TEST_DATA_SALT,
    TEST_DATA_SALT_TOPIC,
    TEST_DATA_SOFTENER,
    TEST_DATA_SOFTENER_TOPIC,
)

from tests.common import async_fire_mqtt_message
from tests.typing import MqttMockHAClient


async def test_binary_sensors_hub(
    hass: HomeAssistant, config_entry_hub, mqtt_mock: MqttMockHAClient
) -> None:
    """Test DROP binary sensors for hubs."""
    config_entry_hub.add_to_hass(hass)
    assert await async_setup_component(hass, DROP_DOMAIN, {})
    await hass.async_block_till_done()

    pendingNotificationsSensorName = (
        "binary_sensor.hub_drop_1_c0ffee_notification_unread"
    )
    leakSensorName = "binary_sensor.hub_drop_1_c0ffee_leak_detected"
    pendingNotifications = hass.states.get(pendingNotificationsSensorName)
    assert pendingNotifications.state == STATE_UNKNOWN

    leak = hass.states.get(leakSensorName)
    assert leak.state == STATE_UNKNOWN

    async_fire_mqtt_message(hass, TEST_DATA_HUB_TOPIC, TEST_DATA_HUB)
    await hass.async_block_till_done()

    pendingNotifications = hass.states.get(pendingNotificationsSensorName)
    assert pendingNotifications.state == STATE_ON

    leak = hass.states.get(leakSensorName)
    assert leak.state == STATE_OFF


async def test_binary_sensors_salt(
    hass: HomeAssistant, config_entry_salt, mqtt_mock: MqttMockHAClient
) -> None:
    """Test DROP binary sensors for salt sensors."""
    config_entry_salt.add_to_hass(hass)
    assert await async_setup_component(hass, DROP_DOMAIN, {})
    await hass.async_block_till_done()

    saltSensorName = "binary_sensor.salt_sensor_salt_low"
    salt = hass.states.get(saltSensorName)
    assert salt.state == STATE_UNKNOWN

    async_fire_mqtt_message(hass, TEST_DATA_SALT_TOPIC, TEST_DATA_SALT)
    await hass.async_block_till_done()

    salt = hass.states.get(saltSensorName)
    assert salt.state == STATE_OFF


async def test_binary_sensors_leak(
    hass: HomeAssistant, config_entry_leak, mqtt_mock: MqttMockHAClient
) -> None:
    """Test DROP binary sensors for leak detectors."""
    config_entry_leak.add_to_hass(hass)
    assert await async_setup_component(hass, DROP_DOMAIN, {})
    await hass.async_block_till_done()

    leakSensorName = "binary_sensor.leak_detector_leak_detected"
    leak = hass.states.get(leakSensorName)
    assert leak.state == STATE_UNKNOWN

    async_fire_mqtt_message(hass, TEST_DATA_LEAK_TOPIC, TEST_DATA_LEAK)
    await hass.async_block_till_done()

    leak = hass.states.get(leakSensorName)
    assert leak.state == STATE_ON


async def test_binary_sensors_softener(
    hass: HomeAssistant, config_entry_softener, mqtt_mock: MqttMockHAClient
) -> None:
    """Test DROP binary sensors for softeners."""
    config_entry_softener.add_to_hass(hass)
    assert await async_setup_component(hass, DROP_DOMAIN, {})
    await hass.async_block_till_done()

    reserveInUseSensorName = "binary_sensor.softener_reserve_capacity_in_use"
    reserveInUse = hass.states.get(reserveInUseSensorName)
    assert reserveInUse.state == STATE_UNKNOWN

    async_fire_mqtt_message(hass, TEST_DATA_SOFTENER_TOPIC, TEST_DATA_SOFTENER)
    await hass.async_block_till_done()

    reserveInUse = hass.states.get(reserveInUseSensorName)
    assert reserveInUse.state == STATE_ON


async def test_binary_sensors_protection_valve(
    hass: HomeAssistant, config_entry_protection_valve, mqtt_mock: MqttMockHAClient
) -> None:
    """Test DROP binary sensors for protection valves."""
    config_entry_protection_valve.add_to_hass(hass)
    assert await async_setup_component(hass, DROP_DOMAIN, {})
    await hass.async_block_till_done()

    leakSensorName = "binary_sensor.protection_valve_leak_detected"
    leak = hass.states.get(leakSensorName)
    assert leak.state == STATE_UNKNOWN

    async_fire_mqtt_message(
        hass, TEST_DATA_PROTECTION_VALVE_TOPIC, TEST_DATA_PROTECTION_VALVE
    )
    await hass.async_block_till_done()

    leak = hass.states.get(leakSensorName)
    assert leak.state == STATE_ON


async def test_binary_sensors_pump_controller(
    hass: HomeAssistant, config_entry_pump_controller, mqtt_mock: MqttMockHAClient
) -> None:
    """Test DROP binary sensors for pump controllers."""
    config_entry_pump_controller.add_to_hass(hass)
    assert await async_setup_component(hass, DROP_DOMAIN, {})
    await hass.async_block_till_done()

    leakSensorName = "binary_sensor.pump_controller_leak_detected"
    leak = hass.states.get(leakSensorName)
    assert leak.state == STATE_UNKNOWN
    pumpSensorName = "binary_sensor.pump_controller_pump_status"
    pump = hass.states.get(pumpSensorName)
    assert pump.state == STATE_UNKNOWN

    async_fire_mqtt_message(
        hass, TEST_DATA_PUMP_CONTROLLER_TOPIC, TEST_DATA_PUMP_CONTROLLER
    )
    await hass.async_block_till_done()

    leak = hass.states.get(leakSensorName)
    assert leak.state == STATE_ON
    pump = hass.states.get(pumpSensorName)
    assert pump.state == STATE_ON


async def test_binary_sensors_ro_filter(
    hass: HomeAssistant, config_entry_ro_filter, mqtt_mock: MqttMockHAClient
) -> None:
    """Test DROP binary sensors for RO filters."""
    config_entry_ro_filter.add_to_hass(hass)
    assert await async_setup_component(hass, DROP_DOMAIN, {})
    await hass.async_block_till_done()

    leakSensorName = "binary_sensor.ro_filter_leak_detected"
    leak = hass.states.get(leakSensorName)
    assert leak.state == STATE_UNKNOWN

    async_fire_mqtt_message(hass, TEST_DATA_RO_FILTER_TOPIC, TEST_DATA_RO_FILTER)
    await hass.async_block_till_done()

    leak = hass.states.get(leakSensorName)
    assert leak.state == STATE_ON
