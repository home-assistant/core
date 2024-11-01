"""The tests for the Prometheus exporter."""

from dataclasses import dataclass
import datetime
from http import HTTPStatus
from typing import Any, Self
from unittest import mock

from freezegun import freeze_time
import prometheus_client
from prometheus_client.utils import floatToGoString
import pytest

from homeassistant.components import (
    alarm_control_panel,
    binary_sensor,
    climate,
    counter,
    cover,
    device_tracker,
    fan,
    humidifier,
    input_boolean,
    input_number,
    light,
    lock,
    number,
    person,
    prometheus,
    sensor,
    switch,
    update,
)
from homeassistant.components.alarm_control_panel import AlarmControlPanelState
from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_FAN_MODES,
    ATTR_HUMIDITY,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODES,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
)
from homeassistant.components.fan import (
    ATTR_DIRECTION,
    ATTR_OSCILLATING,
    ATTR_PERCENTAGE,
    ATTR_PRESET_MODE,
    ATTR_PRESET_MODES,
    DIRECTION_FORWARD,
    DIRECTION_REVERSE,
)
from homeassistant.components.humidifier import ATTR_AVAILABLE_MODES
from homeassistant.components.lock import LockState
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    ATTR_MODE,
    ATTR_TEMPERATURE,
    ATTR_UNIT_OF_MEASUREMENT,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONTENT_TYPE_TEXT_PLAIN,
    DEGREE,
    PERCENTAGE,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_HOME,
    STATE_NOT_HOME,
    STATE_OFF,
    STATE_ON,
    STATE_OPEN,
    STATE_OPENING,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfEnergy,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.typing import ClientSessionGenerator

PROMETHEUS_PATH = "homeassistant.components.prometheus"


class EntityMetric:
    """Represents a Prometheus metric for a Home Assistant entity."""

    metric_name: str
    labels: dict[str, str]

    @classmethod
    def required_labels(cls) -> list[str]:
        """List of all required labels for a Prometheus metric."""
        return [
            "domain",
            "friendly_name",
            "entity",
        ]

    def __init__(self, metric_name: str, **kwargs: Any) -> None:
        """Create a new EntityMetric based on metric name and labels."""
        self.metric_name = metric_name
        self.labels = kwargs

        # Labels that are required for all entities.
        for labelname in self.required_labels():
            assert labelname in self.labels
            assert self.labels[labelname] != ""

    def withValue(self, value: float) -> Self:
        """Return a metric with value."""
        return EntityMetricWithValue(self, value)

    @property
    def _metric_name_string(self) -> str:
        """Return a full metric name as a string."""
        labels = ",".join(
            f'{key}="{value}"' for key, value in sorted(self.labels.items())
        )
        return f"{self.metric_name}{{{labels}}}"

    def _in_metrics(self, metrics: list[str]) -> bool:
        """Report whether this metric exists in the provided Prometheus output."""
        return any(line.startswith(self._metric_name_string) for line in metrics)

    def assert_in_metrics(self, metrics: list[str]) -> None:
        """Assert that this metric exists in the provided Prometheus output."""
        assert self._in_metrics(metrics)

    def assert_not_in_metrics(self, metrics: list[str]) -> None:
        """Assert that this metric does not exist in Prometheus output."""
        assert not self._in_metrics(metrics)


class EntityMetricWithValue(EntityMetric):
    """Represents a Prometheus metric with a value."""

    value: float

    def __init__(self, metric: EntityMetric, value: float) -> None:
        """Create a new metric with a value based on a metric."""
        super().__init__(metric.metric_name, **metric.labels)
        self.value = value

    @property
    def _metric_string(self) -> str:
        """Return a full metric string."""
        value = floatToGoString(self.value)
        return f"{self._metric_name_string} {value}"

    def assert_in_metrics(self, metrics: list[str]) -> None:
        """Assert that this metric exists in the provided Prometheus output."""
        assert self._metric_string in metrics


@dataclass
class FilterTest:
    """Class for capturing a filter test."""

    id: str
    should_pass: bool


def test_entity_metric_generates_metric_name_string_without_value() -> None:
    """Test using EntityMetric to format a simple metric string without any value."""
    domain = "sensor"
    object_id = "outside_temperature"
    entity_metric = EntityMetric(
        metric_name="homeassistant_sensor_temperature_celsius",
        domain=domain,
        friendly_name="Outside Temperature",
        entity=f"{domain}.{object_id}",
    )
    assert entity_metric._metric_name_string == (
        "homeassistant_sensor_temperature_celsius{"
        'domain="sensor",'
        'entity="sensor.outside_temperature",'
        'friendly_name="Outside Temperature"}'
    )


def test_entity_metric_generates_metric_string_with_value() -> None:
    """Test using EntityMetric to format a simple metric string but with a metric value included."""
    domain = "sensor"
    object_id = "outside_temperature"
    entity_metric = EntityMetric(
        metric_name="homeassistant_sensor_temperature_celsius",
        domain=domain,
        friendly_name="Outside Temperature",
        entity=f"{domain}.{object_id}",
    ).withValue(17.2)
    assert entity_metric._metric_string == (
        "homeassistant_sensor_temperature_celsius{"
        'domain="sensor",'
        'entity="sensor.outside_temperature",'
        'friendly_name="Outside Temperature"}'
        " 17.2"
    )


def test_entity_metric_raises_exception_without_required_labels() -> None:
    """Test using EntityMetric to raise exception when required labels are missing."""
    domain = "sensor"
    object_id = "outside_temperature"
    test_kwargs = {
        "metric_name": "homeassistant_sensor_temperature_celsius",
        "domain": domain,
        "friendly_name": "Outside Temperature",
        "entity": f"{domain}.{object_id}",
    }

    assert len(EntityMetric.required_labels()) > 0

    for labelname in EntityMetric.required_labels():
        label_kwargs = dict(test_kwargs)
        # Delete the required label and ensure we get an exception
        del label_kwargs[labelname]
        with pytest.raises(AssertionError):
            EntityMetric(**label_kwargs)


def test_entity_metric_raises_exception_if_required_label_is_empty_string() -> None:
    """Test using EntityMetric to raise exception when required label value is empty string."""
    domain = "sensor"
    object_id = "outside_temperature"
    test_kwargs = {
        "metric_name": "homeassistant_sensor_temperature_celsius",
        "domain": domain,
        "friendly_name": "Outside Temperature",
        "entity": f"{domain}.{object_id}",
    }

    assert len(EntityMetric.required_labels()) > 0

    for labelname in EntityMetric.required_labels():
        label_kwargs = dict(test_kwargs)
        # Replace the required label with "" and ensure we get an exception
        label_kwargs[labelname] = ""
        with pytest.raises(AssertionError):
            EntityMetric(**label_kwargs)


def test_entity_metric_generates_alphabetically_ordered_labels() -> None:
    """Test using EntityMetric to format a simple metric string with labels alphabetically ordered."""
    domain = "sensor"
    object_id = "outside_temperature"

    static_metric_string = (
        "homeassistant_sensor_temperature_celsius{"
        'domain="sensor",'
        'entity="sensor.outside_temperature",'
        'friendly_name="Outside Temperature",'
        'zed_label="foo"'
        "}"
        " 17.2"
    )

    ordered_entity_metric = EntityMetric(
        metric_name="homeassistant_sensor_temperature_celsius",
        domain=domain,
        entity=f"{domain}.{object_id}",
        friendly_name="Outside Temperature",
        zed_label="foo",
    ).withValue(17.2)
    assert ordered_entity_metric._metric_string == static_metric_string

    unordered_entity_metric = EntityMetric(
        metric_name="homeassistant_sensor_temperature_celsius",
        zed_label="foo",
        entity=f"{domain}.{object_id}",
        friendly_name="Outside Temperature",
        domain=domain,
    ).withValue(17.2)
    assert unordered_entity_metric._metric_string == static_metric_string


def test_entity_metric_generates_metric_string_with_non_required_labels() -> None:
    """Test using EntityMetric to format a simple metric string but with extra labels and values included."""
    mode_entity_metric = EntityMetric(
        metric_name="climate_preset_mode",
        domain="climate",
        friendly_name="Ecobee",
        entity="climate.ecobee",
        mode="away",
    ).withValue(1)
    assert mode_entity_metric._metric_string == (
        "climate_preset_mode{"
        'domain="climate",'
        'entity="climate.ecobee",'
        'friendly_name="Ecobee",'
        'mode="away"'
        "}"
        " 1.0"
    )

    action_entity_metric = EntityMetric(
        metric_name="climate_action",
        domain="climate",
        friendly_name="HeatPump",
        entity="climate.heatpump",
        action="heating",
    ).withValue(1)
    assert action_entity_metric._metric_string == (
        "climate_action{"
        'action="heating",'
        'domain="climate",'
        'entity="climate.heatpump",'
        'friendly_name="HeatPump"'
        "}"
        " 1.0"
    )

    state_entity_metric = EntityMetric(
        metric_name="cover_state",
        domain="cover",
        friendly_name="Curtain",
        entity="cover.curtain",
        state="open",
    ).withValue(1)
    assert state_entity_metric._metric_string == (
        "cover_state{"
        'domain="cover",'
        'entity="cover.curtain",'
        'friendly_name="Curtain",'
        'state="open"'
        "}"
        " 1.0"
    )

    foo_entity_metric = EntityMetric(
        metric_name="homeassistant_sensor_temperature_celsius",
        domain="sensor",
        friendly_name="Outside Temperature",
        entity="sensor.outside_temperature",
        foo="bar",
    ).withValue(17.2)
    assert foo_entity_metric._metric_string == (
        "homeassistant_sensor_temperature_celsius{"
        'domain="sensor",'
        'entity="sensor.outside_temperature",'
        'foo="bar",'
        'friendly_name="Outside Temperature"'
        "}"
        " 17.2"
    )


