"""Test DROP sensor entities."""
from homeassistant.components.drop_connect.const import DOMAIN
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .common import (
    TEST_DATA_FILTER,
    TEST_DATA_FILTER_RESET,
    TEST_DATA_FILTER_TOPIC,
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
    TEST_DATA_SOFTENER,
    TEST_DATA_SOFTENER_RESET,
    TEST_DATA_SOFTENER_TOPIC,
)

from tests.common import async_fire_mqtt_message
from tests.typing import MqttMockHAClient


async def test_sensors_hub(
    hass: HomeAssistant, config_entry_hub, mqtt_mock: MqttMockHAClient
) -> None:
    """Test DROP sensors for hubs."""
    config_entry_hub.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    current_flow_sensor_name = "sensor.hub_drop_1_c0ffee_water_flow_rate"
    hass.states.async_set(current_flow_sensor_name, STATE_UNKNOWN)
    peak_flow_sensor_name = "sensor.hub_drop_1_c0ffee_peak_water_flow_rate_today"
    hass.states.async_set(peak_flow_sensor_name, STATE_UNKNOWN)
    used_today_sensor_name = "sensor.hub_drop_1_c0ffee_total_water_used_today"
    hass.states.async_set(used_today_sensor_name, STATE_UNKNOWN)
    average_usage_sensor_name = "sensor.hub_drop_1_c0ffee_average_daily_water_usage"
    hass.states.async_set(average_usage_sensor_name, STATE_UNKNOWN)
    psi_sensor_name = "sensor.hub_drop_1_c0ffee_current_water_pressure"
    hass.states.async_set(psi_sensor_name, STATE_UNKNOWN)
    psi_high_sensor_name = "sensor.hub_drop_1_c0ffee_high_water_pressure_today"
    hass.states.async_set(psi_high_sensor_name, STATE_UNKNOWN)
    psi_low_sensor_name = "sensor.hub_drop_1_c0ffee_low_water_pressure_today"
    hass.states.async_set(psi_low_sensor_name, STATE_UNKNOWN)
    battery_sensor_name = "sensor.hub_drop_1_c0ffee_battery"
    hass.states.async_set(battery_sensor_name, STATE_UNKNOWN)

    async_fire_mqtt_message(hass, TEST_DATA_HUB_TOPIC, TEST_DATA_HUB_RESET)
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, TEST_DATA_HUB_TOPIC, TEST_DATA_HUB)
    await hass.async_block_till_done()

    current_flow_sensor = hass.states.get(current_flow_sensor_name)
    assert current_flow_sensor
    assert round(float(current_flow_sensor.state), 1) == 5.8

    peak_flow_sensor = hass.states.get(peak_flow_sensor_name)
    assert peak_flow_sensor
    assert round(float(peak_flow_sensor.state), 1) == 13.8

    used_today_sensor = hass.states.get(used_today_sensor_name)
    assert used_today_sensor
    assert round(float(used_today_sensor.state), 1) == 881.1  # liters

    average_usage_sensor = hass.states.get(average_usage_sensor_name)
    assert average_usage_sensor
    assert round(float(average_usage_sensor.state), 1) == 287.7  # liters

    psi_sensor = hass.states.get(psi_sensor_name)
    assert psi_sensor
    assert round(float(psi_sensor.state), 1) == 428.9  # centibars

    psi_high_sensor = hass.states.get(psi_high_sensor_name)
    assert psi_high_sensor
    assert round(float(psi_high_sensor.state), 1) == 427.5  # centibars

    psi_low_sensor = hass.states.get(psi_low_sensor_name)
    assert psi_low_sensor
    assert round(float(psi_low_sensor.state), 1) == 420.6  # centibars

    battery_sensor = hass.states.get(battery_sensor_name)
    assert battery_sensor
    assert int(battery_sensor.state) == 50


async def test_sensors_leak(
    hass: HomeAssistant, config_entry_leak, mqtt_mock: MqttMockHAClient
) -> None:
    """Test DROP sensors for leak detectors."""
    config_entry_leak.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    battery_sensor_name = "sensor.leak_detector_battery"
    hass.states.async_set(battery_sensor_name, STATE_UNKNOWN)
    temp_sensor_name = "sensor.leak_detector_temperature"
    hass.states.async_set(temp_sensor_name, STATE_UNKNOWN)

    async_fire_mqtt_message(hass, TEST_DATA_LEAK_TOPIC, TEST_DATA_LEAK_RESET)
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, TEST_DATA_LEAK_TOPIC, TEST_DATA_LEAK)
    await hass.async_block_till_done()

    battery_sensor = hass.states.get(battery_sensor_name)
    assert battery_sensor
    assert int(battery_sensor.state) == 100

    temp_sensor = hass.states.get(temp_sensor_name)
    assert temp_sensor
    assert round(float(temp_sensor.state), 1) == 20.1  # C


