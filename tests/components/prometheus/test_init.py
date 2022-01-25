"""The tests for the Prometheus exporter."""
from dataclasses import dataclass
import datetime
from http import HTTPStatus
import unittest.mock as mock

import prometheus_client
import pytest

from homeassistant.components import climate, counter, humidifier, lock, sensor
from homeassistant.components.demo.binary_sensor import DemoBinarySensor
from homeassistant.components.demo.light import DemoLight
from homeassistant.components.demo.number import DemoNumber
from homeassistant.components.demo.sensor import DemoSensor
import homeassistant.components.prometheus as prometheus
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONTENT_TYPE_TEXT_PLAIN,
    DEGREE,
    ENERGY_KILO_WATT_HOUR,
    EVENT_STATE_CHANGED,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import split_entity_id
from homeassistant.helpers import entity_registry
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

PROMETHEUS_PATH = "homeassistant.components.prometheus"


@dataclass
class FilterTest:
    """Class for capturing a filter test."""

    id: str
    should_pass: bool


async def setup_prometheus_client(hass, hass_client, namespace):
    """Initialize an hass_client with Prometheus component."""
    # Reset registry
    prometheus_client.REGISTRY = prometheus_client.CollectorRegistry(auto_describe=True)
    prometheus_client.ProcessCollector(registry=prometheus_client.REGISTRY)
    prometheus_client.PlatformCollector(registry=prometheus_client.REGISTRY)
    prometheus_client.GCCollector(registry=prometheus_client.REGISTRY)

    config = {}
    if namespace is not None:
        config[prometheus.CONF_PROM_NAMESPACE] = namespace
    assert await async_setup_component(
        hass, prometheus.DOMAIN, {prometheus.DOMAIN: config}
    )
    await hass.async_block_till_done()

    return await hass_client()


async def generate_latest_metrics(client):
    """Generate the latest metrics and transform the body."""
    resp = await client.get(prometheus.API_ENDPOINT)
    assert resp.status == HTTPStatus.OK
    assert resp.headers["content-type"] == CONTENT_TYPE_TEXT_PLAIN
    body = await resp.text()
    body = body.split("\n")

    assert len(body) > 3

    return body


async def test_view_empty_namespace(hass, hass_client):
    """Test prometheus metrics view."""
    client = await setup_prometheus_client(hass, hass_client, "")

    sensor2 = DemoSensor(
        None,
        "Radio Energy",
        14,
        SensorDeviceClass.POWER,
        None,
        ENERGY_KILO_WATT_HOUR,
        None,
    )
    sensor2.hass = hass
    sensor2.entity_id = "sensor.radio_energy"
    with mock.patch(
        "homeassistant.util.dt.utcnow",
        return_value=datetime.datetime(1970, 1, 2, tzinfo=dt_util.UTC),
    ):
        await sensor2.async_update_ha_state()

    await hass.async_block_till_done()
    body = await generate_latest_metrics(client)

    assert "# HELP python_info Python platform information" in body
    assert (
        "# HELP python_gc_objects_collected_total "
        "Objects collected during gc" in body
    )

    assert (
        'entity_available{domain="sensor",'
        'entity="sensor.radio_energy",'
        'friendly_name="Radio Energy"} 1.0' in body
    )

    assert (
        'last_updated_time_seconds{domain="sensor",'
        'entity="sensor.radio_energy",'
        'friendly_name="Radio Energy"} 86400.0' in body
    )


async def test_view_default_namespace(hass, hass_client):
    """Test prometheus metrics view."""
    assert await async_setup_component(
        hass,
        "conversation",
        {},
    )

    client = await setup_prometheus_client(hass, hass_client, None)

    assert await async_setup_component(
        hass, sensor.DOMAIN, {"sensor": [{"platform": "demo"}]}
    )
    await hass.async_block_till_done()

    body = await generate_latest_metrics(client)

    assert "# HELP python_info Python platform information" in body
    assert (
        "# HELP python_gc_objects_collected_total "
        "Objects collected during gc" in body
    )

    assert (
        'homeassistant_sensor_temperature_celsius{domain="sensor",'
        'entity="sensor.outside_temperature",'
        'friendly_name="Outside Temperature"} 15.6' in body
    )