def test_entity_metric_assert_helpers() -> None:
    """Test using EntityMetric for both assert_in_metrics and assert_not_in_metrics."""
    temp_metric = (
        "homeassistant_sensor_temperature_celsius{"
        'domain="sensor",'
        'entity="sensor.outside_temperature",'
        'foo="bar",'
        'friendly_name="Outside Temperature"'
        "}"
    )
    climate_metric = (
        "climate_preset_mode{"
        'domain="climate",'
        'entity="climate.ecobee",'
        'friendly_name="Ecobee",'
        'mode="away"'
        "}"
    )
    excluded_cover_metric = (
        "cover_state{"
        'domain="cover",'
        'entity="cover.curtain",'
        'friendly_name="Curtain",'
        'state="open"'
        "}"
    )
    metrics = [
        temp_metric,
        climate_metric,
    ]
    # First make sure the excluded metric is not present
    assert excluded_cover_metric not in metrics
    # now check for actual metrics
    temp_entity_metric = EntityMetric(
        metric_name="homeassistant_sensor_temperature_celsius",
        domain="sensor",
        friendly_name="Outside Temperature",
        entity="sensor.outside_temperature",
        foo="bar",
    )
    assert temp_entity_metric._metric_name_string == temp_metric
    temp_entity_metric.assert_in_metrics(metrics)

    climate_entity_metric = EntityMetric(
        metric_name="climate_preset_mode",
        domain="climate",
        friendly_name="Ecobee",
        entity="climate.ecobee",
        mode="away",
    )
    assert climate_entity_metric._metric_name_string == climate_metric
    climate_entity_metric.assert_in_metrics(metrics)

    excluded_cover_entity_metric = EntityMetric(
        metric_name="cover_state",
        domain="cover",
        friendly_name="Curtain",
        entity="cover.curtain",
        state="open",
    )
    assert excluded_cover_entity_metric._metric_name_string == excluded_cover_metric
    excluded_cover_entity_metric.assert_not_in_metrics(metrics)


def test_entity_metric_with_value_assert_helpers() -> None:
    """Test using EntityMetricWithValue helpers, which is only assert_in_metrics."""
    temp_metric = (
        "homeassistant_sensor_temperature_celsius{"
        'domain="sensor",'
        'entity="sensor.outside_temperature",'
        'foo="bar",'
        'friendly_name="Outside Temperature"'
        "}"
        " 17.2"
    )
    climate_metric = (
        "climate_preset_mode{"
        'domain="climate",'
        'entity="climate.ecobee",'
        'friendly_name="Ecobee",'
        'mode="away"'
        "}"
        " 1.0"
    )
    metrics = [
        temp_metric,
        climate_metric,
    ]
    temp_entity_metric = EntityMetric(
        metric_name="homeassistant_sensor_temperature_celsius",
        domain="sensor",
        friendly_name="Outside Temperature",
        entity="sensor.outside_temperature",
        foo="bar",
    ).withValue(17.2)
    assert temp_entity_metric._metric_string == temp_metric
    temp_entity_metric.assert_in_metrics(metrics)

    climate_entity_metric = EntityMetric(
        metric_name="climate_preset_mode",
        domain="climate",
        friendly_name="Ecobee",
        entity="climate.ecobee",
        mode="away",
    ).withValue(1)
    assert climate_entity_metric._metric_string == climate_metric
    climate_entity_metric.assert_in_metrics(metrics)


@pytest.fixture(name="client")
async def setup_prometheus_client(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    namespace: str,
):
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


@pytest.mark.parametrize("namespace", [""])
async def test_setup_enumeration(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    entity_registry: er.EntityRegistry,
    namespace: str,
) -> None:
    """Test that setup enumerates existing states/entities."""

    # The order of when things are created must be carefully controlled in
    # this test, so we don't use fixtures.

    sensor_1 = entity_registry.async_get_or_create(
        domain=sensor.DOMAIN,
        platform="test",
        unique_id="sensor_1",
        unit_of_measurement=UnitOfTemperature.CELSIUS,
        original_device_class=SensorDeviceClass.TEMPERATURE,
        suggested_object_id="outside_temperature",
        original_name="Outside Temperature",
    )
    state = 12.3
    set_state_with_entry(hass, sensor_1, state, {})
    assert await async_setup_component(hass, prometheus.DOMAIN, {prometheus.DOMAIN: {}})

    client = await hass_client()
    body = await generate_latest_metrics(client)
    EntityMetric(
        metric_name="homeassistant_sensor_temperature_celsius",
        domain="sensor",
        friendly_name="Outside Temperature",
        entity="sensor.outside_temperature",
    ).withValue(state).assert_in_metrics(body)


@pytest.mark.parametrize("namespace", [""])
async def test_view_empty_namespace(
    client: ClientSessionGenerator, sensor_entities: dict[str, er.RegistryEntry]
) -> None:
    """Test prometheus metrics view."""
    body = await generate_latest_metrics(client)

    assert "# HELP python_info Python platform information" in body
    assert (
        "# HELP python_gc_objects_collected_total "
        "Objects collected during gc" in body
    )

    EntityMetric(
        metric_name="entity_available",
        domain="sensor",
        friendly_name="Radio Energy",
        entity="sensor.radio_energy",
    ).withValue(1).assert_in_metrics(body)

    EntityMetric(
        metric_name="last_updated_time_seconds",
        domain="sensor",
        friendly_name="Radio Energy",
        entity="sensor.radio_energy",
    ).withValue(86400.0).assert_in_metrics(body)


@pytest.mark.parametrize("namespace", [None])
async def test_view_default_namespace(
    client: ClientSessionGenerator, sensor_entities: dict[str, er.RegistryEntry]
) -> None:
    """Test prometheus metrics view."""
    body = await generate_latest_metrics(client)

    assert "# HELP python_info Python platform information" in body
    assert (
        "# HELP python_gc_objects_collected_total "
        "Objects collected during gc" in body
    )

    EntityMetric(
        metric_name="homeassistant_sensor_temperature_celsius",
        domain="sensor",
        friendly_name="Outside Temperature",
        entity="sensor.outside_temperature",
    ).withValue(15.6).assert_in_metrics(body)


@pytest.mark.parametrize("namespace", [""])
async def test_sensor_unit(
    client: ClientSessionGenerator, sensor_entities: dict[str, er.RegistryEntry]
) -> None:
    """Test prometheus metrics for sensors with a unit."""
    body = await generate_latest_metrics(client)

    EntityMetric(
        metric_name="sensor_unit_kwh",
        domain="sensor",
        friendly_name="Television Energy",
        entity="sensor.television_energy",
    ).withValue(74.0).assert_in_metrics(body)

    EntityMetric(
        metric_name="sensor_unit_sek_per_kwh",
        domain="sensor",
        friendly_name="Electricity price",
        entity="sensor.electricity_price",
    ).withValue(0.123).assert_in_metrics(body)

    EntityMetric(
        metric_name="sensor_unit_u0xb0",
        domain="sensor",
        friendly_name="Wind Direction",
        entity="sensor.wind_direction",
    ).withValue(25.0).assert_in_metrics(body)

    EntityMetric(
        metric_name="sensor_unit_u0xb5g_per_mu0xb3",
        domain="sensor",
        friendly_name="SPS30 PM <1µm Weight concentration",
        entity="sensor.sps30_pm_1um_weight_concentration",
    ).withValue(3.7069).assert_in_metrics(body)


@pytest.mark.parametrize("namespace", [""])
async def test_sensor_without_unit(
    client: ClientSessionGenerator, sensor_entities: dict[str, er.RegistryEntry]
) -> None:
    """Test prometheus metrics for sensors without a unit."""
    body = await generate_latest_metrics(client)

    EntityMetric(
        metric_name="sensor_state",
        domain="sensor",
        friendly_name="Trend Gradient",
        entity="sensor.trend_gradient",
    ).withValue(0.002).assert_in_metrics(body)

    EntityMetric(
        metric_name="sensor_state",
        domain="sensor",
        friendly_name="Text",
        entity="sensor.text",
    ).assert_not_in_metrics(body)

    EntityMetric(
        metric_name="sensor_unit_text",
        domain="sensor",
        friendly_name="Text Unit",
        entity="sensor.text_unit",
    ).assert_not_in_metrics(body)


@pytest.mark.parametrize("namespace", [""])
async def test_sensor_device_class(
    client: ClientSessionGenerator, sensor_entities: dict[str, er.RegistryEntry]
) -> None:
    """Test prometheus metrics for sensor with a device_class."""
    body = await generate_latest_metrics(client)

    EntityMetric(
        metric_name="sensor_temperature_celsius",
        domain="sensor",
        friendly_name="Fahrenheit",
        entity="sensor.fahrenheit",
    ).withValue(10.0).assert_in_metrics(body)

    EntityMetric(
        metric_name="sensor_temperature_celsius",
        domain="sensor",
        friendly_name="Outside Temperature",
        entity="sensor.outside_temperature",
    ).withValue(15.6).assert_in_metrics(body)

    EntityMetric(
        metric_name="sensor_humidity_percent",
        domain="sensor",
        friendly_name="Outside Humidity",
        entity="sensor.outside_humidity",
    ).withValue(54.0).assert_in_metrics(body)

    EntityMetric(
        metric_name="sensor_power_kwh",
        domain="sensor",
        friendly_name="Radio Energy",
        entity="sensor.radio_energy",
    ).withValue(14.0).assert_in_metrics(body)

    EntityMetric(
        metric_name="sensor_timestamp_seconds",
        domain="sensor",
        friendly_name="Timestamp",
        entity="sensor.timestamp",
    ).withValue(1.691445808136036e09).assert_in_metrics(body)


@pytest.mark.parametrize("namespace", [""])
async def test_input_number(
    client: ClientSessionGenerator, input_number_entities: dict[str, er.RegistryEntry]
) -> None:
    """Test prometheus metrics for input_number."""
    body = await generate_latest_metrics(client)

    EntityMetric(
        metric_name="input_number_state",
        domain="input_number",
        friendly_name="Threshold",
        entity="input_number.threshold",
    ).withValue(5.2).assert_in_metrics(body)

    EntityMetric(
        metric_name="input_number_state",
        domain="input_number",
        friendly_name="None",
        entity="input_number.brightness",
    ).withValue(60.0).assert_in_metrics(body)

    EntityMetric(
        metric_name="input_number_state_celsius",
        domain="input_number",
        friendly_name="Target temperature",
        entity="input_number.target_temperature",
    ).withValue(22.7).assert_in_metrics(body)

    EntityMetric(
        metric_name="input_number_state_celsius",
        domain="input_number",
        friendly_name="Converted temperature",
        entity="input_number.converted_temperature",
    ).withValue(100).assert_in_metrics(body)


@pytest.mark.parametrize("namespace", [""])
async def test_number(
    client: ClientSessionGenerator, number_entities: dict[str, er.RegistryEntry]
) -> None:
    """Test prometheus metrics for number."""
    body = await generate_latest_metrics(client)

    EntityMetric(
        metric_name="number_state",
        domain="number",
        friendly_name="Threshold",
        entity="number.threshold",
    ).withValue(5.2).assert_in_metrics(body)

    EntityMetric(
        metric_name="number_state",
        domain="number",
        friendly_name="None",
        entity="number.brightness",
    ).withValue(60.0).assert_in_metrics(body)

    EntityMetric(
        metric_name="number_state_celsius",
        domain="number",
        friendly_name="Target temperature",
        entity="number.target_temperature",
    ).withValue(22.7).assert_in_metrics(body)