async def test_sensors_softener(
    hass: HomeAssistant, config_entry_softener, mqtt_mock: MqttMockHAClient
) -> None:
    """Test DROP sensors for softeners."""
    config_entry_softener.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    battery_sensor_name = "sensor.softener_battery"
    hass.states.async_set(battery_sensor_name, STATE_UNKNOWN)
    current_flow_sensor_name = "sensor.softener_water_flow_rate"
    hass.states.async_set(current_flow_sensor_name, STATE_UNKNOWN)
    psi_sensor_name = "sensor.softener_current_water_pressure"
    hass.states.async_set(psi_sensor_name, STATE_UNKNOWN)
    capacity_sensor_name = "sensor.softener_capacity_remaining"
    hass.states.async_set(capacity_sensor_name, STATE_UNKNOWN)

    async_fire_mqtt_message(hass, TEST_DATA_SOFTENER_TOPIC, TEST_DATA_SOFTENER_RESET)
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, TEST_DATA_SOFTENER_TOPIC, TEST_DATA_SOFTENER)
    await hass.async_block_till_done()

    battery_sensor = hass.states.get(battery_sensor_name)
    assert battery_sensor
    assert int(battery_sensor.state) == 20

    current_flow_sensor = hass.states.get(current_flow_sensor_name)
    assert current_flow_sensor
    assert round(float(current_flow_sensor.state), 1) == 5.0

    psi_sensor = hass.states.get(psi_sensor_name)
    assert psi_sensor
    assert round(float(psi_sensor.state), 1) == 348.2  # centibars

    capacity_sensor = hass.states.get(capacity_sensor_name)
    assert capacity_sensor
    assert round(float(capacity_sensor.state), 1) == 3785.4  # liters


async def test_sensors_filter(
    hass: HomeAssistant, config_entry_filter, mqtt_mock: MqttMockHAClient
) -> None:
    """Test DROP sensors for filters."""
    config_entry_filter.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    battery_sensor_name = "sensor.filter_battery"
    hass.states.async_set(battery_sensor_name, STATE_UNKNOWN)
    current_flow_sensor_name = "sensor.filter_water_flow_rate"
    hass.states.async_set(current_flow_sensor_name, STATE_UNKNOWN)
    psi_sensor_name = "sensor.filter_current_water_pressure"
    hass.states.async_set(psi_sensor_name, STATE_UNKNOWN)

    async_fire_mqtt_message(hass, TEST_DATA_FILTER_TOPIC, TEST_DATA_FILTER_RESET)
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, TEST_DATA_FILTER_TOPIC, TEST_DATA_FILTER)
    await hass.async_block_till_done()

    battery_sensor = hass.states.get(battery_sensor_name)
    assert battery_sensor
    assert round(float(battery_sensor.state), 1) == 12.0

    current_flow_sensor = hass.states.get(current_flow_sensor_name)
    assert current_flow_sensor
    assert round(float(current_flow_sensor.state), 1) == 19.8

    psi_sensor = hass.states.get(psi_sensor_name)
    assert psi_sensor
    assert round(float(psi_sensor.state), 1) == 263.4  # centibars


async def test_sensors_protection_valve(
    hass: HomeAssistant, config_entry_protection_valve, mqtt_mock: MqttMockHAClient
) -> None:
    """Test DROP sensors for protection valves."""
    config_entry_protection_valve.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    battery_sensor_name = "sensor.protection_valve_battery"
    hass.states.async_set(battery_sensor_name, STATE_UNKNOWN)
    current_flow_sensor_name = "sensor.protection_valve_water_flow_rate"
    hass.states.async_set(current_flow_sensor_name, STATE_UNKNOWN)
    psi_sensor_name = "sensor.protection_valve_current_water_pressure"
    hass.states.async_set(psi_sensor_name, STATE_UNKNOWN)
    temp_sensor_name = "sensor.protection_valve_temperature"
    hass.states.async_set(temp_sensor_name, STATE_UNKNOWN)

    async_fire_mqtt_message(
        hass, TEST_DATA_PROTECTION_VALVE_TOPIC, TEST_DATA_PROTECTION_VALVE_RESET
    )
    await hass.async_block_till_done()
    async_fire_mqtt_message(
        hass, TEST_DATA_PROTECTION_VALVE_TOPIC, TEST_DATA_PROTECTION_VALVE
    )
    await hass.async_block_till_done()

    battery_sensor = hass.states.get(battery_sensor_name)
    assert battery_sensor
    assert int(battery_sensor.state) == 0

    current_flow_sensor = hass.states.get(current_flow_sensor_name)
    assert current_flow_sensor
    assert round(float(current_flow_sensor.state), 1) == 7.1

    psi_sensor = hass.states.get(psi_sensor_name)
    assert psi_sensor
    assert round(float(psi_sensor.state), 1) == 422.6  # centibars

    temp_sensor = hass.states.get(temp_sensor_name)
    assert temp_sensor
    assert round(float(temp_sensor.state), 1) == 21.4  # C