async def test_sensor_unit(hass, hass_client):
    """Test prometheus metrics for sensors with a unit."""
    client = await setup_prometheus_client(hass, hass_client, "")

    sensor1 = DemoSensor(
        None, "Television Energy", 74, None, None, ENERGY_KILO_WATT_HOUR, None
    )
    sensor1.hass = hass
    sensor1.entity_id = "sensor.television_energy"
    await sensor1.async_update_ha_state()

    sensor2 = DemoSensor(
        None,
        "Radio Energy",
        14,
        SensorDeviceClass.POWER,
        None,
        ENERGY_KILO_WATT_HOUR,
        None,
    )
    sensor2.hass = hass
    sensor2.entity_id = "sensor.radio_energy"
    with mock.patch(
        "homeassistant.util.dt.utcnow",
        return_value=datetime.datetime(1970, 1, 2, tzinfo=dt_util.UTC),
    ):
        await sensor2.async_update_ha_state()

    sensor3 = DemoSensor(
        None,
        "Electricity price",
        0.123,
        None,
        None,
        f"SEK/{ENERGY_KILO_WATT_HOUR}",
        None,
    )
    sensor3.hass = hass
    sensor3.entity_id = "sensor.electricity_price"
    await sensor3.async_update_ha_state()

    sensor4 = DemoSensor(None, "Wind Direction", 25, None, None, DEGREE, None)
    sensor4.hass = hass
    sensor4.entity_id = "sensor.wind_direction"
    await sensor4.async_update_ha_state()

    sensor5 = DemoSensor(
        None,
        "SPS30 PM <1µm Weight concentration",
        3.7069,
        None,
        None,
        CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        None,
    )
    sensor5.hass = hass
    sensor5.entity_id = "sensor.sps30_pm_1um_weight_concentration"
    await sensor5.async_update_ha_state()

    sensor6 = DemoSensor(
        None, "Target temperature", 22.7, None, None, TEMP_CELSIUS, None
    )
    sensor6.hass = hass
    sensor6.entity_id = "input_number.target_temperature"
    await sensor6.async_update_ha_state()

    await hass.async_block_till_done()
    body = await generate_latest_metrics(client)

    assert (
        'sensor_unit_kwh{domain="sensor",'
        'entity="sensor.television_energy",'
        'friendly_name="Television Energy"} 74.0' in body
    )

    assert (
        'sensor_unit_sek_per_kwh{domain="sensor",'
        'entity="sensor.electricity_price",'
        'friendly_name="Electricity price"} 0.123' in body
    )

    assert (
        'sensor_unit_u0xb0{domain="sensor",'
        'entity="sensor.wind_direction",'
        'friendly_name="Wind Direction"} 25.0' in body
    )

    assert (
        'sensor_unit_u0xb5g_per_mu0xb3{domain="sensor",'
        'entity="sensor.sps30_pm_1um_weight_concentration",'
        'friendly_name="SPS30 PM <1µm Weight concentration"} 3.7069' in body
    )

    assert (
        'input_number_state_celsius{domain="input_number",'
        'entity="input_number.target_temperature",'
        'friendly_name="Target temperature"} 22.7' in body
    )


async def test_sensor_without_unit(hass, hass_client):
    """Test prometheus metrics for sensors without a unit."""
    client = await setup_prometheus_client(hass, hass_client, "")

    sensor6 = DemoSensor(None, "Trend Gradient", 0.002, None, None, None, None)
    sensor6.hass = hass
    sensor6.entity_id = "sensor.trend_gradient"
    await sensor6.async_update_ha_state()

    sensor7 = DemoSensor(None, "Text", "should_not_work", None, None, None, None)
    sensor7.hass = hass
    sensor7.entity_id = "sensor.text"
    await sensor7.async_update_ha_state()

    sensor8 = DemoSensor(None, "Text Unit", "should_not_work", None, None, "Text", None)
    sensor8.hass = hass
    sensor8.entity_id = "sensor.text_unit"
    await sensor8.async_update_ha_state()

    body = await generate_latest_metrics(client)

    assert (
        'sensor_state{domain="sensor",'
        'entity="sensor.trend_gradient",'
        'friendly_name="Trend Gradient"} 0.002' in body
    )

    assert (
        'sensor_state{domain="sensor",'
        'entity="sensor.text",'
        'friendly_name="Text"} 0' not in body
    )

    assert (
        'sensor_unit_text{domain="sensor",'
        'entity="sensor.text_unit",'
        'friendly_name="Text Unit"} 0' not in body
    )


