"""Test DROP sensor entities."""

from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant

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
    config_entry_filter,
    config_entry_hub,
    config_entry_leak,
    config_entry_protection_valve,
    config_entry_pump_controller,
    config_entry_ro_filter,
    config_entry_softener,
)

from tests.common import async_fire_mqtt_message
from tests.typing import MqttMockHAClient


async def test_sensors_hub(hass: HomeAssistant, mqtt_mock: MqttMockHAClient) -> None:
    """Test DROP sensors for hubs."""
    entry = config_entry_hub()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)

    current_flow_sensor_name = "sensor.hub_drop_1_c0ffee_water_flow_rate"
    assert hass.states.get(current_flow_sensor_name).state == STATE_UNKNOWN
    peak_flow_sensor_name = "sensor.hub_drop_1_c0ffee_peak_water_flow_rate_today"
    assert hass.states.get(peak_flow_sensor_name).state == STATE_UNKNOWN
    used_today_sensor_name = "sensor.hub_drop_1_c0ffee_total_water_used_today"
    assert hass.states.get(used_today_sensor_name).state == STATE_UNKNOWN
    average_usage_sensor_name = "sensor.hub_drop_1_c0ffee_average_daily_water_usage"
    assert hass.states.get(average_usage_sensor_name).state == STATE_UNKNOWN
    psi_sensor_name = "sensor.hub_drop_1_c0ffee_current_water_pressure"
    assert hass.states.get(psi_sensor_name).state == STATE_UNKNOWN
    psi_high_sensor_name = "sensor.hub_drop_1_c0ffee_high_water_pressure_today"
    assert hass.states.get(psi_high_sensor_name).state == STATE_UNKNOWN
    psi_low_sensor_name = "sensor.hub_drop_1_c0ffee_low_water_pressure_today"
    assert hass.states.get(psi_low_sensor_name).state == STATE_UNKNOWN
    battery_sensor_name = "sensor.hub_drop_1_c0ffee_battery"
    assert hass.states.get(battery_sensor_name).state == STATE_UNKNOWN

    async_fire_mqtt_message(hass, TEST_DATA_HUB_TOPIC, TEST_DATA_HUB_RESET)
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, TEST_DATA_HUB_TOPIC, TEST_DATA_HUB)
    await hass.async_block_till_done()

    current_flow_sensor = hass.states.get(current_flow_sensor_name)
    assert current_flow_sensor
    assert current_flow_sensor.state == "5.77"

    peak_flow_sensor = hass.states.get(peak_flow_sensor_name)
    assert peak_flow_sensor
    assert peak_flow_sensor.state == "13.8"

    used_today_sensor = hass.states.get(used_today_sensor_name)
    assert used_today_sensor
    assert used_today_sensor.state == "881.13030096168"  # liters

    average_usage_sensor = hass.states.get(average_usage_sensor_name)
    assert average_usage_sensor
    assert average_usage_sensor.state == "287.691295584"  # liters

    psi_sensor = hass.states.get(psi_sensor_name)
    assert psi_sensor
    assert psi_sensor.state == "428.8538854"  # centibars

    psi_high_sensor = hass.states.get(psi_high_sensor_name)
    assert psi_high_sensor
    assert psi_high_sensor.state == "427.474934"  # centibars

    psi_low_sensor = hass.states.get(psi_low_sensor_name)
    assert psi_low_sensor
    assert psi_low_sensor.state == "420.580177"  # centibars

    battery_sensor = hass.states.get(battery_sensor_name)
    assert battery_sensor
    assert battery_sensor.state == "50"