async def test_sensors_pump_controller(
    hass: HomeAssistant, config_entry_pump_controller, mqtt_mock: MqttMockHAClient
) -> None:
    """Test DROP sensors for pump controllers."""
    config_entry_pump_controller.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    current_flow_sensor_name = "sensor.pump_controller_water_flow_rate"
    hass.states.async_set(current_flow_sensor_name, STATE_UNKNOWN)
    psi_sensor_name = "sensor.pump_controller_current_water_pressure"
    hass.states.async_set(psi_sensor_name, STATE_UNKNOWN)
    temp_sensor_name = "sensor.pump_controller_temperature"
    hass.states.async_set(temp_sensor_name, STATE_UNKNOWN)

    async_fire_mqtt_message(
        hass, TEST_DATA_PUMP_CONTROLLER_TOPIC, TEST_DATA_PUMP_CONTROLLER_RESET
    )
    await hass.async_block_till_done()
    async_fire_mqtt_message(
        hass, TEST_DATA_PUMP_CONTROLLER_TOPIC, TEST_DATA_PUMP_CONTROLLER
    )
    await hass.async_block_till_done()

    current_flow_sensor = hass.states.get(current_flow_sensor_name)
    assert current_flow_sensor
    assert round(float(current_flow_sensor.state), 1) == 2.2

    psi_sensor = hass.states.get(psi_sensor_name)
    assert psi_sensor
    assert round(float(psi_sensor.state), 1) == 428.9  # centibars

    temp_sensor = hass.states.get(temp_sensor_name)
    assert temp_sensor
    assert round(float(temp_sensor.state), 1) == 20.4  # C


async def test_sensors_ro_filter(
    hass: HomeAssistant, config_entry_ro_filter, mqtt_mock: MqttMockHAClient
) -> None:
    """Test DROP sensors for RO filters."""
    config_entry_ro_filter.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    tds_in_sensor_name = "sensor.ro_filter_inlet_tds"
    hass.states.async_set(tds_in_sensor_name, STATE_UNKNOWN)
    tds_out_sensor_name = "sensor.ro_filter_outlet_tds"
    hass.states.async_set(tds_out_sensor_name, STATE_UNKNOWN)
    cart1_sensor_name = "sensor.ro_filter_cartridge_1_life_remaining"
    hass.states.async_set(cart1_sensor_name, STATE_UNKNOWN)
    cart2_sensor_name = "sensor.ro_filter_cartridge_2_life_remaining"
    hass.states.async_set(cart2_sensor_name, STATE_UNKNOWN)
    cart3_sensor_name = "sensor.ro_filter_cartridge_3_life_remaining"
    hass.states.async_set(cart3_sensor_name, STATE_UNKNOWN)

    async_fire_mqtt_message(hass, TEST_DATA_RO_FILTER_TOPIC, TEST_DATA_RO_FILTER_RESET)
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, TEST_DATA_RO_FILTER_TOPIC, TEST_DATA_RO_FILTER)
    await hass.async_block_till_done()

    tds_in_sensor = hass.states.get(tds_in_sensor_name)
    assert tds_in_sensor
    assert int(tds_in_sensor.state) == 164

    tds_out_sensor = hass.states.get(tds_out_sensor_name)
    assert tds_out_sensor
    assert int(tds_out_sensor.state) == 9

    cart1_sensor = hass.states.get(cart1_sensor_name)
    assert cart1_sensor
    assert int(cart1_sensor.state) == 59

    cart2_sensor = hass.states.get(cart2_sensor_name)
    assert cart2_sensor
    assert int(cart2_sensor.state) == 80

    cart3_sensor = hass.states.get(cart3_sensor_name)
    assert cart3_sensor
    assert int(cart3_sensor.state) == 59