async def test_sensor_device_class(hass, hass_client):
    """Test prometheus metrics for sensor with a device_class."""
    assert await async_setup_component(
        hass,
        "conversation",
        {},
    )

    client = await setup_prometheus_client(hass, hass_client, "")

    await async_setup_component(hass, sensor.DOMAIN, {"sensor": [{"platform": "demo"}]})
    await hass.async_block_till_done()

    sensor1 = DemoSensor(
        None,
        "Fahrenheit",
        50,
        SensorDeviceClass.TEMPERATURE,
        None,
        TEMP_FAHRENHEIT,
        None,
    )
    sensor1.hass = hass
    sensor1.entity_id = "sensor.fahrenheit"
    await sensor1.async_update_ha_state()

    sensor2 = DemoSensor(
        None,
        "Radio Energy",
        14,
        SensorDeviceClass.POWER,
        None,
        ENERGY_KILO_WATT_HOUR,
        None,
    )
    sensor2.hass = hass
    sensor2.entity_id = "sensor.radio_energy"
    with mock.patch(
        "homeassistant.util.dt.utcnow",
        return_value=datetime.datetime(1970, 1, 2, tzinfo=dt_util.UTC),
    ):
        await sensor2.async_update_ha_state()

    await hass.async_block_till_done()
    body = await generate_latest_metrics(client)

    assert (
        'sensor_temperature_celsius{domain="sensor",'
        'entity="sensor.fahrenheit",'
        'friendly_name="Fahrenheit"} 10.0' in body
    )

    assert (
        'sensor_temperature_celsius{domain="sensor",'
        'entity="sensor.outside_temperature",'
        'friendly_name="Outside Temperature"} 15.6' in body
    )

    assert (
        'sensor_humidity_percent{domain="sensor",'
        'entity="sensor.outside_humidity",'
        'friendly_name="Outside Humidity"} 54.0' in body
    )

    assert (
        'sensor_power_kwh{domain="sensor",'
        'entity="sensor.radio_energy",'
        'friendly_name="Radio Energy"} 14.0' in body
    )


async def test_input_number(hass, hass_client):
    """Test prometheus metrics for input_number."""
    client = await setup_prometheus_client(hass, hass_client, "")

    number1 = DemoNumber(None, "Threshold", 5.2, None, False, 0, 10, 0.1)
    number1.hass = hass
    number1.entity_id = "input_number.threshold"
    await number1.async_update_ha_state()

    number2 = DemoNumber(None, None, 60, None, False, 0, 100)
    number2.hass = hass
    number2.entity_id = "input_number.brightness"
    number2._attr_name = None
    await number2.async_update_ha_state()

    number3 = DemoSensor(None, "Retry count", 5, None, None, None, None)
    number3.hass = hass
    number3.entity_id = "input_number.retry_count"
    await number3.async_update_ha_state()

    await hass.async_block_till_done()
    body = await generate_latest_metrics(client)

    assert (
        'input_number_state{domain="input_number",'
        'entity="input_number.threshold",'
        'friendly_name="Threshold"} 5.2' in body
    )

    assert (
        'input_number_state{domain="input_number",'
        'entity="input_number.brightness",'
        'friendly_name="None"} 60.0' in body
    )

    assert (
        'input_number_state{domain="input_number",'
        'entity="input_number.retry_count",'
        'friendly_name="Retry count"} 5.0' in body
    )


async def test_battery(hass, hass_client):
    """Test prometheus metrics for battery."""
    assert await async_setup_component(
        hass,
        "conversation",
        {},
    )

    client = await setup_prometheus_client(hass, hass_client, "")

    await async_setup_component(hass, sensor.DOMAIN, {"sensor": [{"platform": "demo"}]})
    await hass.async_block_till_done()

    body = await generate_latest_metrics(client)

    assert (
        'battery_level_percent{domain="sensor",'
        'entity="sensor.outside_temperature",'
        'friendly_name="Outside Temperature"} 12.0' in body
    )


async def test_climate(hass, hass_client):
    """Test prometheus metrics for climate."""
    assert await async_setup_component(
        hass,
        "conversation",
        {},
    )

    client = await setup_prometheus_client(hass, hass_client, "")

    await async_setup_component(
        hass, climate.DOMAIN, {"climate": [{"platform": "demo"}]}
    )

    await hass.async_block_till_done()
    body = await generate_latest_metrics(client)

    assert (
        'climate_current_temperature_celsius{domain="climate",'
        'entity="climate.heatpump",'
        'friendly_name="HeatPump"} 25.0' in body
    )

    assert (
        'climate_target_temperature_celsius{domain="climate",'
        'entity="climate.heatpump",'
        'friendly_name="HeatPump"} 20.0' in body
    )

    assert (
        'climate_target_temperature_low_celsius{domain="climate",'
        'entity="climate.ecobee",'
        'friendly_name="Ecobee"} 21.0' in body
    )

    assert (
        'climate_target_temperature_high_celsius{domain="climate",'
        'entity="climate.ecobee",'
        'friendly_name="Ecobee"} 24.0' in body
    )

    assert (
        'climate_mode{domain="climate",'
        'entity="climate.heatpump",'
        'friendly_name="HeatPump",'
        'mode="heat"} 1.0' in body
    )

    assert (
        'climate_mode{domain="climate",'
        'entity="climate.heatpump",'
        'friendly_name="HeatPump",'
        'mode="off"} 0.0' in body
    )