async def test_sensors_leak(hass: HomeAssistant, mqtt_mock: MqttMockHAClient) -> None:
    """Test DROP sensors for leak detectors."""
    entry = config_entry_leak()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)

    battery_sensor_name = "sensor.leak_detector_battery"
    assert hass.states.get(battery_sensor_name).state == STATE_UNKNOWN
    temp_sensor_name = "sensor.leak_detector_temperature"
    assert hass.states.get(temp_sensor_name).state == STATE_UNKNOWN

    async_fire_mqtt_message(hass, TEST_DATA_LEAK_TOPIC, TEST_DATA_LEAK_RESET)
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, TEST_DATA_LEAK_TOPIC, TEST_DATA_LEAK)
    await hass.async_block_till_done()

    battery_sensor = hass.states.get(battery_sensor_name)
    assert battery_sensor
    assert battery_sensor.state == "100"

    temp_sensor = hass.states.get(temp_sensor_name)
    assert temp_sensor
    assert temp_sensor.state == "20.1111111111111"  # °C


async def test_sensors_softener(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test DROP sensors for softeners."""
    entry = config_entry_softener()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)

    battery_sensor_name = "sensor.softener_battery"
    assert hass.states.get(battery_sensor_name).state == STATE_UNKNOWN
    current_flow_sensor_name = "sensor.softener_water_flow_rate"
    assert hass.states.get(current_flow_sensor_name).state == STATE_UNKNOWN
    psi_sensor_name = "sensor.softener_current_water_pressure"
    assert hass.states.get(psi_sensor_name).state == STATE_UNKNOWN
    capacity_sensor_name = "sensor.softener_capacity_remaining"
    assert hass.states.get(capacity_sensor_name).state == STATE_UNKNOWN

    async_fire_mqtt_message(hass, TEST_DATA_SOFTENER_TOPIC, TEST_DATA_SOFTENER_RESET)
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, TEST_DATA_SOFTENER_TOPIC, TEST_DATA_SOFTENER)
    await hass.async_block_till_done()

    battery_sensor = hass.states.get(battery_sensor_name)
    assert battery_sensor
    assert battery_sensor.state == "20"

    current_flow_sensor = hass.states.get(current_flow_sensor_name)
    assert current_flow_sensor
    assert current_flow_sensor.state == "5.0"

    psi_sensor = hass.states.get(psi_sensor_name)
    assert psi_sensor
    assert psi_sensor.state == "348.1852285"  # centibars

    capacity_sensor = hass.states.get(capacity_sensor_name)
    assert capacity_sensor
    assert capacity_sensor.state == "3785.411784"  # liters


async def test_sensors_filter(hass: HomeAssistant, mqtt_mock: MqttMockHAClient) -> None:
    """Test DROP sensors for filters."""
    entry = config_entry_filter()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)

    battery_sensor_name = "sensor.filter_battery"
    assert hass.states.get(battery_sensor_name).state == STATE_UNKNOWN
    current_flow_sensor_name = "sensor.filter_water_flow_rate"
    assert hass.states.get(current_flow_sensor_name).state == STATE_UNKNOWN
    psi_sensor_name = "sensor.filter_current_water_pressure"
    assert hass.states.get(psi_sensor_name).state == STATE_UNKNOWN

    async_fire_mqtt_message(hass, TEST_DATA_FILTER_TOPIC, TEST_DATA_FILTER_RESET)
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, TEST_DATA_FILTER_TOPIC, TEST_DATA_FILTER)
    await hass.async_block_till_done()

    battery_sensor = hass.states.get(battery_sensor_name)
    assert battery_sensor
    assert battery_sensor.state == "12"

    current_flow_sensor = hass.states.get(current_flow_sensor_name)
    assert current_flow_sensor
    assert current_flow_sensor.state == "19.84"

    psi_sensor = hass.states.get(psi_sensor_name)
    assert psi_sensor
    assert psi_sensor.state == "263.3797174"  # centibars


async def test_sensors_protection_valve(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test DROP sensors for protection valves."""
    entry = config_entry_protection_valve()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)

    battery_sensor_name = "sensor.protection_valve_battery"
    assert hass.states.get(battery_sensor_name).state == STATE_UNKNOWN
    current_flow_sensor_name = "sensor.protection_valve_water_flow_rate"
    assert hass.states.get(current_flow_sensor_name).state == STATE_UNKNOWN
    psi_sensor_name = "sensor.protection_valve_current_water_pressure"
    assert hass.states.get(psi_sensor_name).state == STATE_UNKNOWN
    temp_sensor_name = "sensor.protection_valve_temperature"
    assert hass.states.get(temp_sensor_name).state == STATE_UNKNOWN

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
    assert battery_sensor.state == "0"

    current_flow_sensor = hass.states.get(current_flow_sensor_name)
    assert current_flow_sensor
    assert current_flow_sensor.state == "7.1"

    psi_sensor = hass.states.get(psi_sensor_name)
    assert psi_sensor
    assert psi_sensor.state == "422.6486041"  # centibars

    temp_sensor = hass.states.get(temp_sensor_name)
    assert temp_sensor
    assert temp_sensor.state == "21.3888888888889"  # °C