@pytest.mark.parametrize("namespace", [""])
async def test_battery(
    client: ClientSessionGenerator, sensor_entities: dict[str, er.RegistryEntry]
) -> None:
    """Test prometheus metrics for battery."""
    body = await generate_latest_metrics(client)

    EntityMetric(
        metric_name="battery_level_percent",
        domain="sensor",
        friendly_name="Outside Temperature",
        entity="sensor.outside_temperature",
    ).withValue(12.0).assert_in_metrics(body)


@pytest.mark.parametrize("namespace", [""])
async def test_climate(
    client: ClientSessionGenerator,
    climate_entities: dict[str, er.RegistryEntry | dict[str, Any]],
) -> None:
    """Test prometheus metrics for climate entities."""
    body = await generate_latest_metrics(client)

    EntityMetric(
        metric_name="climate_current_temperature_celsius",
        domain="climate",
        friendly_name="HeatPump",
        entity="climate.heatpump",
    ).withValue(25.0).assert_in_metrics(body)

    EntityMetric(
        metric_name="climate_target_temperature_celsius",
        domain="climate",
        friendly_name="HeatPump",
        entity="climate.heatpump",
    ).withValue(20.0).assert_in_metrics(body)

    EntityMetric(
        metric_name="climate_target_temperature_low_celsius",
        domain="climate",
        friendly_name="Ecobee",
        entity="climate.ecobee",
    ).withValue(21.0).assert_in_metrics(body)

    EntityMetric(
        metric_name="climate_target_temperature_high_celsius",
        domain="climate",
        friendly_name="Ecobee",
        entity="climate.ecobee",
    ).withValue(24.0).assert_in_metrics(body)

    EntityMetric(
        metric_name="climate_target_temperature_celsius",
        domain="climate",
        friendly_name="Fritz!DECT",
        entity="climate.fritzdect",
    ).withValue(0.0).assert_in_metrics(body)

    EntityMetric(
        metric_name="climate_preset_mode",
        domain="climate",
        friendly_name="Ecobee",
        entity="climate.ecobee",
        mode="away",
    ).withValue(1).assert_in_metrics(body)

    EntityMetric(
        metric_name="climate_fan_mode",
        domain="climate",
        friendly_name="Ecobee",
        entity="climate.ecobee",
        mode="auto",
    ).withValue(1).assert_in_metrics(body)


@pytest.mark.parametrize("namespace", [""])
async def test_humidifier(
    client: ClientSessionGenerator,
    humidifier_entities: dict[str, er.RegistryEntry | dict[str, Any]],
) -> None:
    """Test prometheus metrics for humidifier entities."""
    body = await generate_latest_metrics(client)

    EntityMetric(
        metric_name="humidifier_target_humidity_percent",
        domain="humidifier",
        friendly_name="Humidifier",
        entity="humidifier.humidifier",
    ).withValue(68.0).assert_in_metrics(body)

    EntityMetric(
        metric_name="humidifier_state",
        domain="humidifier",
        friendly_name="Dehumidifier",
        entity="humidifier.dehumidifier",
    ).withValue(1).assert_in_metrics(body)

    EntityMetric(
        metric_name="humidifier_mode",
        domain="humidifier",
        friendly_name="Hygrostat",
        entity="humidifier.hygrostat",
        mode="home",
    ).withValue(1).assert_in_metrics(body)

    EntityMetric(
        metric_name="humidifier_mode",
        domain="humidifier",
        friendly_name="Hygrostat",
        entity="humidifier.hygrostat",
        mode="eco",
    ).withValue(0.0).assert_in_metrics(body)


@pytest.mark.parametrize("namespace", [""])
async def test_attributes(
    client: ClientSessionGenerator,
    switch_entities: dict[str, er.RegistryEntry | dict[str, Any]],
) -> None:
    """Test prometheus metrics for entity attributes."""
    body = await generate_latest_metrics(client)

    EntityMetric(
        metric_name="switch_state",
        domain="switch",
        friendly_name="Boolean",
        entity="switch.boolean",
    ).withValue(1).assert_in_metrics(body)

    EntityMetric(
        metric_name="switch_attr_boolean",
        domain="switch",
        friendly_name="Boolean",
        entity="switch.boolean",
    ).withValue(1).assert_in_metrics(body)

    EntityMetric(
        metric_name="switch_state",
        domain="switch",
        friendly_name="Number",
        entity="switch.number",
    ).withValue(0.0).assert_in_metrics(body)

    EntityMetric(
        metric_name="switch_attr_number",
        domain="switch",
        friendly_name="Number",
        entity="switch.number",
    ).withValue(10.2).assert_in_metrics(body)


@pytest.mark.parametrize("namespace", [""])
async def test_binary_sensor(
    client: ClientSessionGenerator, binary_sensor_entities: dict[str, er.RegistryEntry]
) -> None:
    """Test prometheus metrics for binary_sensor."""
    body = await generate_latest_metrics(client)

    EntityMetric(
        metric_name="binary_sensor_state",
        domain="binary_sensor",
        friendly_name="Door",
        entity="binary_sensor.door",
    ).withValue(1).assert_in_metrics(body)

    EntityMetric(
        metric_name="binary_sensor_state",
        domain="binary_sensor",
        friendly_name="Window",
        entity="binary_sensor.window",
    ).withValue(0.0).assert_in_metrics(body)


@pytest.mark.parametrize("namespace", [""])
async def test_input_boolean(
    client: ClientSessionGenerator, input_boolean_entities: dict[str, er.RegistryEntry]
) -> None:
    """Test prometheus metrics for input_boolean."""
    body = await generate_latest_metrics(client)

    EntityMetric(
        metric_name="input_boolean_state",
        domain="input_boolean",
        friendly_name="Test",
        entity="input_boolean.test",
    ).withValue(1).assert_in_metrics(body)

    EntityMetric(
        metric_name="input_boolean_state",
        domain="input_boolean",
        friendly_name="Helper",
        entity="input_boolean.helper",
    ).withValue(0.0).assert_in_metrics(body)


@pytest.mark.parametrize("namespace", [""])
async def test_light(
    client: ClientSessionGenerator, light_entities: dict[str, er.RegistryEntry]
) -> None:
    """Test prometheus metrics for lights."""
    body = await generate_latest_metrics(client)

    EntityMetric(
        metric_name="light_brightness_percent",
        domain="light",
        friendly_name="Desk",
        entity="light.desk",
    ).withValue(100.0).assert_in_metrics(body)

    EntityMetric(
        metric_name="light_brightness_percent",
        domain="light",
        friendly_name="Wall",
        entity="light.wall",
    ).withValue(0.0).assert_in_metrics(body)

    EntityMetric(
        metric_name="light_brightness_percent",
        domain="light",
        friendly_name="TV",
        entity="light.tv",
    ).withValue(100.0).assert_in_metrics(body)

    EntityMetric(
        metric_name="light_brightness_percent",
        domain="light",
        friendly_name="PC",
        entity="light.pc",
    ).withValue(70.58823529411765).assert_in_metrics(body)

    EntityMetric(
        metric_name="light_brightness_percent",
        domain="light",
        friendly_name="Hallway",
        entity="light.hallway",
    ).withValue(100.0).assert_in_metrics(body)


@pytest.mark.parametrize("namespace", [""])
async def test_lock(
    client: ClientSessionGenerator, lock_entities: dict[str, er.RegistryEntry]
) -> None:
    """Test prometheus metrics for lock."""
    body = await generate_latest_metrics(client)

    EntityMetric(
        metric_name="lock_state",
        domain="lock",
        friendly_name="Front Door",
        entity="lock.front_door",
    ).withValue(1).assert_in_metrics(body)

    EntityMetric(
        metric_name="lock_state",
        domain="lock",
        friendly_name="Kitchen Door",
        entity="lock.kitchen_door",
    ).withValue(0.0).assert_in_metrics(body)


@pytest.mark.parametrize("namespace", [""])
async def test_fan(
    client: ClientSessionGenerator, fan_entities: dict[str, er.RegistryEntry]
) -> None:
    """Test prometheus metrics for fan."""
    body = await generate_latest_metrics(client)

    EntityMetric(
        metric_name="fan_state",
        domain="fan",
        friendly_name="Fan 1",
        entity="fan.fan_1",
    ).withValue(1).assert_in_metrics(body)

    EntityMetric(
        metric_name="fan_speed_percent",
        domain="fan",
        friendly_name="Fan 1",
        entity="fan.fan_1",
    ).withValue(33.0).assert_in_metrics(body)

    EntityMetric(
        metric_name="fan_is_oscillating",
        domain="fan",
        friendly_name="Fan 1",
        entity="fan.fan_1",
    ).withValue(1).assert_in_metrics(body)

    EntityMetric(
        metric_name="fan_direction_reversed",
        domain="fan",
        friendly_name="Fan 1",
        entity="fan.fan_1",
    ).withValue(0.0).assert_in_metrics(body)

    EntityMetric(
        metric_name="fan_preset_mode",
        domain="fan",
        friendly_name="Fan 1",
        entity="fan.fan_1",
        mode="LO",
    ).withValue(1).assert_in_metrics(body)

    EntityMetric(
        metric_name="fan_direction_reversed",
        domain="fan",
        friendly_name="Reverse Fan",
        entity="fan.fan_2",
    ).withValue(1).assert_in_metrics(body)


@pytest.mark.parametrize("namespace", [""])
async def test_alarm_control_panel(
    client: ClientSessionGenerator,
    alarm_control_panel_entities: dict[str, er.RegistryEntry],
) -> None:
    """Test prometheus metrics for alarm control panel."""
    body = await generate_latest_metrics(client)

    EntityMetric(
        metric_name="alarm_control_panel_state",
        domain="alarm_control_panel",
        friendly_name="Alarm Control Panel 1",
        entity="alarm_control_panel.alarm_control_panel_1",
        state="armed_away",
    ).withValue(1).assert_in_metrics(body)

    EntityMetric(
        metric_name="alarm_control_panel_state",
        domain="alarm_control_panel",
        friendly_name="Alarm Control Panel 1",
        entity="alarm_control_panel.alarm_control_panel_1",
        state="disarmed",
    ).withValue(0.0).assert_in_metrics(body)

    EntityMetric(
        metric_name="alarm_control_panel_state",
        domain="alarm_control_panel",
        friendly_name="Alarm Control Panel 2",
        entity="alarm_control_panel.alarm_control_panel_2",
        state="armed_home",
    ).withValue(1).assert_in_metrics(body)

    EntityMetric(
        metric_name="alarm_control_panel_state",
        domain="alarm_control_panel",
        friendly_name="Alarm Control Panel 2",
        entity="alarm_control_panel.alarm_control_panel_2",
        state="armed_away",
    ).withValue(0.0).assert_in_metrics(body)