async def test_humidifier(hass, hass_client):
    """Test prometheus metrics for battery."""
    assert await async_setup_component(
        hass,
        "conversation",
        {},
    )

    client = await setup_prometheus_client(hass, hass_client, "")

    await async_setup_component(
        hass, humidifier.DOMAIN, {"humidifier": [{"platform": "demo"}]}
    )

    await hass.async_block_till_done()
    body = await generate_latest_metrics(client)

    assert (
        'humidifier_target_humidity_percent{domain="humidifier",'
        'entity="humidifier.humidifier",'
        'friendly_name="Humidifier"} 68.0' in body
    )

    assert (
        'humidifier_state{domain="humidifier",'
        'entity="humidifier.dehumidifier",'
        'friendly_name="Dehumidifier"} 1.0' in body
    )

    assert (
        'humidifier_mode{domain="humidifier",'
        'entity="humidifier.hygrostat",'
        'friendly_name="Hygrostat",'
        'mode="home"} 1.0' in body
    )
    assert (
        'humidifier_mode{domain="humidifier",'
        'entity="humidifier.hygrostat",'
        'friendly_name="Hygrostat",'
        'mode="eco"} 0.0' in body
    )


async def test_attributes(hass, hass_client):
    """Test prometheus metrics for entity attributes."""
    client = await setup_prometheus_client(hass, hass_client, "")

    switch1 = DemoSensor(None, "Boolean", 74, None, None, None, None)
    switch1.hass = hass
    switch1.entity_id = "switch.boolean"
    switch1._attr_extra_state_attributes = {"boolean": True}
    await switch1.async_update_ha_state()

    switch2 = DemoSensor(None, "Number", 42, None, None, None, None)
    switch2.hass = hass
    switch2.entity_id = "switch.number"
    switch2._attr_extra_state_attributes = {"Number": 10.2}
    await switch2.async_update_ha_state()

    await hass.async_block_till_done()
    body = await generate_latest_metrics(client)

    assert (
        'switch_state{domain="switch",'
        'entity="switch.boolean",'
        'friendly_name="Boolean"} 74.0' in body
    )

    assert (
        'switch_attr_boolean{domain="switch",'
        'entity="switch.boolean",'
        'friendly_name="Boolean"} 1.0' in body
    )

    assert (
        'switch_state{domain="switch",'
        'entity="switch.number",'
        'friendly_name="Number"} 42.0' in body
    )

    assert (
        'switch_attr_number{domain="switch",'
        'entity="switch.number",'
        'friendly_name="Number"} 10.2' in body
    )


async def test_binary_sensor(hass, hass_client):
    """Test prometheus metrics for binary_sensor."""
    client = await setup_prometheus_client(hass, hass_client, "")

    binary_sensor1 = DemoBinarySensor(None, "Door", True, None)
    binary_sensor1.hass = hass
    binary_sensor1.entity_id = "binary_sensor.door"
    await binary_sensor1.async_update_ha_state()

    binary_sensor1 = DemoBinarySensor(None, "Window", False, None)
    binary_sensor1.hass = hass
    binary_sensor1.entity_id = "binary_sensor.window"
    await binary_sensor1.async_update_ha_state()

    await hass.async_block_till_done()
    body = await generate_latest_metrics(client)

    assert (
        'binary_sensor_state{domain="binary_sensor",'
        'entity="binary_sensor.door",'
        'friendly_name="Door"} 1.0' in body
    )

    assert (
        'binary_sensor_state{domain="binary_sensor",'
        'entity="binary_sensor.window",'
        'friendly_name="Window"} 0.0' in body
    )


async def test_input_boolean(hass, hass_client):
    """Test prometheus metrics for input_boolean."""
    client = await setup_prometheus_client(hass, hass_client, "")

    input_boolean1 = DemoSensor(None, "Test", 1, None, None, None, None)
    input_boolean1.hass = hass
    input_boolean1.entity_id = "input_boolean.test"
    await input_boolean1.async_update_ha_state()

    input_boolean2 = DemoSensor(None, "Helper", 0, None, None, None, None)
    input_boolean2.hass = hass
    input_boolean2.entity_id = "input_boolean.helper"
    await input_boolean2.async_update_ha_state()

    await hass.async_block_till_done()
    body = await generate_latest_metrics(client)

    assert (
        'input_boolean_state{domain="input_boolean",'
        'entity="input_boolean.test",'
        'friendly_name="Test"} 1.0' in body
    )

    assert (
        'input_boolean_state{domain="input_boolean",'
        'entity="input_boolean.helper",'
        'friendly_name="Helper"} 0.0' in body
    )