async def test_sensors_pump_controller(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test DROP sensors for pump controllers."""
    entry = config_entry_pump_controller()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)

    current_flow_sensor_name = "sensor.pump_controller_water_flow_rate"
    assert hass.states.get(current_flow_sensor_name).state == STATE_UNKNOWN
    psi_sensor_name = "sensor.pump_controller_current_water_pressure"
    assert hass.states.get(psi_sensor_name).state == STATE_UNKNOWN
    temp_sensor_name = "sensor.pump_controller_temperature"
    assert hass.states.get(temp_sensor_name).state == STATE_UNKNOWN

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
    assert current_flow_sensor.state == "2.2"

    psi_sensor = hass.states.get(psi_sensor_name)
    assert psi_sensor
    assert psi_sensor.state == "428.8538854"  # centibars

    temp_sensor = hass.states.get(temp_sensor_name)
    assert temp_sensor
    assert temp_sensor.state == "20.4444444444444"  # °C


async def test_sensors_ro_filter(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient
) -> None:
    """Test DROP sensors for RO filters."""
    entry = config_entry_ro_filter()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)

    tds_in_sensor_name = "sensor.ro_filter_inlet_tds"
    assert hass.states.get(tds_in_sensor_name).state == STATE_UNKNOWN
    tds_out_sensor_name = "sensor.ro_filter_outlet_tds"
    assert hass.states.get(tds_out_sensor_name).state == STATE_UNKNOWN
    cart1_sensor_name = "sensor.ro_filter_cartridge_1_life_remaining"
    assert hass.states.get(cart1_sensor_name).state == STATE_UNKNOWN
    cart2_sensor_name = "sensor.ro_filter_cartridge_2_life_remaining"
    assert hass.states.get(cart2_sensor_name).state == STATE_UNKNOWN
    cart3_sensor_name = "sensor.ro_filter_cartridge_3_life_remaining"
    assert hass.states.get(cart3_sensor_name).state == STATE_UNKNOWN

    async_fire_mqtt_message(hass, TEST_DATA_RO_FILTER_TOPIC, TEST_DATA_RO_FILTER_RESET)
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, TEST_DATA_RO_FILTER_TOPIC, TEST_DATA_RO_FILTER)
    await hass.async_block_till_done()

    tds_in_sensor = hass.states.get(tds_in_sensor_name)
    assert tds_in_sensor
    assert tds_in_sensor.state == "164"

    tds_out_sensor = hass.states.get(tds_out_sensor_name)
    assert tds_out_sensor
    assert tds_out_sensor.state == "9"

    cart1_sensor = hass.states.get(cart1_sensor_name)
    assert cart1_sensor
    assert cart1_sensor.state == "59"

    cart2_sensor = hass.states.get(cart2_sensor_name)
    assert cart2_sensor
    assert cart2_sensor.state == "80"

    cart3_sensor = hass.states.get(cart3_sensor_name)
    assert cart3_sensor
    assert cart3_sensor.state == "59"