@pytest.mark.parametrize("namespace", [""])
async def test_cover(
    client: ClientSessionGenerator, cover_entities: dict[str, er.RegistryEntry]
) -> None:
    """Test prometheus metrics for cover."""
    data = {**cover_entities}
    body = await generate_latest_metrics(client)

    open_covers = ["cover_open", "cover_position", "cover_tilt_position"]
    for testcover in data:
        EntityMetric(
            metric_name="cover_state",
            domain="cover",
            friendly_name=cover_entities[testcover].original_name,
            entity=cover_entities[testcover].entity_id,
            state="open",
        ).withValue(
            1.0 if cover_entities[testcover].unique_id in open_covers else 0.0
        ).assert_in_metrics(body)

        EntityMetric(
            metric_name="cover_state",
            domain="cover",
            friendly_name=cover_entities[testcover].original_name,
            entity=cover_entities[testcover].entity_id,
            state="closed",
        ).withValue(
            1.0 if cover_entities[testcover].unique_id == "cover_closed" else 0.0
        ).assert_in_metrics(body)

        EntityMetric(
            metric_name="cover_state",
            domain="cover",
            friendly_name=cover_entities[testcover].original_name,
            entity=cover_entities[testcover].entity_id,
            state="opening",
        ).withValue(
            1.0 if cover_entities[testcover].unique_id == "cover_opening" else 0.0
        ).assert_in_metrics(body)

        EntityMetric(
            metric_name="cover_state",
            domain="cover",
            friendly_name=cover_entities[testcover].original_name,
            entity=cover_entities[testcover].entity_id,
            state="closing",
        ).withValue(
            1.0 if cover_entities[testcover].unique_id == "cover_closing" else 0.0
        ).assert_in_metrics(body)

        if testcover == "cover_position":
            EntityMetric(
                metric_name="cover_position",
                domain="cover",
                friendly_name=cover_entities[testcover].original_name,
                entity=cover_entities[testcover].entity_id,
            ).withValue(50.0).assert_in_metrics(body)

        if testcover == "cover_tilt_position":
            EntityMetric(
                metric_name="cover_tilt_position",
                domain="cover",
                friendly_name=cover_entities[testcover].original_name,
                entity=cover_entities[testcover].entity_id,
            ).withValue(50.0).assert_in_metrics(body)


@pytest.mark.parametrize("namespace", [""])
async def test_device_tracker(
    client: ClientSessionGenerator, device_tracker_entities: dict[str, er.RegistryEntry]
) -> None:
    """Test prometheus metrics for device_tracker."""
    body = await generate_latest_metrics(client)

    EntityMetric(
        metric_name="device_tracker_state",
        domain="device_tracker",
        friendly_name="Phone",
        entity="device_tracker.phone",
    ).withValue(1).assert_in_metrics(body)

    EntityMetric(
        metric_name="device_tracker_state",
        domain="device_tracker",
        friendly_name="Watch",
        entity="device_tracker.watch",
    ).withValue(0.0).assert_in_metrics(body)


@pytest.mark.parametrize("namespace", [""])
async def test_person(
    client: ClientSessionGenerator, person_entities: dict[str, er.RegistryEntry]
) -> None:
    """Test prometheus metrics for person."""
    body = await generate_latest_metrics(client)

    EntityMetric(
        metric_name="person_state",
        domain="person",
        friendly_name="Bob",
        entity="person.bob",
    ).withValue(1).assert_in_metrics(body)
    EntityMetric(
        metric_name="person_state",
        domain="person",
        friendly_name="Alice",
        entity="person.alice",
    ).withValue(0.0).assert_in_metrics(body)


@pytest.mark.parametrize("namespace", [""])
async def test_counter(
    client: ClientSessionGenerator, counter_entities: dict[str, er.RegistryEntry]
) -> None:
    """Test prometheus metrics for counter."""
    body = await generate_latest_metrics(client)

    EntityMetric(
        metric_name="counter_value",
        domain="counter",
        friendly_name="None",
        entity="counter.counter",
    ).withValue(2.0).assert_in_metrics(body)


@pytest.mark.parametrize("namespace", [""])
async def test_update(
    client: ClientSessionGenerator, update_entities: dict[str, er.RegistryEntry]
) -> None:
    """Test prometheus metrics for update."""
    body = await generate_latest_metrics(client)

    EntityMetric(
        metric_name="update_state",
        domain="update",
        friendly_name="Firmware",
        entity="update.firmware",
    ).withValue(1).assert_in_metrics(body)
    EntityMetric(
        metric_name="update_state",
        domain="update",
        friendly_name="Addon",
        entity="update.addon",
    ).withValue(0.0).assert_in_metrics(body)


@pytest.mark.parametrize("namespace", [""])
async def test_renaming_entity_name(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    client: ClientSessionGenerator,
    sensor_entities: dict[str, er.RegistryEntry],
    climate_entities: dict[str, er.RegistryEntry | dict[str, Any]],
) -> None:
    """Test renaming entity name."""
    data = {**sensor_entities, **climate_entities}
    body = await generate_latest_metrics(client)

    EntityMetric(
        metric_name="sensor_temperature_celsius",
        domain="sensor",
        friendly_name="Outside Temperature",
        entity="sensor.outside_temperature",
    ).withValue(15.6).assert_in_metrics(body)

    EntityMetric(
        metric_name="entity_available",
        domain="sensor",
        friendly_name="Outside Temperature",
        entity="sensor.outside_temperature",
    ).withValue(1).assert_in_metrics(body)

    EntityMetric(
        metric_name="sensor_humidity_percent",
        domain="sensor",
        friendly_name="Outside Humidity",
        entity="sensor.outside_humidity",
    ).withValue(54.0).assert_in_metrics(body)

    EntityMetric(
        metric_name="entity_available",
        domain="sensor",
        friendly_name="Outside Humidity",
        entity="sensor.outside_humidity",
    ).withValue(1).assert_in_metrics(body)

    EntityMetric(
        metric_name="climate_action",
        domain="climate",
        friendly_name="HeatPump",
        entity="climate.heatpump",
        action="heating",
    ).withValue(1).assert_in_metrics(body)

    EntityMetric(
        metric_name="climate_action",
        domain="climate",
        friendly_name="HeatPump",
        entity="climate.heatpump",
        action="cooling",
    ).withValue(0.0).assert_in_metrics(body)

    assert "sensor.outside_temperature" in entity_registry.entities
    assert "climate.heatpump" in entity_registry.entities
    entity_registry.async_update_entity(
        entity_id=data["sensor_1"].entity_id,
        name="Outside Temperature Renamed",
    )
    set_state_with_entry(
        hass,
        data["sensor_1"],
        15.6,
        {ATTR_FRIENDLY_NAME: "Outside Temperature Renamed"},
    )
    entity_registry.async_update_entity(
        entity_id=data["climate_1"].entity_id,
        name="HeatPump Renamed",
    )
    data["climate_1_attributes"] = {
        **data["climate_1_attributes"],
        ATTR_FRIENDLY_NAME: "HeatPump Renamed",
    }
    set_state_with_entry(
        hass,
        data["climate_1"],
        climate.HVACAction.HEATING,
        data["climate_1_attributes"],
    )

    await hass.async_block_till_done()
    body = await generate_latest_metrics(client)

    # Check if old metrics deleted
    body_line = "\n".join(body)
    assert 'friendly_name="Outside Temperature"' not in body_line
    assert 'friendly_name="HeatPump"' not in body_line

    # Check if new metrics created
    EntityMetric(
        metric_name="sensor_temperature_celsius",
        domain="sensor",
        friendly_name="Outside Temperature Renamed",
        entity="sensor.outside_temperature",
    ).withValue(15.6).assert_in_metrics(body)

    EntityMetric(
        metric_name="entity_available",
        domain="sensor",
        friendly_name="Outside Temperature Renamed",
        entity="sensor.outside_temperature",
    ).withValue(1).assert_in_metrics(body)

    EntityMetric(
        metric_name="climate_action",
        domain="climate",
        friendly_name="HeatPump Renamed",
        entity="climate.heatpump",
        action="heating",
    ).withValue(1).assert_in_metrics(body)

    EntityMetric(
        metric_name="climate_action",
        domain="climate",
        friendly_name="HeatPump Renamed",
        entity="climate.heatpump",
        action="cooling",
    ).withValue(0.0).assert_in_metrics(body)

    # Keep other sensors
    EntityMetric(
        metric_name="sensor_humidity_percent",
        domain="sensor",
        friendly_name="Outside Humidity",
        entity="sensor.outside_humidity",
    ).withValue(54.0).assert_in_metrics(body)

    EntityMetric(
        metric_name="entity_available",
        domain="sensor",
        friendly_name="Outside Humidity",
        entity="sensor.outside_humidity",
    ).withValue(1).assert_in_metrics(body)