async def test_light(hass, hass_client):
    """Test prometheus metrics for lights."""
    client = await setup_prometheus_client(hass, hass_client, "")

    light1 = DemoSensor(None, "Desk", 1, None, None, None, None)
    light1.hass = hass
    light1.entity_id = "light.desk"
    await light1.async_update_ha_state()

    light2 = DemoSensor(None, "Wall", 0, None, None, None, None)
    light2.hass = hass
    light2.entity_id = "light.wall"
    await light2.async_update_ha_state()

    light3 = DemoLight(None, "TV", True, True, 255, None, None)
    light3.hass = hass
    light3.entity_id = "light.tv"
    await light3.async_update_ha_state()

    light4 = DemoLight(None, "PC", True, True, 180, None, None)
    light4.hass = hass
    light4.entity_id = "light.pc"
    await light4.async_update_ha_state()

    await hass.async_block_till_done()
    body = await generate_latest_metrics(client)

    assert (
        'light_brightness_percent{domain="light",'
        'entity="light.desk",'
        'friendly_name="Desk"} 100.0' in body
    )

    assert (
        'light_brightness_percent{domain="light",'
        'entity="light.wall",'
        'friendly_name="Wall"} 0.0' in body
    )

    assert (
        'light_brightness_percent{domain="light",'
        'entity="light.tv",'
        'friendly_name="TV"} 100.0' in body
    )

    assert (
        'light_brightness_percent{domain="light",'
        'entity="light.pc",'
        'friendly_name="PC"} 70.58823529411765' in body
    )


async def test_lock(hass, hass_client):
    """Test prometheus metrics for lock."""
    assert await async_setup_component(
        hass,
        "conversation",
        {},
    )

    client = await setup_prometheus_client(hass, hass_client, "")

    await async_setup_component(hass, lock.DOMAIN, {"lock": [{"platform": "demo"}]})

    await hass.async_block_till_done()
    body = await generate_latest_metrics(client)

    assert (
        'lock_state{domain="lock",'
        'entity="lock.front_door",'
        'friendly_name="Front Door"} 1.0' in body
    )

    assert (
        'lock_state{domain="lock",'
        'entity="lock.kitchen_door",'
        'friendly_name="Kitchen Door"} 0.0' in body
    )


async def test_counter(hass, hass_client):
    """Test prometheus metrics for counter."""
    assert await async_setup_component(
        hass,
        "conversation",
        {},
    )

    client = await setup_prometheus_client(hass, hass_client, "")

    await async_setup_component(
        hass, counter.DOMAIN, {"counter": {"counter": {"initial": "2"}}}
    )

    await hass.async_block_till_done()

    body = await generate_latest_metrics(client)

    assert (
        'counter_value{domain="counter",'
        'entity="counter.counter",'
        'friendly_name="None"} 2.0' in body
    )


async def test_renaming_entity_name(hass, hass_client):
    """Test renaming entity name."""
    assert await async_setup_component(
        hass,
        "conversation",
        {},
    )
    client = await setup_prometheus_client(hass, hass_client, "")

    assert await async_setup_component(
        hass, climate.DOMAIN, {"climate": [{"platform": "demo"}]}
    )

    assert await async_setup_component(
        hass, sensor.DOMAIN, {"sensor": [{"platform": "demo"}]}
    )

    await hass.async_block_till_done()
    body = await generate_latest_metrics(client)

    assert (
        'sensor_temperature_celsius{domain="sensor",'
        'entity="sensor.outside_temperature",'
        'friendly_name="Outside Temperature"} 15.6' in body
    )

    assert (
        'entity_available{domain="sensor",'
        'entity="sensor.outside_temperature",'
        'friendly_name="Outside Temperature"} 1.0' in body
    )

    assert (
        'sensor_humidity_percent{domain="sensor",'
        'entity="sensor.outside_humidity",'
        'friendly_name="Outside Humidity"} 54.0' in body
    )

    assert (
        'entity_available{domain="sensor",'
        'entity="sensor.outside_humidity",'
        'friendly_name="Outside Humidity"} 1.0' in body
    )

    assert (
        'climate_action{action="heating",'
        'domain="climate",'
        'entity="climate.heatpump",'
        'friendly_name="HeatPump"} 1.0' in body
    )

    assert (
        'climate_action{action="cooling",'
        'domain="climate",'
        'entity="climate.heatpump",'
        'friendly_name="HeatPump"} 0.0' in body
    )

    registry = entity_registry.async_get(hass)
    assert "sensor.outside_temperature" in registry.entities
    assert "climate.heatpump" in registry.entities
    registry.async_update_entity(
        entity_id="sensor.outside_temperature",
        name="Outside Temperature Renamed",
    )
    registry.async_update_entity(
        entity_id="climate.heatpump",
        name="HeatPump Renamed",
    )

    await hass.async_block_till_done()
    body = await generate_latest_metrics(client)

    # Check if old metrics deleted
    body_line = "\n".join(body)
    assert 'friendly_name="Outside Temperature"' not in body_line
    assert 'friendly_name="HeatPump"' not in body_line

    # Check if new metrics created
    assert (
        'sensor_temperature_celsius{domain="sensor",'
        'entity="sensor.outside_temperature",'
        'friendly_name="Outside Temperature Renamed"} 15.6' in body
    )

    assert (
        'entity_available{domain="sensor",'
        'entity="sensor.outside_temperature",'
        'friendly_name="Outside Temperature Renamed"} 1.0' in body
    )

    assert (
        'climate_action{action="heating",'
        'domain="climate",'
        'entity="climate.heatpump",'
        'friendly_name="HeatPump Renamed"} 1.0' in body
    )

    assert (
        'climate_action{action="cooling",'
        'domain="climate",'
        'entity="climate.heatpump",'
        'friendly_name="HeatPump Renamed"} 0.0' in body
    )

    # Keep other sensors
    assert (
        'sensor_humidity_percent{domain="sensor",'
        'entity="sensor.outside_humidity",'
        'friendly_name="Outside Humidity"} 54.0' in body
    )

    assert (
        'entity_available{domain="sensor",'
        'entity="sensor.outside_humidity",'
        'friendly_name="Outside Humidity"} 1.0' in body
    )


