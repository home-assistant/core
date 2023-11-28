"""Test DROP sensor entities."""
from homeassistant.components.drop.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .common import (
    TEST_DATA_FILTER,
    TEST_DATA_FILTER_TOPIC,
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
    TEST_DATA_SOFTENER,
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

    async_fire_mqtt_message(hass, TEST_DATA_HUB_TOPIC, TEST_DATA_HUB)
    await hass.async_block_till_done()

    currentFlowSensorName = "sensor.hub_drop_1_c0ffee_water_flow_rate"
    currentFlowSensor = hass.states.get(currentFlowSensorName)
    assert currentFlowSensor
    assert currentFlowSensor.state == "5.8"

    peakFlowSensorName = "sensor.hub_drop_1_c0ffee_peak_water_flow_rate_today"
    peakFlowSensor = hass.states.get(peakFlowSensorName)
    assert peakFlowSensor
    assert peakFlowSensor.state == "13.8"

    usedTodaySensorName = "sensor.hub_drop_1_c0ffee_total_water_used_today"
    usedTodaySensor = hass.states.get(usedTodaySensorName)
    assert usedTodaySensor
    assert usedTodaySensor.state == "881.2"  # liters

    averageUsageSensorName = "sensor.hub_drop_1_c0ffee_average_daily_water_usage"
    averageUsageSensor = hass.states.get(averageUsageSensorName)
    assert averageUsageSensor
    assert averageUsageSensor.state == "287.7"  # liters

    psiSensorName = "sensor.hub_drop_1_c0ffee_current_water_pressure"
    psiSensor = hass.states.get(psiSensorName)
    assert psiSensor
    assert psiSensor.state == "428.9"  # liters

    psiHighSensorName = "sensor.hub_drop_1_c0ffee_high_water_pressure_today"
    psiHighSensor = hass.states.get(psiHighSensorName)
    assert psiHighSensor
    assert psiHighSensor.state == "427"  # centibars

    psiLowSensorName = "sensor.hub_drop_1_c0ffee_low_water_pressure_today"
    psiLowSensor = hass.states.get(psiLowSensorName)
    assert psiLowSensor
    assert psiLowSensor.state == "421"  # centibars

    batterySensorName = "sensor.hub_drop_1_c0ffee_battery"
    batterySensor = hass.states.get(batterySensorName)
    assert batterySensor
    assert batterySensor.state == "50"


async def test_sensors_leak(
    hass: HomeAssistant, config_entry_leak, mqtt_mock: MqttMockHAClient
) -> None:
    """Test DROP sensors for leak detectors."""
    config_entry_leak.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    async_fire_mqtt_message(hass, TEST_DATA_LEAK_TOPIC, TEST_DATA_LEAK)
    await hass.async_block_till_done()

    batterySensorName = "sensor.leak_detector_battery"
    batterySensor = hass.states.get(batterySensorName)
    assert batterySensor
    assert batterySensor.state == "100"


async def test_sensors_softener(
    hass: HomeAssistant, config_entry_softener, mqtt_mock: MqttMockHAClient
) -> None:
    """Test DROP sensors for softeners."""
    config_entry_softener.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    async_fire_mqtt_message(hass, TEST_DATA_SOFTENER_TOPIC, TEST_DATA_SOFTENER)
    await hass.async_block_till_done()

    batterySensorName = "sensor.softener_battery"
    batterySensor = hass.states.get(batterySensorName)
    assert batterySensor
    assert batterySensor.state == "20"

    currentFlowSensorName = "sensor.softener_water_flow_rate"
    currentFlowSensor = hass.states.get(currentFlowSensorName)
    assert currentFlowSensor
    assert currentFlowSensor.state == "5.0"

    psiSensorName = "sensor.softener_current_water_pressure"
    psiSensor = hass.states.get(psiSensorName)
    assert psiSensor
    assert psiSensor.state == "6894.1"  # centibars

    capacitySensorName = "sensor.softener_capacity_remaining"
    capacitySensor = hass.states.get(capacitySensorName)
    assert capacitySensor
    assert capacitySensor.state == "3785.4"  # liters


async def test_sensors_filter(
    hass: HomeAssistant, config_entry_filter, mqtt_mock: MqttMockHAClient
) -> None:
    """Test DROP sensors for filters."""
    config_entry_filter.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    async_fire_mqtt_message(hass, TEST_DATA_FILTER_TOPIC, TEST_DATA_FILTER)
    await hass.async_block_till_done()

    batterySensorName = "sensor.filter_battery"
    batterySensor = hass.states.get(batterySensorName)
    assert batterySensor
    assert batterySensor.state == "12"

    currentFlowSensorName = "sensor.filter_water_flow_rate"
    currentFlowSensor = hass.states.get(currentFlowSensorName)
    assert currentFlowSensor
    assert currentFlowSensor.state == "19.8"

    psiSensorName = "sensor.filter_current_water_pressure"
    psiSensor = hass.states.get(psiSensorName)
    assert psiSensor
    assert psiSensor.state == "6894.1"  # centibars


async def test_sensors_protection_valve(
    hass: HomeAssistant, config_entry_protection_valve, mqtt_mock: MqttMockHAClient
) -> None:
    """Test DROP sensors for protection valves."""
    config_entry_protection_valve.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    async_fire_mqtt_message(
        hass, TEST_DATA_PROTECTION_VALVE_TOPIC, TEST_DATA_PROTECTION_VALVE
    )
    await hass.async_block_till_done()

    batterySensorName = "sensor.protection_valve_battery"
    batterySensor = hass.states.get(batterySensorName)
    assert batterySensor
    assert batterySensor.state == "0"

    currentFlowSensorName = "sensor.protection_valve_water_flow_rate"
    currentFlowSensor = hass.states.get(currentFlowSensorName)
    assert currentFlowSensor
    assert currentFlowSensor.state == "7.1"

    psiSensorName = "sensor.protection_valve_current_water_pressure"
    psiSensor = hass.states.get(psiSensorName)
    assert psiSensor
    assert psiSensor.state == "422.6"  # centibars

    tempSensorName = "sensor.protection_valve_temperature_degc"
    tempSensor = hass.states.get(tempSensorName)
    assert tempSensor
    assert tempSensor.state == "21.2"

    tempSensorFName = "sensor.protection_valve_temperature_degf"
    tempSensorF = hass.states.get(tempSensorFName)
    assert tempSensorF
    assert tempSensorF.state == "21.2"  # C


async def test_sensors_pump_controller(
    hass: HomeAssistant, config_entry_pump_controller, mqtt_mock: MqttMockHAClient
) -> None:
    """Test DROP sensors for pump controllers."""
    config_entry_pump_controller.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    async_fire_mqtt_message(
        hass, TEST_DATA_PUMP_CONTROLLER_TOPIC, TEST_DATA_PUMP_CONTROLLER
    )
    await hass.async_block_till_done()

    currentFlowSensorName = "sensor.pump_controller_water_flow_rate"
    currentFlowSensor = hass.states.get(currentFlowSensorName)
    assert currentFlowSensor
    assert currentFlowSensor.state == "2.2"

    psiSensorName = "sensor.pump_controller_current_water_pressure"
    psiSensor = hass.states.get(psiSensorName)
    assert psiSensor
    assert psiSensor.state == "428.9"  # centibars

    tempSensorName = "sensor.pump_controller_temperature_degc"
    tempSensor = hass.states.get(tempSensorName)
    assert tempSensor
    assert tempSensor.state == "24.5"

    tempSensorFName = "sensor.pump_controller_temperature_degf"
    tempSensorF = hass.states.get(tempSensorFName)
    assert tempSensorF
    assert tempSensorF.state == "24.5"  # C


async def test_sensors_ro_filter(
    hass: HomeAssistant, config_entry_ro_filter, mqtt_mock: MqttMockHAClient
) -> None:
    """Test DROP sensors for RO filters."""
    config_entry_ro_filter.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    async_fire_mqtt_message(hass, TEST_DATA_RO_FILTER_TOPIC, TEST_DATA_RO_FILTER)
    await hass.async_block_till_done()

    tdsInSensorName = "sensor.ro_filter_inlet_tds"
    tdsInSensor = hass.states.get(tdsInSensorName)
    assert tdsInSensor
    assert tdsInSensor.state == "164"

    tdsOutSensorName = "sensor.ro_filter_outlet_tds"
    tdsOutSensor = hass.states.get(tdsOutSensorName)
    assert tdsOutSensor
    assert tdsOutSensor.state == "9"

    cart1SensorName = "sensor.ro_filter_cartridge_1_life_remaining"
    cart1Sensor = hass.states.get(cart1SensorName)
    assert cart1Sensor
    assert cart1Sensor.state == "59"

    cart2SensorName = "sensor.ro_filter_cartridge_2_life_remaining"
    cart2Sensor = hass.states.get(cart2SensorName)
    assert cart2Sensor
    assert cart2Sensor.state == "80"

    cart3SensorName = "sensor.ro_filter_cartridge_3_life_remaining"
    cart3Sensor = hass.states.get(cart3SensorName)
    assert cart3Sensor
    assert cart3Sensor.state == "59"