@pytest.mark.parametrize("namespace", [""])
async def test_renaming_entity_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    client: ClientSessionGenerator,
    sensor_entities: dict[str, er.RegistryEntry],
    climate_entities: dict[str, er.RegistryEntry | dict[str, Any]],
) -> None:
    """Test renaming entity id."""
    data = {**sensor_entities, **climate_entities}
    body = await generate_latest_metrics(client)

    EntityMetric(
        metric_name="sensor_temperature_celsius",
        domain="sensor",
        friendly_name="Outside Temperature",
        entity="sensor.outside_temperature",
    ).withValue(15.6).assert_in_metrics(body)

    EntityMetric(
        metric_name="entity_available",
        domain="sensor",
        friendly_name="Outside Temperature",
        entity="sensor.outside_temperature",
    ).withValue(1).assert_in_metrics(body)

    EntityMetric(
        metric_name="sensor_humidity_percent",
        domain="sensor",
        friendly_name="Outside Humidity",
        entity="sensor.outside_humidity",
    ).withValue(54.0).assert_in_metrics(body)

    EntityMetric(
        metric_name="entity_available",
        domain="sensor",
        friendly_name="Outside Humidity",
        entity="sensor.outside_humidity",
    ).withValue(1).assert_in_metrics(body)

    assert "sensor.outside_temperature" in entity_registry.entities
    assert "climate.heatpump" in entity_registry.entities
    entity_registry.async_update_entity(
        entity_id="sensor.outside_temperature",
        new_entity_id="sensor.outside_temperature_renamed",
    )
    set_state_with_entry(
        hass, data["sensor_1"], 15.6, None, "sensor.outside_temperature_renamed"
    )

    await hass.async_block_till_done()
    body = await generate_latest_metrics(client)

    # Check if old metrics deleted
    body_line = "\n".join(body)
    assert 'entity="sensor.outside_temperature"' not in body_line

    # Check if new metrics created
    EntityMetric(
        metric_name="sensor_temperature_celsius",
        domain="sensor",
        friendly_name="Outside Temperature",
        entity="sensor.outside_temperature_renamed",
    ).withValue(15.6).assert_in_metrics(body)

    EntityMetric(
        metric_name="entity_available",
        domain="sensor",
        friendly_name="Outside Temperature",
        entity="sensor.outside_temperature_renamed",
    ).withValue(1).assert_in_metrics(body)

    # Keep other sensors
    EntityMetric(
        metric_name="sensor_humidity_percent",
        domain="sensor",
        friendly_name="Outside Humidity",
        entity="sensor.outside_humidity",
    ).withValue(54.0).assert_in_metrics(body)
    EntityMetric(
        metric_name="entity_available",
        domain="sensor",
        friendly_name="Outside Humidity",
        entity="sensor.outside_humidity",
    ).withValue(1).assert_in_metrics(body)


@pytest.mark.parametrize("namespace", [""])
async def test_deleting_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    client: ClientSessionGenerator,
    sensor_entities: dict[str, er.RegistryEntry],
    climate_entities: dict[str, er.RegistryEntry | dict[str, Any]],
) -> None:
    """Test deleting a entity."""
    data = {**sensor_entities, **climate_entities}
    body = await generate_latest_metrics(client)

    EntityMetric(
        metric_name="sensor_temperature_celsius",
        domain="sensor",
        friendly_name="Outside Temperature",
        entity="sensor.outside_temperature",
    ).withValue(15.6).assert_in_metrics(body)

    EntityMetric(
        metric_name="entity_available",
        domain="sensor",
        friendly_name="Outside Temperature",
        entity="sensor.outside_temperature",
    ).withValue(1).assert_in_metrics(body)

    EntityMetric(
        metric_name="sensor_humidity_percent",
        domain="sensor",
        friendly_name="Outside Humidity",
        entity="sensor.outside_humidity",
    ).withValue(54.0).assert_in_metrics(body)

    EntityMetric(
        metric_name="entity_available",
        domain="sensor",
        friendly_name="Outside Humidity",
        entity="sensor.outside_humidity",
    ).withValue(1).assert_in_metrics(body)

    EntityMetric(
        metric_name="climate_action",
        domain="climate",
        friendly_name="HeatPump",
        entity="climate.heatpump",
        action="heating",
    ).withValue(1).assert_in_metrics(body)

    EntityMetric(
        metric_name="climate_action",
        domain="climate",
        friendly_name="HeatPump",
        entity="climate.heatpump",
        action="cooling",
    ).withValue(0.0).assert_in_metrics(body)

    assert "sensor.outside_temperature" in entity_registry.entities
    assert "climate.heatpump" in entity_registry.entities
    entity_registry.async_remove(data["sensor_1"].entity_id)
    entity_registry.async_remove(data["climate_1"].entity_id)

    await hass.async_block_till_done()
    body = await generate_latest_metrics(client)

    # Check if old metrics deleted
    body_line = "\n".join(body)
    assert 'entity="sensor.outside_temperature"' not in body_line
    assert 'friendly_name="Outside Temperature"' not in body_line
    assert 'entity="climate.heatpump"' not in body_line
    assert 'friendly_name="HeatPump"' not in body_line

    # Keep other sensors
    EntityMetric(
        metric_name="sensor_humidity_percent",
        domain="sensor",
        friendly_name="Outside Humidity",
        entity="sensor.outside_humidity",
    ).withValue(54.0).assert_in_metrics(body)

    EntityMetric(
        metric_name="entity_available",
        domain="sensor",
        friendly_name="Outside Humidity",
        entity="sensor.outside_humidity",
    ).withValue(1).assert_in_metrics(body)