async def test_renaming_entity_id(hass, hass_client):
    """Test renaming entity id."""
    assert await async_setup_component(
        hass,
        "conversation",
        {},
    )
    client = await setup_prometheus_client(hass, hass_client, "")

    assert await async_setup_component(
        hass, sensor.DOMAIN, {"sensor": [{"platform": "demo"}]}
    )

    await hass.async_block_till_done()
    body = await generate_latest_metrics(client)

    assert (
        'sensor_temperature_celsius{domain="sensor",'
        'entity="sensor.outside_temperature",'
        'friendly_name="Outside Temperature"} 15.6' in body
    )

    assert (
        'entity_available{domain="sensor",'
        'entity="sensor.outside_temperature",'
        'friendly_name="Outside Temperature"} 1.0' in body
    )

    assert (
        'sensor_humidity_percent{domain="sensor",'
        'entity="sensor.outside_humidity",'
        'friendly_name="Outside Humidity"} 54.0' in body
    )

    assert (
        'entity_available{domain="sensor",'
        'entity="sensor.outside_humidity",'
        'friendly_name="Outside Humidity"} 1.0' in body
    )

    registry = entity_registry.async_get(hass)
    assert "sensor.outside_temperature" in registry.entities
    registry.async_update_entity(
        entity_id="sensor.outside_temperature",
        new_entity_id="sensor.outside_temperature_renamed",
    )

    await hass.async_block_till_done()
    body = await generate_latest_metrics(client)

    # Check if old metrics deleted
    body_line = "\n".join(body)
    assert 'entity="sensor.outside_temperature"' not in body_line

    # Check if new metrics created
    assert (
        'sensor_temperature_celsius{domain="sensor",'
        'entity="sensor.outside_temperature_renamed",'
        'friendly_name="Outside Temperature"} 15.6' in body
    )

    assert (
        'entity_available{domain="sensor",'
        'entity="sensor.outside_temperature_renamed",'
        'friendly_name="Outside Temperature"} 1.0' in body
    )

    # Keep other sensors
    assert (
        'sensor_humidity_percent{domain="sensor",'
        'entity="sensor.outside_humidity",'
        'friendly_name="Outside Humidity"} 54.0' in body
    )

    assert (
        'entity_available{domain="sensor",'
        'entity="sensor.outside_humidity",'
        'friendly_name="Outside Humidity"} 1.0' in body
    )


