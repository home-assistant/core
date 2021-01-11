"""The tests for the Prometheus exporter."""
from dataclasses import dataclass
import datetime
import unittest.mock as mock

import pytest

from homeassistant.components import climate, humidifier, sensor
from homeassistant.components.demo.sensor import DemoSensor
import homeassistant.components.prometheus as prometheus
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONTENT_TYPE_TEXT_PLAIN,
    DEGREE,
    DEVICE_CLASS_POWER,
    ENERGY_KILO_WATT_HOUR,
    EVENT_STATE_CHANGED,
)
from homeassistant.core import split_entity_id
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

PROMETHEUS_PATH = "homeassistant.components.prometheus"


@dataclass
class FilterTest:
    """Class for capturing a filter test."""

    id: str
    should_pass: bool


async def prometheus_client(hass, hass_client):
    """Initialize an hass_client with Prometheus component."""
    await async_setup_component(hass, prometheus.DOMAIN, {prometheus.DOMAIN: {}})

    await async_setup_component(hass, sensor.DOMAIN, {"sensor": [{"platform": "demo"}]})

    await async_setup_component(
        hass, climate.DOMAIN, {"climate": [{"platform": "demo"}]}
    )
    await hass.async_block_till_done()

    await async_setup_component(
        hass, humidifier.DOMAIN, {"humidifier": [{"platform": "demo"}]}
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
    with mock.patch(
        "homeassistant.util.dt.utcnow",
        return_value=datetime.datetime(1970, 1, 2, tzinfo=dt_util.UTC),
    ):
        await sensor2.async_update_ha_state()

    sensor3 = DemoSensor(
        None, "Electricity price", 0.123, None, f"SEK/{ENERGY_KILO_WATT_HOUR}", None
    )
    sensor3.hass = hass
    sensor3.entity_id = "sensor.electricity_price"
    await sensor3.async_update_ha_state()

    sensor4 = DemoSensor(None, "Wind Direction", 25, None, DEGREE, None)
    sensor4.hass = hass
    sensor4.entity_id = "sensor.wind_direction"
    await sensor4.async_update_ha_state()

    sensor5 = DemoSensor(
        None,
        "SPS30 PM <1µm Weight concentration",
        3.7069,
        None,
        CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        None,
    )
    sensor5.hass = hass
    sensor5.entity_id = "sensor.sps30_pm_1um_weight_concentration"
    await sensor5.async_update_ha_state()

    return await hass_client()


async def test_view(hass, hass_client):
    """Test prometheus metrics view."""
    client = await prometheus_client(hass, hass_client)
    resp = await client.get(prometheus.API_ENDPOINT)

    assert resp.status == 200
    assert resp.headers["content-type"] == CONTENT_TYPE_TEXT_PLAIN
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
        'entity_available{domain="sensor",'
        'entity="sensor.radio_energy",'
        'friendly_name="Radio Energy"} 1.0' in body
    )

    assert (
        'last_updated_time_seconds{domain="sensor",'
        'entity="sensor.radio_energy",'
        'friendly_name="Radio Energy"} 86400.0' in body
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
    assert EVENT_STATE_CHANGED == hass.bus.listen.call_args_list[0][0][0]


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
    assert EVENT_STATE_CHANGED == hass.bus.listen.call_args_list[0][0][0]


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