@pytest.mark.parametrize("namespace", [""])
async def test_disabling_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    client: ClientSessionGenerator,
    sensor_entities: dict[str, er.RegistryEntry],
    climate_entities: dict[str, er.RegistryEntry | dict[str, Any]],
) -> None:
    """Test disabling a entity."""
    data = {**sensor_entities, **climate_entities}

    await hass.async_block_till_done()
    body = await generate_latest_metrics(client)

    EntityMetric(
        metric_name="sensor_temperature_celsius",
        domain="sensor",
        friendly_name="Outside Temperature",
        entity="sensor.outside_temperature",
    ).withValue(15.6).assert_in_metrics(body)

    EntityMetric(
        metric_name="state_change_total",
        domain="sensor",
        friendly_name="Outside Temperature",
        entity="sensor.outside_temperature",
    ).withValue(1).assert_in_metrics(body)

    EntityMetric(
        metric_name="state_change_created",
        domain="sensor",
        friendly_name="Outside Temperature",
        entity="sensor.outside_temperature",
    ).assert_in_metrics(body)

    EntityMetric(
        metric_name="sensor_humidity_percent",
        domain="sensor",
        friendly_name="Outside Humidity",
        entity="sensor.outside_humidity",
    ).withValue(54.0).assert_in_metrics(body)

    EntityMetric(
        metric_name="entity_available",
        domain="sensor",
        friendly_name="Outside Humidity",
        entity="sensor.outside_humidity",
    ).withValue(1).assert_in_metrics(body)

    EntityMetric(
        metric_name="climate_action",
        domain="climate",
        friendly_name="HeatPump",
        entity="climate.heatpump",
        action="heating",
    ).withValue(1).assert_in_metrics(body)

    EntityMetric(
        metric_name="climate_action",
        domain="climate",
        friendly_name="HeatPump",
        entity="climate.heatpump",
        action="cooling",
    ).withValue(0.0).assert_in_metrics(body)

    assert "sensor.outside_temperature" in entity_registry.entities
    assert "climate.heatpump" in entity_registry.entities
    entity_registry.async_update_entity(
        entity_id=data["sensor_1"].entity_id,
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    entity_registry.async_update_entity(
        entity_id="climate.heatpump",
        disabled_by=er.RegistryEntryDisabler.USER,
    )

    await hass.async_block_till_done()
    body = await generate_latest_metrics(client)

    # Check if old metrics deleted
    body_line = "\n".join(body)
    assert 'entity="sensor.outside_temperature"' not in body_line
    assert 'friendly_name="Outside Temperature"' not in body_line
    assert 'entity="climate.heatpump"' not in body_line
    assert 'friendly_name="HeatPump"' not in body_line

    # Keep other sensors
    EntityMetric(
        metric_name="sensor_humidity_percent",
        domain="sensor",
        friendly_name="Outside Humidity",
        entity="sensor.outside_humidity",
    ).withValue(54.0).assert_in_metrics(body)

    EntityMetric(
        metric_name="entity_available",
        domain="sensor",
        friendly_name="Outside Humidity",
        entity="sensor.outside_humidity",
    ).withValue(1).assert_in_metrics(body)


@pytest.mark.parametrize("namespace", [""])
@pytest.mark.parametrize("unavailable_state", [STATE_UNAVAILABLE, STATE_UNKNOWN])
async def test_entity_becomes_unavailable(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    client: ClientSessionGenerator,
    sensor_entities: dict[str, er.RegistryEntry],
    unavailable_state: str,
) -> None:
    """Test an entity that becomes unavailable/unknown is no longer exported."""
    data = {**sensor_entities}

    await hass.async_block_till_done()
    body = await generate_latest_metrics(client)

    EntityMetric(
        metric_name="sensor_temperature_celsius",
        domain="sensor",
        friendly_name="Outside Temperature",
        entity="sensor.outside_temperature",
    ).withValue(15.6).assert_in_metrics(body)

    EntityMetric(
        metric_name="state_change_total",
        domain="sensor",
        friendly_name="Outside Temperature",
        entity="sensor.outside_temperature",
    ).withValue(1).assert_in_metrics(body)

    EntityMetric(
        metric_name="entity_available",
        domain="sensor",
        friendly_name="Outside Temperature",
        entity="sensor.outside_temperature",
    ).withValue(1).assert_in_metrics(body)

    EntityMetric(
        metric_name="last_updated_time_seconds",
        domain="sensor",
        friendly_name="Outside Temperature",
        entity="sensor.outside_temperature",
    ).assert_in_metrics(body)

    EntityMetric(
        metric_name="battery_level_percent",
        domain="sensor",
        friendly_name="Outside Temperature",
        entity="sensor.outside_temperature",
    ).withValue(12.0).assert_in_metrics(body)

    EntityMetric(
        metric_name="sensor_humidity_percent",
        domain="sensor",
        friendly_name="Outside Humidity",
        entity="sensor.outside_humidity",
    ).withValue(54.0).assert_in_metrics(body)

    EntityMetric(
        metric_name="state_change_total",
        domain="sensor",
        friendly_name="Outside Humidity",
        entity="sensor.outside_humidity",
    ).withValue(1).assert_in_metrics(body)

    EntityMetric(
        metric_name="entity_available",
        domain="sensor",
        friendly_name="Outside Humidity",
        entity="sensor.outside_humidity",
    ).withValue(1).assert_in_metrics(body)

    # Make sensor_1 unavailable/unknown.
    set_state_with_entry(
        hass, data["sensor_1"], unavailable_state, data["sensor_1_attributes"]
    )

    await hass.async_block_till_done()
    body = await generate_latest_metrics(client)

    # Check that the availability changed on sensor_1 and the metric with the value is gone.
    EntityMetric(
        metric_name="sensor_temperature_celsius",
        domain="sensor",
        friendly_name="Outside Temperature",
        entity="sensor.outside_temperature",
    ).assert_not_in_metrics(body)

    EntityMetric(
        metric_name="battery_level_percent",
        domain="sensor",
        friendly_name="Outside Temperature",
        entity="sensor.outside_temperature",
    ).assert_not_in_metrics(body)

    EntityMetric(
        metric_name="state_change_total",
        domain="sensor",
        friendly_name="Outside Temperature",
        entity="sensor.outside_temperature",
    ).withValue(2.0).assert_in_metrics(body)

    EntityMetric(
        metric_name="entity_available",
        domain="sensor",
        friendly_name="Outside Temperature",
        entity="sensor.outside_temperature",
    ).withValue(0.0).assert_in_metrics(body)

    EntityMetric(
        metric_name="last_updated_time_seconds",
        domain="sensor",
        friendly_name="Outside Temperature",
        entity="sensor.outside_temperature",
    ).assert_in_metrics(body)

    # The other sensor should be unchanged.
    EntityMetric(
        metric_name="sensor_humidity_percent",
        domain="sensor",
        friendly_name="Outside Humidity",
        entity="sensor.outside_humidity",
    ).withValue(54.0).assert_in_metrics(body)

    EntityMetric(
        metric_name="state_change_total",
        domain="sensor",
        friendly_name="Outside Humidity",
        entity="sensor.outside_humidity",
    ).withValue(1).assert_in_metrics(body)

    EntityMetric(
        metric_name="entity_available",
        domain="sensor",
        friendly_name="Outside Humidity",
        entity="sensor.outside_humidity",
    ).withValue(1).assert_in_metrics(body)

    # Bring sensor_1 back and check that it returned.
    set_state_with_entry(hass, data["sensor_1"], 201.0, data["sensor_1_attributes"])

    await hass.async_block_till_done()
    body = await generate_latest_metrics(client)

    EntityMetric(
        metric_name="sensor_temperature_celsius",
        domain="sensor",
        friendly_name="Outside Temperature",
        entity="sensor.outside_temperature",
    ).withValue(201.0).assert_in_metrics(body)

    EntityMetric(
        metric_name="battery_level_percent",
        domain="sensor",
        friendly_name="Outside Temperature",
        entity="sensor.outside_temperature",
    ).withValue(12.0).assert_in_metrics(body)

    EntityMetric(
        metric_name="state_change_total",
        domain="sensor",
        friendly_name="Outside Temperature",
        entity="sensor.outside_temperature",
    ).withValue(3.0).assert_in_metrics(body)

    EntityMetric(
        metric_name="entity_available",
        domain="sensor",
        friendly_name="Outside Temperature",
        entity="sensor.outside_temperature",
    ).withValue(1).assert_in_metrics(body)


@pytest.fixture(name="sensor_entities")
async def sensor_fixture(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> dict[str, er.RegistryEntry]:
    """Simulate sensor entities."""
    data = {}
    sensor_1 = entity_registry.async_get_or_create(
        domain=sensor.DOMAIN,
        platform="test",
        unique_id="sensor_1",
        unit_of_measurement=UnitOfTemperature.CELSIUS,
        original_device_class=SensorDeviceClass.TEMPERATURE,
        suggested_object_id="outside_temperature",
        original_name="Outside Temperature",
    )
    sensor_1_attributes = {ATTR_BATTERY_LEVEL: 12}
    set_state_with_entry(hass, sensor_1, 15.6, sensor_1_attributes)
    data["sensor_1"] = sensor_1
    data["sensor_1_attributes"] = sensor_1_attributes

    sensor_2 = entity_registry.async_get_or_create(
        domain=sensor.DOMAIN,
        platform="test",
        unique_id="sensor_2",
        unit_of_measurement=PERCENTAGE,
        original_device_class=SensorDeviceClass.HUMIDITY,
        suggested_object_id="outside_humidity",
        original_name="Outside Humidity",
    )
    set_state_with_entry(hass, sensor_2, 54.0)
    data["sensor_2"] = sensor_2

    sensor_3 = entity_registry.async_get_or_create(
        domain=sensor.DOMAIN,
        platform="test",
        unique_id="sensor_3",
        unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        original_device_class=SensorDeviceClass.POWER,
        suggested_object_id="radio_energy",
        original_name="Radio Energy",
    )
    with freeze_time(datetime.datetime(1970, 1, 2, tzinfo=dt_util.UTC)):
        set_state_with_entry(hass, sensor_3, 14)
    data["sensor_3"] = sensor_3

    sensor_4 = entity_registry.async_get_or_create(
        domain=sensor.DOMAIN,
        platform="test",
        unique_id="sensor_4",
        unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_object_id="television_energy",
        original_name="Television Energy",
    )
    set_state_with_entry(hass, sensor_4, 74)
    data["sensor_4"] = sensor_4

    sensor_5 = entity_registry.async_get_or_create(
        domain=sensor.DOMAIN,
        platform="test",
        unique_id="sensor_5",
        unit_of_measurement=f"SEK/{UnitOfEnergy.KILO_WATT_HOUR}",
        suggested_object_id="electricity_price",
        original_name="Electricity price",
    )
    set_state_with_entry(hass, sensor_5, 0.123)
    data["sensor_5"] = sensor_5

    sensor_6 = entity_registry.async_get_or_create(
        domain=sensor.DOMAIN,
        platform="test",
        unique_id="sensor_6",
        unit_of_measurement=DEGREE,
        suggested_object_id="wind_direction",
        original_name="Wind Direction",
    )
    set_state_with_entry(hass, sensor_6, 25)
    data["sensor_6"] = sensor_6

    sensor_7 = entity_registry.async_get_or_create(
        domain=sensor.DOMAIN,
        platform="test",
        unique_id="sensor_7",
        unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        suggested_object_id="sps30_pm_1um_weight_concentration",
        original_name="SPS30 PM <1µm Weight concentration",
    )
    set_state_with_entry(hass, sensor_7, 3.7069)
    data["sensor_7"] = sensor_7

    sensor_8 = entity_registry.async_get_or_create(
        domain=sensor.DOMAIN,
        platform="test",
        unique_id="sensor_8",
        suggested_object_id="trend_gradient",
        original_name="Trend Gradient",
    )
    set_state_with_entry(hass, sensor_8, 0.002)
    data["sensor_8"] = sensor_8

    sensor_9 = entity_registry.async_get_or_create(
        domain=sensor.DOMAIN,
        platform="test",
        unique_id="sensor_9",
        suggested_object_id="text",
        original_name="Text",
    )
    set_state_with_entry(hass, sensor_9, "should_not_work")
    data["sensor_9"] = sensor_9

    sensor_10 = entity_registry.async_get_or_create(
        domain=sensor.DOMAIN,
        platform="test",
        unique_id="sensor_10",
        unit_of_measurement="Text",
        suggested_object_id="text_unit",
        original_name="Text Unit",
    )
    set_state_with_entry(hass, sensor_10, "should_not_work")
    data["sensor_10"] = sensor_10

    sensor_11 = entity_registry.async_get_or_create(
        domain=sensor.DOMAIN,
        platform="test",
        unique_id="sensor_11",
        unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        original_device_class=SensorDeviceClass.TEMPERATURE,
        suggested_object_id="fahrenheit",
        original_name="Fahrenheit",
    )
    set_state_with_entry(hass, sensor_11, 50)
    data["sensor_11"] = sensor_11

    sensor_12 = entity_registry.async_get_or_create(
        domain=sensor.DOMAIN,
        platform="test",
        unique_id="sensor_12",
        original_device_class=SensorDeviceClass.TIMESTAMP,
        suggested_object_id="Timestamp",
        original_name="Timestamp",
    )
    set_state_with_entry(hass, sensor_12, "2023-08-07T15:03:28.136036-0700")
    data["sensor_12"] = sensor_12
    await hass.async_block_till_done()
    return data


@pytest.fixture(name="climate_entities")
async def climate_fixture(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> dict[str, er.RegistryEntry | dict[str, Any]]:
    """Simulate climate entities."""
    data = {}
    climate_1 = entity_registry.async_get_or_create(
        domain=climate.DOMAIN,
        platform="test",
        unique_id="climate_1",
        unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_object_id="heatpump",
        original_name="HeatPump",
    )
    climate_1_attributes = {
        ATTR_TEMPERATURE: 20,
        ATTR_CURRENT_TEMPERATURE: 25,
        ATTR_HVAC_ACTION: climate.HVACAction.HEATING,
    }
    set_state_with_entry(
        hass, climate_1, climate.HVACAction.HEATING, climate_1_attributes
    )
    data["climate_1"] = climate_1
    data["climate_1_attributes"] = climate_1_attributes

    climate_2 = entity_registry.async_get_or_create(
        domain=climate.DOMAIN,
        platform="test",
        unique_id="climate_2",
        unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_object_id="ecobee",
        original_name="Ecobee",
    )
    climate_2_attributes = {
        ATTR_TEMPERATURE: 21,
        ATTR_CURRENT_TEMPERATURE: 22,
        ATTR_TARGET_TEMP_LOW: 21,
        ATTR_TARGET_TEMP_HIGH: 24,
        ATTR_HVAC_ACTION: climate.HVACAction.COOLING,
        ATTR_HVAC_MODES: ["off", "heat", "cool", "heat_cool"],
        ATTR_PRESET_MODE: "away",
        ATTR_PRESET_MODES: ["away", "home", "sleep"],
        ATTR_FAN_MODE: "auto",
        ATTR_FAN_MODES: ["auto", "on"],
    }
    set_state_with_entry(
        hass, climate_2, climate.HVACAction.HEATING, climate_2_attributes
    )
    data["climate_2"] = climate_2
    data["climate_2_attributes"] = climate_2_attributes

    climate_3 = entity_registry.async_get_or_create(
        domain=climate.DOMAIN,
        platform="test",
        unique_id="climate_3",
        unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_object_id="fritzdect",
        original_name="Fritz!DECT",
    )
    climate_3_attributes = {
        ATTR_TEMPERATURE: 0,
        ATTR_CURRENT_TEMPERATURE: 22,
        ATTR_HVAC_ACTION: climate.HVACAction.OFF,
    }
    set_state_with_entry(hass, climate_3, climate.HVACAction.OFF, climate_3_attributes)
    data["climate_3"] = climate_3
    data["climate_3_attributes"] = climate_3_attributes

    await hass.async_block_till_done()
    return data


@pytest.fixture(name="humidifier_entities")
async def humidifier_fixture(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> dict[str, er.RegistryEntry | dict[str, Any]]:
    """Simulate humidifier entities."""
    data = {}
    humidifier_1 = entity_registry.async_get_or_create(
        domain=humidifier.DOMAIN,
        platform="test",
        unique_id="humidifier_1",
        original_device_class=humidifier.HumidifierDeviceClass.HUMIDIFIER,
        suggested_object_id="humidifier",
        original_name="Humidifier",
    )
    humidifier_1_attributes = {
        ATTR_HUMIDITY: 68,
    }
    set_state_with_entry(hass, humidifier_1, STATE_ON, humidifier_1_attributes)
    data["humidifier_1"] = humidifier_1
    data["humidifier_1_attributes"] = humidifier_1_attributes

    humidifier_2 = entity_registry.async_get_or_create(
        domain=humidifier.DOMAIN,
        platform="test",
        unique_id="humidifier_2",
        original_device_class=humidifier.HumidifierDeviceClass.DEHUMIDIFIER,
        suggested_object_id="dehumidifier",
        original_name="Dehumidifier",
    )
    humidifier_2_attributes = {
        ATTR_HUMIDITY: 54,
    }
    set_state_with_entry(hass, humidifier_2, STATE_ON, humidifier_2_attributes)
    data["humidifier_2"] = humidifier_2
    data["humidifier_2_attributes"] = humidifier_2_attributes

    humidifier_3 = entity_registry.async_get_or_create(
        domain=humidifier.DOMAIN,
        platform="test",
        unique_id="humidifier_3",
        suggested_object_id="hygrostat",
        original_name="Hygrostat",
    )
    humidifier_3_attributes = {
        ATTR_HUMIDITY: 50,
        ATTR_MODE: "home",
        ATTR_AVAILABLE_MODES: ["home", "eco"],
    }
    set_state_with_entry(hass, humidifier_3, STATE_ON, humidifier_3_attributes)
    data["humidifier_3"] = humidifier_3
    data["humidifier_3_attributes"] = humidifier_3_attributes

    await hass.async_block_till_done()
    return data


@pytest.fixture(name="lock_entities")
async def lock_fixture(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> dict[str, er.RegistryEntry]:
    """Simulate lock entities."""
    data = {}
    lock_1 = entity_registry.async_get_or_create(
        domain=lock.DOMAIN,
        platform="test",
        unique_id="lock_1",
        suggested_object_id="front_door",
        original_name="Front Door",
    )
    set_state_with_entry(hass, lock_1, LockState.LOCKED)
    data["lock_1"] = lock_1

    lock_2 = entity_registry.async_get_or_create(
        domain=lock.DOMAIN,
        platform="test",
        unique_id="lock_2",
        suggested_object_id="kitchen_door",
        original_name="Kitchen Door",
    )
    set_state_with_entry(hass, lock_2, LockState.UNLOCKED)
    data["lock_2"] = lock_2

    await hass.async_block_till_done()
    return data


@pytest.fixture(name="cover_entities")
async def cover_fixture(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> dict[str, er.RegistryEntry]:
    """Simulate cover entities."""
    data = {}
    cover_open = entity_registry.async_get_or_create(
        domain=cover.DOMAIN,
        platform="test",
        unique_id="cover_open",
        suggested_object_id="open_shade",
        original_name="Open Shade",
    )
    set_state_with_entry(hass, cover_open, STATE_OPEN)
    data["cover_open"] = cover_open

    cover_closed = entity_registry.async_get_or_create(
        domain=cover.DOMAIN,
        platform="test",
        unique_id="cover_closed",
        suggested_object_id="closed_shade",
        original_name="Closed Shade",
    )
    set_state_with_entry(hass, cover_closed, STATE_CLOSED)
    data["cover_closed"] = cover_closed

    cover_closing = entity_registry.async_get_or_create(
        domain=cover.DOMAIN,
        platform="test",
        unique_id="cover_closing",
        suggested_object_id="closing_shade",
        original_name="Closing Shade",
    )
    set_state_with_entry(hass, cover_closing, STATE_CLOSING)
    data["cover_closing"] = cover_closing

    cover_opening = entity_registry.async_get_or_create(
        domain=cover.DOMAIN,
        platform="test",
        unique_id="cover_opening",
        suggested_object_id="opening_shade",
        original_name="Opening Shade",
    )
    set_state_with_entry(hass, cover_opening, STATE_OPENING)
    data["cover_opening"] = cover_opening

    cover_position = entity_registry.async_get_or_create(
        domain=cover.DOMAIN,
        platform="test",
        unique_id="cover_position",
        suggested_object_id="position_shade",
        original_name="Position Shade",
    )
    cover_position_attributes = {cover.ATTR_CURRENT_POSITION: 50}
    set_state_with_entry(hass, cover_position, STATE_OPEN, cover_position_attributes)
    data["cover_position"] = cover_position

    cover_tilt_position = entity_registry.async_get_or_create(
        domain=cover.DOMAIN,
        platform="test",
        unique_id="cover_tilt_position",
        suggested_object_id="tilt_position_shade",
        original_name="Tilt Position Shade",
    )
    cover_tilt_position_attributes = {cover.ATTR_CURRENT_TILT_POSITION: 50}
    set_state_with_entry(
        hass, cover_tilt_position, STATE_OPEN, cover_tilt_position_attributes
    )
    data["cover_tilt_position"] = cover_tilt_position

    await hass.async_block_till_done()
    return data


@pytest.fixture(name="input_number_entities")
async def input_number_fixture(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> dict[str, er.RegistryEntry]:
    """Simulate input_number entities."""
    data = {}
    input_number_1 = entity_registry.async_get_or_create(
        domain=input_number.DOMAIN,
        platform="test",
        unique_id="input_number_1",
        suggested_object_id="threshold",
        original_name="Threshold",
    )
    set_state_with_entry(hass, input_number_1, 5.2)
    data["input_number_1"] = input_number_1

    input_number_2 = entity_registry.async_get_or_create(
        domain=input_number.DOMAIN,
        platform="test",
        unique_id="input_number_2",
        suggested_object_id="brightness",
    )
    set_state_with_entry(hass, input_number_2, 60)
    data["input_number_2"] = input_number_2

    input_number_3 = entity_registry.async_get_or_create(
        domain=input_number.DOMAIN,
        platform="test",
        unique_id="input_number_3",
        suggested_object_id="target_temperature",
        original_name="Target temperature",
        unit_of_measurement=UnitOfTemperature.CELSIUS,
    )
    set_state_with_entry(hass, input_number_3, 22.7)
    data["input_number_3"] = input_number_3

    input_number_4 = entity_registry.async_get_or_create(
        domain=input_number.DOMAIN,
        platform="test",
        unique_id="input_number_4",
        suggested_object_id="converted_temperature",
        original_name="Converted temperature",
        unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
    )
    set_state_with_entry(hass, input_number_4, 212)
    data["input_number_4"] = input_number_4

    await hass.async_block_till_done()
    return data


@pytest.fixture(name="number_entities")
async def number_fixture(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> dict[str, er.RegistryEntry]:
    """Simulate number entities."""
    data = {}
    number_1 = entity_registry.async_get_or_create(
        domain=number.DOMAIN,
        platform="test",
        unique_id="number_1",
        suggested_object_id="threshold",
        original_name="Threshold",
    )
    set_state_with_entry(hass, number_1, 5.2)
    data["number_1"] = number_1

    number_2 = entity_registry.async_get_or_create(
        domain=number.DOMAIN,
        platform="test",
        unique_id="number_2",
        suggested_object_id="brightness",
    )
    set_state_with_entry(hass, number_2, 60)
    data["number_2"] = number_2

    number_3 = entity_registry.async_get_or_create(
        domain=number.DOMAIN,
        platform="test",
        unique_id="number_3",
        suggested_object_id="target_temperature",
        original_name="Target temperature",
        unit_of_measurement=UnitOfTemperature.CELSIUS,
    )
    set_state_with_entry(hass, number_3, 22.7)
    data["number_3"] = number_3

    await hass.async_block_till_done()
    return data


@pytest.fixture(name="input_boolean_entities")
async def input_boolean_fixture(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> dict[str, er.RegistryEntry]:
    """Simulate input_boolean entities."""
    data = {}
    input_boolean_1 = entity_registry.async_get_or_create(
        domain=input_boolean.DOMAIN,
        platform="test",
        unique_id="input_boolean_1",
        suggested_object_id="test",
        original_name="Test",
    )
    set_state_with_entry(hass, input_boolean_1, STATE_ON)
    data["input_boolean_1"] = input_boolean_1

    input_boolean_2 = entity_registry.async_get_or_create(
        domain=input_boolean.DOMAIN,
        platform="test",
        unique_id="input_boolean_2",
        suggested_object_id="helper",
        original_name="Helper",
    )
    set_state_with_entry(hass, input_boolean_2, STATE_OFF)
    data["input_boolean_2"] = input_boolean_2

    await hass.async_block_till_done()
    return data


@pytest.fixture(name="binary_sensor_entities")
async def binary_sensor_fixture(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> dict[str, er.RegistryEntry]:
    """Simulate binary_sensor entities."""
    data = {}
    binary_sensor_1 = entity_registry.async_get_or_create(
        domain=binary_sensor.DOMAIN,
        platform="test",
        unique_id="binary_sensor_1",
        suggested_object_id="door",
        original_name="Door",
    )
    set_state_with_entry(hass, binary_sensor_1, STATE_ON)
    data["binary_sensor_1"] = binary_sensor_1

    binary_sensor_2 = entity_registry.async_get_or_create(
        domain=binary_sensor.DOMAIN,
        platform="test",
        unique_id="binary_sensor_2",
        suggested_object_id="window",
        original_name="Window",
    )
    set_state_with_entry(hass, binary_sensor_2, STATE_OFF)
    data["binary_sensor_2"] = binary_sensor_2

    await hass.async_block_till_done()
    return data


@pytest.fixture(name="light_entities")
async def light_fixture(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> dict[str, er.RegistryEntry]:
    """Simulate light entities."""
    data = {}
    light_1 = entity_registry.async_get_or_create(
        domain=light.DOMAIN,
        platform="test",
        unique_id="light_1",
        suggested_object_id="desk",
        original_name="Desk",
    )
    set_state_with_entry(hass, light_1, STATE_ON)
    data["light_1"] = light_1

    light_2 = entity_registry.async_get_or_create(
        domain=light.DOMAIN,
        platform="test",
        unique_id="light_2",
        suggested_object_id="wall",
        original_name="Wall",
    )
    set_state_with_entry(hass, light_2, STATE_OFF)
    data["light_2"] = light_2

    light_3 = entity_registry.async_get_or_create(
        domain=light.DOMAIN,
        platform="test",
        unique_id="light_3",
        suggested_object_id="tv",
        original_name="TV",
    )
    light_3_attributes = {light.ATTR_BRIGHTNESS: 255}
    set_state_with_entry(hass, light_3, STATE_ON, light_3_attributes)
    data["light_3"] = light_3
    data["light_3_attributes"] = light_3_attributes

    light_4 = entity_registry.async_get_or_create(
        domain=light.DOMAIN,
        platform="test",
        unique_id="light_4",
        suggested_object_id="pc",
        original_name="PC",
    )
    light_4_attributes = {light.ATTR_BRIGHTNESS: 180}
    set_state_with_entry(hass, light_4, STATE_ON, light_4_attributes)
    data["light_4"] = light_4
    data["light_4_attributes"] = light_4_attributes

    light_5 = entity_registry.async_get_or_create(
        domain=light.DOMAIN,
        platform="test",
        unique_id="light_5",
        suggested_object_id="hallway",
        original_name="Hallway",
    )
    # Light is on, but brightness is unset; expect metrics to report
    # brightness of 100%.
    light_5_attributes = {light.ATTR_BRIGHTNESS: None}
    set_state_with_entry(hass, light_5, STATE_ON, light_5_attributes)
    data["light_5"] = light_5
    data["light_5_attributes"] = light_5_attributes
    await hass.async_block_till_done()
    return data


@pytest.fixture(name="switch_entities")
async def switch_fixture(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> dict[str, er.RegistryEntry | dict[str, Any]]:
    """Simulate switch entities."""
    data = {}
    switch_1 = entity_registry.async_get_or_create(
        domain=switch.DOMAIN,
        platform="test",
        unique_id="switch_1",
        suggested_object_id="boolean",
        original_name="Boolean",
    )
    switch_1_attributes = {"boolean": True}
    set_state_with_entry(hass, switch_1, STATE_ON, switch_1_attributes)
    data["switch_1"] = switch_1
    data["switch_1_attributes"] = switch_1_attributes

    switch_2 = entity_registry.async_get_or_create(
        domain=switch.DOMAIN,
        platform="test",
        unique_id="switch_2",
        suggested_object_id="number",
        original_name="Number",
    )
    switch_2_attributes = {"Number": 10.2}
    set_state_with_entry(hass, switch_2, STATE_OFF, switch_2_attributes)
    data["switch_2"] = switch_2
    data["switch_2_attributes"] = switch_2_attributes

    await hass.async_block_till_done()
    return data


@pytest.fixture(name="fan_entities")
async def fan_fixture(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> dict[str, er.RegistryEntry]:
    """Simulate fan entities."""
    data = {}
    fan_1 = entity_registry.async_get_or_create(
        domain=fan.DOMAIN,
        platform="test",
        unique_id="fan_1",
        suggested_object_id="fan_1",
        original_name="Fan 1",
    )
    fan_1_attributes = {
        ATTR_DIRECTION: DIRECTION_FORWARD,
        ATTR_OSCILLATING: True,
        ATTR_PERCENTAGE: 33,
        ATTR_PRESET_MODE: "LO",
        ATTR_PRESET_MODES: ["LO", "OFF", "HI"],
    }
    set_state_with_entry(hass, fan_1, STATE_ON, fan_1_attributes)
    data["fan_1"] = fan_1
    data["fan_1_attributes"] = fan_1_attributes

    fan_2 = entity_registry.async_get_or_create(
        domain=fan.DOMAIN,
        platform="test",
        unique_id="fan_2",
        suggested_object_id="fan_2",
        original_name="Reverse Fan",
    )
    fan_2_attributes = {ATTR_DIRECTION: DIRECTION_REVERSE}
    set_state_with_entry(hass, fan_2, STATE_ON, fan_2_attributes)
    data["fan_2"] = fan_2
    data["fan_2_attributes"] = fan_2_attributes

    await hass.async_block_till_done()
    return data


@pytest.fixture(name="alarm_control_panel_entities")
async def alarm_control_panel_fixture(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> dict[str, er.RegistryEntry]:
    """Simulate alarm control panel entities."""
    data = {}
    alarm_control_panel_1 = entity_registry.async_get_or_create(
        domain=alarm_control_panel.DOMAIN,
        platform="test",
        unique_id="alarm_control_panel_1",
        suggested_object_id="alarm_control_panel_1",
        original_name="Alarm Control Panel 1",
    )
    set_state_with_entry(hass, alarm_control_panel_1, AlarmControlPanelState.ARMED_AWAY)
    data["alarm_control_panel_1"] = alarm_control_panel_1

    alarm_control_panel_2 = entity_registry.async_get_or_create(
        domain=alarm_control_panel.DOMAIN,
        platform="test",
        unique_id="alarm_control_panel_2",
        suggested_object_id="alarm_control_panel_2",
        original_name="Alarm Control Panel 2",
    )
    set_state_with_entry(hass, alarm_control_panel_2, AlarmControlPanelState.ARMED_HOME)
    data["alarm_control_panel_2"] = alarm_control_panel_2

    await hass.async_block_till_done()
    return data


@pytest.fixture(name="person_entities")
async def person_fixture(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> dict[str, er.RegistryEntry]:
    """Simulate person entities."""
    data = {}
    person_1 = entity_registry.async_get_or_create(
        domain=person.DOMAIN,
        platform="test",
        unique_id="person_1",
        suggested_object_id="bob",
        original_name="Bob",
    )
    set_state_with_entry(hass, person_1, STATE_HOME)
    data["person_1"] = person_1

    person_2 = entity_registry.async_get_or_create(
        domain=person.DOMAIN,
        platform="test",
        unique_id="person_2",
        suggested_object_id="alice",
        original_name="Alice",
    )
    set_state_with_entry(hass, person_2, STATE_NOT_HOME)
    data["person_2"] = person_2

    await hass.async_block_till_done()
    return data


@pytest.fixture(name="device_tracker_entities")
async def device_tracker_fixture(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> dict[str, er.RegistryEntry]:
    """Simulate device_tracker entities."""
    data = {}
    device_tracker_1 = entity_registry.async_get_or_create(
        domain=device_tracker.DOMAIN,
        platform="test",
        unique_id="device_tracker_1",
        suggested_object_id="phone",
        original_name="Phone",
    )
    set_state_with_entry(hass, device_tracker_1, STATE_HOME)
    data["device_tracker_1"] = device_tracker_1

    device_tracker_2 = entity_registry.async_get_or_create(
        domain=device_tracker.DOMAIN,
        platform="test",
        unique_id="device_tracker_2",
        suggested_object_id="watch",
        original_name="Watch",
    )
    set_state_with_entry(hass, device_tracker_2, STATE_NOT_HOME)
    data["device_tracker_2"] = device_tracker_2

    await hass.async_block_till_done()
    return data


@pytest.fixture(name="counter_entities")
async def counter_fixture(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> dict[str, er.RegistryEntry]:
    """Simulate counter entities."""
    data = {}
    counter_1 = entity_registry.async_get_or_create(
        domain=counter.DOMAIN,
        platform="test",
        unique_id="counter_1",
        suggested_object_id="counter",
    )
    set_state_with_entry(hass, counter_1, 2)
    data["counter_1"] = counter_1

    await hass.async_block_till_done()
    return data


@pytest.fixture(name="update_entities")
async def update_fixture(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> dict[str, er.RegistryEntry]:
    """Simulate update entities."""
    data = {}
    update_1 = entity_registry.async_get_or_create(
        domain=update.DOMAIN,
        platform="test",
        unique_id="update_1",
        suggested_object_id="firmware",
        original_name="Firmware",
    )
    set_state_with_entry(hass, update_1, STATE_ON)
    data["update_1"] = update_1

    update_2 = entity_registry.async_get_or_create(
        domain=update.DOMAIN,
        platform="test",
        unique_id="update_2",
        suggested_object_id="addon",
        original_name="Addon",
    )
    set_state_with_entry(hass, update_2, STATE_OFF)
    data["update_2"] = update_2

    await hass.async_block_till_done()
    return data


def set_state_with_entry(
    hass: HomeAssistant,
    entry: er.RegistryEntry,
    state,
    additional_attributes=None,
    new_entity_id=None,
):
    """Set the state of an entity with an Entity Registry entry."""
    attributes = {}

    if entry.original_name:
        attributes[ATTR_FRIENDLY_NAME] = entry.original_name
    if entry.unit_of_measurement:
        attributes[ATTR_UNIT_OF_MEASUREMENT] = entry.unit_of_measurement
    if entry.original_device_class:
        attributes[ATTR_DEVICE_CLASS] = entry.original_device_class

    if additional_attributes:
        attributes = {**attributes, **additional_attributes}

    hass.states.async_set(
        entity_id=new_entity_id if new_entity_id else entry.entity_id,
        new_state=state,
        attributes=attributes,
    )


@pytest.fixture(name="mock_client")
def mock_client_fixture():
    """Mock the prometheus client."""
    with mock.patch(f"{PROMETHEUS_PATH}.prometheus_client") as client:
        counter_client = mock.MagicMock()
        client.Counter = mock.MagicMock(return_value=counter_client)
        setattr(counter_client, "labels", mock.MagicMock(return_value=mock.MagicMock()))
        yield counter_client


async def test_minimal_config(hass: HomeAssistant, mock_client: mock.MagicMock) -> None:
    """Test the minimal config and defaults of component."""
    config = {prometheus.DOMAIN: {}}
    assert await async_setup_component(hass, prometheus.DOMAIN, config)
    await hass.async_block_till_done()


async def test_full_config(hass: HomeAssistant, mock_client: mock.MagicMock) -> None:
    """Test the full config of component."""
    config = {
        prometheus.DOMAIN: {
            "namespace": "ns",
            "default_metric": "m",
            "override_metric": "m",
            "requires_auth": False,
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


async def _setup(hass: HomeAssistant, filter_config):
    """Shared set up for filtering tests."""
    config = {prometheus.DOMAIN: {"filter": filter_config}}
    assert await async_setup_component(hass, prometheus.DOMAIN, config)
    await hass.async_block_till_done()


async def test_allowlist(hass: HomeAssistant, mock_client: mock.MagicMock) -> None:
    """Test an allowlist only config."""
    await _setup(
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
        hass.states.async_set(test.id, "not blank")
        await hass.async_block_till_done()

        was_called = mock_client.labels.call_count == 1
        assert test.should_pass == was_called
        mock_client.labels.reset_mock()


async def test_denylist(hass: HomeAssistant, mock_client: mock.MagicMock) -> None:
    """Test a denylist only config."""
    await _setup(
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
        hass.states.async_set(test.id, "not blank")
        await hass.async_block_till_done()

        was_called = mock_client.labels.call_count == 1
        assert test.should_pass == was_called
        mock_client.labels.reset_mock()


async def test_filtered_denylist(
    hass: HomeAssistant, mock_client: mock.MagicMock
) -> None:
    """Test a denylist config with a filtering allowlist."""
    await _setup(
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
        hass.states.async_set(test.id, "not blank")
        await hass.async_block_till_done()

        was_called = mock_client.labels.call_count == 1
        assert test.should_pass == was_called
        mock_client.labels.reset_mock()