async def test_deleting_entity(hass, hass_client):
    """Test deleting a entity."""
    assert await async_setup_component(
        hass,
        "conversation",
        {},
    )
    client = await setup_prometheus_client(hass, hass_client, "")

    await async_setup_component(
        hass, climate.DOMAIN, {"climate": [{"platform": "demo"}]}
    )

    assert await async_setup_component(
        hass, sensor.DOMAIN, {"sensor": [{"platform": "demo"}]}
    )

    await hass.async_block_till_done()
    body = await generate_latest_metrics(client)

    assert (
        'sensor_temperature_celsius{domain="sensor",'
        'entity="sensor.outside_temperature",'
        'friendly_name="Outside Temperature"} 15.6' in body
    )

    assert (
        'entity_available{domain="sensor",'
        'entity="sensor.outside_temperature",'
        'friendly_name="Outside Temperature"} 1.0' in body
    )

    assert (
        'sensor_humidity_percent{domain="sensor",'
        'entity="sensor.outside_humidity",'
        'friendly_name="Outside Humidity"} 54.0' in body
    )

    assert (
        'entity_available{domain="sensor",'
        'entity="sensor.outside_humidity",'
        'friendly_name="Outside Humidity"} 1.0' in body
    )

    assert (
        'climate_action{action="heating",'
        'domain="climate",'
        'entity="climate.heatpump",'
        'friendly_name="HeatPump"} 1.0' in body
    )

    assert (
        'climate_action{action="cooling",'
        'domain="climate",'
        'entity="climate.heatpump",'
        'friendly_name="HeatPump"} 0.0' in body
    )

    registry = entity_registry.async_get(hass)
    assert "sensor.outside_temperature" in registry.entities
    assert "climate.heatpump" in registry.entities
    registry.async_remove("sensor.outside_temperature")
    registry.async_remove("climate.heatpump")

    await hass.async_block_till_done()
    body = await generate_latest_metrics(client)

    # Check if old metrics deleted
    body_line = "\n".join(body)
    assert 'entity="sensor.outside_temperature"' not in body_line
    assert 'friendly_name="Outside Temperature"' not in body_line
    assert 'entity="climate.heatpump"' not in body_line
    assert 'friendly_name="HeatPump"' not in body_line

    # Keep other sensors
    assert (
        'sensor_humidity_percent{domain="sensor",'
        'entity="sensor.outside_humidity",'
        'friendly_name="Outside Humidity"} 54.0' in body
    )

    assert (
        'entity_available{domain="sensor",'
        'entity="sensor.outside_humidity",'
        'friendly_name="Outside Humidity"} 1.0' in body
    )


async def test_disabling_entity(hass, hass_client):
    """Test disabling a entity."""
    assert await async_setup_component(
        hass,
        "conversation",
        {},
    )
    client = await setup_prometheus_client(hass, hass_client, "")

    await async_setup_component(
        hass, climate.DOMAIN, {"climate": [{"platform": "demo"}]}
    )

    assert await async_setup_component(
        hass, sensor.DOMAIN, {"sensor": [{"platform": "demo"}]}
    )

    await hass.async_block_till_done()
    body = await generate_latest_metrics(client)

    assert (
        'sensor_temperature_celsius{domain="sensor",'
        'entity="sensor.outside_temperature",'
        'friendly_name="Outside Temperature"} 15.6' in body
    )

    assert (
        'state_change_total{domain="sensor",'
        'entity="sensor.outside_temperature",'
        'friendly_name="Outside Temperature"} 1.0' in body
    )

    assert any(
        'state_change_created{domain="sensor",'
        'entity="sensor.outside_temperature",'
        'friendly_name="Outside Temperature"}' in metric
        for metric in body
    )

    assert (
        'sensor_humidity_percent{domain="sensor",'
        'entity="sensor.outside_humidity",'
        'friendly_name="Outside Humidity"} 54.0' in body
    )

    assert (
        'entity_available{domain="sensor",'
        'entity="sensor.outside_humidity",'
        'friendly_name="Outside Humidity"} 1.0' in body
    )

    assert (
        'climate_action{action="heating",'
        'domain="climate",'
        'entity="climate.heatpump",'
        'friendly_name="HeatPump"} 1.0' in body
    )

    assert (
        'climate_action{action="cooling",'
        'domain="climate",'
        'entity="climate.heatpump",'
        'friendly_name="HeatPump"} 0.0' in body
    )

    registry = entity_registry.async_get(hass)
    assert "sensor.outside_temperature" in registry.entities
    assert "climate.heatpump" in registry.entities
    registry.async_update_entity(
        entity_id="sensor.outside_temperature",
        disabled_by="user",
    )
    registry.async_update_entity(entity_id="climate.heatpump", disabled_by="user")

    await hass.async_block_till_done()
    body = await generate_latest_metrics(client)

    # Check if old metrics deleted
    body_line = "\n".join(body)
    assert 'entity="sensor.outside_temperature"' not in body_line
    assert 'friendly_name="Outside Temperature"' not in body_line
    assert 'entity="climate.heatpump"' not in body_line
    assert 'friendly_name="HeatPump"' not in body_line

    # Keep other sensors
    assert (
        'sensor_humidity_percent{domain="sensor",'
        'entity="sensor.outside_humidity",'
        'friendly_name="Outside Humidity"} 54.0' in body
    )

    assert (
        'entity_available{domain="sensor",'
        'entity="sensor.outside_humidity",'
        'friendly_name="Outside Humidity"} 1.0' in body
    )


@pytest.fixture(name="mock_client")
def mock_client_fixture():
    """Mock the prometheus client."""
    with mock.patch(f"{PROMETHEUS_PATH}.prometheus_client") as client:
        counter_client = mock.MagicMock()
        client.Counter = mock.MagicMock(return_value=counter_client)
        setattr(counter_client, "labels", mock.MagicMock(return_value=mock.MagicMock()))
        yield counter_client


