"""The tests for the Prometheus exporter."""
import pytest

from homeassistant import setup
from homeassistant.components import climate, sensor
from homeassistant.components.demo.sensor import DemoSensor
import homeassistant.components.prometheus as prometheus
from homeassistant.const import DEVICE_CLASS_POWER, ENERGY_KILO_WATT_HOUR
from homeassistant.setup import async_setup_component


@pytest.fixture
async def prometheus_client(loop, hass, hass_client):
    """Initialize an hass_client with Prometheus component."""
    await async_setup_component(hass, prometheus.DOMAIN, {prometheus.DOMAIN: {}})

    await setup.async_setup_component(
        hass, sensor.DOMAIN, {"sensor": [{"platform": "demo"}]}
    )

    await setup.async_setup_component(
        hass, climate.DOMAIN, {"climate": [{"platform": "demo"}]}
    )

    sensor1 = DemoSensor(
        None, "Television Energy", 74, None, ENERGY_KILO_WATT_HOUR, None
    )
    sensor1.hass = hass
    sensor1.entity_id = "sensor.television_energy"
    await sensor1.async_update_ha_state()

    sensor2 = DemoSensor(
        None, "Radio Energy", 14, DEVICE_CLASS_POWER, ENERGY_KILO_WATT_HOUR, None
    )
    sensor2.hass = hass
    sensor2.entity_id = "sensor.radio_energy"
    await sensor2.async_update_ha_state()

    sensor3 = DemoSensor(None, "Electricity price", 0.123, None, "SEK/kWh", None)
    sensor3.hass = hass
    sensor3.entity_id = "sensor.electricity_price"
    await sensor3.async_update_ha_state()

    sensor4 = DemoSensor(None, "Wind Direction", 25, None, "°", None)
    sensor4.hass = hass
    sensor4.entity_id = "sensor.wind_direction"
    await sensor4.async_update_ha_state()

    sensor5 = DemoSensor(
        None, "SPS30 PM <1µm Weight concentration", 3.7069, None, "µg/m³", None
    )
    sensor5.hass = hass
    sensor5.entity_id = "sensor.sps30_pm_1um_weight_concentration"
    await sensor5.async_update_ha_state()

    return await hass_client()


async def test_view(prometheus_client):  # pylint: disable=redefined-outer-name
    """Test prometheus metrics view."""
    resp = await prometheus_client.get(prometheus.API_ENDPOINT)

    assert resp.status == 200
    assert resp.headers["content-type"] == "text/plain"
    body = await resp.text()
    body = body.split("\n")

    assert len(body) > 3

    assert "# HELP python_info Python platform information" in body
    assert (
        "# HELP python_gc_objects_collected_total "
        "Objects collected during gc" in body
    )

    assert (
        'temperature_c{domain="sensor",'
        'entity="sensor.outside_temperature",'
        'friendly_name="Outside Temperature"} 15.6' in body
    )

    assert (
        'battery_level_percent{domain="sensor",'
        'entity="sensor.outside_temperature",'
        'friendly_name="Outside Temperature"} 12.0' in body
    )

    assert (
        'current_temperature_c{domain="climate",'
        'entity="climate.heatpump",'
        'friendly_name="HeatPump"} 25.0' in body
    )

    assert (
        'humidity_percent{domain="sensor",'
        'entity="sensor.outside_humidity",'
        'friendly_name="Outside Humidity"} 54.0' in body
    )

    assert (
        'sensor_unit_kwh{domain="sensor",'
        'entity="sensor.television_energy",'
        'friendly_name="Television Energy"} 74.0' in body
    )

    assert (
        'power_kwh{domain="sensor",'
        'entity="sensor.radio_energy",'
        'friendly_name="Radio Energy"} 14.0' in body
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