@pytest.fixture
def mock_bus(hass):
    """Mock the event bus listener."""
    hass.bus.listen = mock.MagicMock()


@pytest.mark.usefixtures("mock_bus")
async def test_minimal_config(hass, mock_client):
    """Test the minimal config and defaults of component."""
    config = {prometheus.DOMAIN: {}}
    assert await async_setup_component(hass, prometheus.DOMAIN, config)
    await hass.async_block_till_done()
    assert hass.bus.listen.called
    assert hass.bus.listen.call_args_list[0][0][0] == EVENT_STATE_CHANGED


@pytest.mark.usefixtures("mock_bus")
async def test_full_config(hass, mock_client):
    """Test the full config of component."""
    config = {
        prometheus.DOMAIN: {
            "namespace": "ns",
            "default_metric": "m",
            "override_metric": "m",
            "component_config": {"fake.test": {"override_metric": "km"}},
            "component_config_glob": {"fake.time_*": {"override_metric": "h"}},
            "component_config_domain": {"climate": {"override_metric": "°C"}},
            "filter": {
                "include_domains": ["climate"],
                "include_entity_globs": ["fake.time_*"],
                "include_entities": ["fake.test"],
                "exclude_domains": ["script"],
                "exclude_entity_globs": ["climate.excluded_*"],
                "exclude_entities": ["fake.time_excluded"],
            },
        }
    }
    assert await async_setup_component(hass, prometheus.DOMAIN, config)
    await hass.async_block_till_done()
    assert hass.bus.listen.called
    assert hass.bus.listen.call_args_list[0][0][0] == EVENT_STATE_CHANGED


def make_event(entity_id):
    """Make a mock event for test."""
    domain = split_entity_id(entity_id)[0]
    state = mock.MagicMock(
        state="not blank",
        domain=domain,
        entity_id=entity_id,
        object_id="entity",
        attributes={},
    )
    return mock.MagicMock(data={"new_state": state}, time_fired=12345)


async def _setup(hass, filter_config):
    """Shared set up for filtering tests."""
    config = {prometheus.DOMAIN: {"filter": filter_config}}
    assert await async_setup_component(hass, prometheus.DOMAIN, config)
    await hass.async_block_till_done()
    return hass.bus.listen.call_args_list[0][0][1]


@pytest.mark.usefixtures("mock_bus")
async def test_allowlist(hass, mock_client):
    """Test an allowlist only config."""
    handler_method = await _setup(
        hass,
        {
            "include_domains": ["fake"],
            "include_entity_globs": ["test.included_*"],
            "include_entities": ["not_real.included"],
        },
    )

    tests = [
        FilterTest("climate.excluded", False),
        FilterTest("fake.included", True),
        FilterTest("test.excluded_test", False),
        FilterTest("test.included_test", True),
        FilterTest("not_real.included", True),
        FilterTest("not_real.excluded", False),
    ]

    for test in tests:
        event = make_event(test.id)
        handler_method(event)

        was_called = mock_client.labels.call_count == 1
        assert test.should_pass == was_called
        mock_client.labels.reset_mock()


@pytest.mark.usefixtures("mock_bus")
async def test_denylist(hass, mock_client):
    """Test a denylist only config."""
    handler_method = await _setup(
        hass,
        {
            "exclude_domains": ["fake"],
            "exclude_entity_globs": ["test.excluded_*"],
            "exclude_entities": ["not_real.excluded"],
        },
    )

    tests = [
        FilterTest("fake.excluded", False),
        FilterTest("light.included", True),
        FilterTest("test.excluded_test", False),
        FilterTest("test.included_test", True),
        FilterTest("not_real.included", True),
        FilterTest("not_real.excluded", False),
    ]

    for test in tests:
        event = make_event(test.id)
        handler_method(event)

        was_called = mock_client.labels.call_count == 1
        assert test.should_pass == was_called
        mock_client.labels.reset_mock()


@pytest.mark.usefixtures("mock_bus")
async def test_filtered_denylist(hass, mock_client):
    """Test a denylist config with a filtering allowlist."""
    handler_method = await _setup(
        hass,
        {
            "include_entities": ["fake.included", "test.excluded_test"],
            "exclude_domains": ["fake"],
            "exclude_entity_globs": ["*.excluded_*"],
            "exclude_entities": ["not_real.excluded"],
        },
    )

    tests = [
        FilterTest("fake.excluded", False),
        FilterTest("fake.included", True),
        FilterTest("alt_fake.excluded_test", False),
        FilterTest("test.excluded_test", True),
        FilterTest("not_real.excluded", False),
        FilterTest("not_real.included", True),
    ]

    for test in tests:
        event = make_event(test.id)
        handler_method(event)

        was_called = mock_client.labels.call_count == 1
        assert test.should_pass == was_called
        mock_client.labels.reset_mock()
