"""Tests for MQTT helper classes and entities."""

from __future__ import annotations

from datetime import time as dt_time
from types import SimpleNamespace

import pytest
from victron_mqtt import MetricKind, MetricNature, MetricType

from homeassistant.components.victron_remote_monitoring import (
    button as vrm_button,
    number as vrm_number,
    select as vrm_select,
    switch as vrm_switch,
    time as vrm_time,
)
from homeassistant.components.victron_remote_monitoring.binary_sensor import (
    VRMMqttBinarySensor,
)
from homeassistant.components.victron_remote_monitoring.button import VRMMqttButton
from homeassistant.components.victron_remote_monitoring.entity import VRMMqttBaseEntity
from homeassistant.components.victron_remote_monitoring.mqtt_hub import VRMMqttHub
from homeassistant.components.victron_remote_monitoring.number import VRMMqttNumber
from homeassistant.components.victron_remote_monitoring.select import VRMMqttSelect
from homeassistant.components.victron_remote_monitoring.sensor import VRMMqttSensor
from homeassistant.components.victron_remote_monitoring.switch import VRMMqttSwitch
from homeassistant.components.victron_remote_monitoring.time import VRMMqttTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo

from .conftest import FakeDevice, FakeMetric, FakeWritableMetric


class _TestEntity(VRMMqttBaseEntity):
    def __init__(
        self,
        device: FakeDevice,
        metric: FakeMetric,
        device_info: DeviceInfo,
        site_id: int,
    ) -> None:
        self.last_value = None
        super().__init__(device, metric, device_info, site_id)

    def _on_update_task(self, value) -> None:
        self.last_value = value


def _device_info() -> DeviceInfo:
    return DeviceInfo(identifiers={("victron_remote_monitoring", "device")})


def _metric(
    *,
    metric_type: MetricType,
    metric_nature: MetricNature,
    unit: str | None,
) -> FakeMetric:
    return FakeMetric(
        metric_kind=MetricKind.SENSOR,
        metric_type=metric_type,
        metric_nature=metric_nature,
        unit_of_measurement=unit,
        precision=1,
        short_id="metric",
        unique_id="metric_1",
        name="Metric",
        value=1,
    )


def _set_entity_id(entity, domain: str) -> None:
    """Assign an entity_id to allow state writes."""
    entity.entity_id = f"{domain}.test_{entity._attr_unique_id}"


@pytest.fixture(autouse=True)
def _patch_writable_metric(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure writable metric assertions accept test fakes."""
    monkeypatch.setattr(vrm_number, "VictronWritableMetric", FakeWritableMetric)
    monkeypatch.setattr(vrm_select, "VictronWritableMetric", FakeWritableMetric)
    monkeypatch.setattr(vrm_switch, "VictronWritableMetric", FakeWritableMetric)
    monkeypatch.setattr(vrm_button, "VictronWritableMetric", FakeWritableMetric)
    monkeypatch.setattr(vrm_time, "VictronWritableMetric", FakeWritableMetric)


@pytest.mark.parametrize(
    ("metric_type", "expected"),
    [
        (MetricType.POWER, "power"),
        (MetricType.APPARENT_POWER, "apparent_power"),
        (MetricType.ENERGY, "energy"),
        (MetricType.VOLTAGE, "voltage"),
        (MetricType.CURRENT, "current"),
        (MetricType.FREQUENCY, "frequency"),
        (MetricType.ELECTRIC_STORAGE_PERCENTAGE, "battery"),
        (MetricType.TEMPERATURE, "temperature"),
        (MetricType.SPEED, "speed"),
        (MetricType.LIQUID_VOLUME, "volume_storage"),
        (MetricType.DURATION, "duration"),
        (MetricType.TIME, None),
    ],
)
def test_mqtt_entity_device_class_mapping(metric_type, expected) -> None:
    """Verify device class mapping for MQTT metrics."""
    metric = _metric(
        metric_type=metric_type,
        metric_nature=MetricNature.INSTANTANEOUS,
        unit="V",
    )
    device_class = VRMMqttBaseEntity._map_device_class(metric)
    if expected is None:
        assert device_class is None
    else:
        assert device_class.value == expected


def test_mqtt_entity_device_class_mapping_default() -> None:
    """Verify device class mapping default branch."""
    metric = FakeMetric(
        metric_kind=MetricKind.SENSOR,
        metric_type=object(),
        metric_nature=MetricNature.INSTANTANEOUS,
        unit_of_measurement=None,
        precision=None,
        short_id="metric",
        unique_id="metric_default",
        name="Metric",
        value=None,
    )
    assert VRMMqttBaseEntity._map_device_class(metric) is None


@pytest.mark.parametrize(
    ("metric_nature", "expected"),
    [
        (MetricNature.CUMULATIVE, "total"),
        (MetricNature.INSTANTANEOUS, "measurement"),
        (object(), None),
    ],
)
def test_mqtt_entity_state_class_mapping(metric_nature, expected) -> None:
    """Verify state class mapping for MQTT metrics."""
    metric = _metric(
        metric_type=MetricType.POWER,
        metric_nature=metric_nature,
        unit="W",
    )
    state_class = VRMMqttBaseEntity._map_state_class(metric)
    if expected is None:
        assert state_class is None
    else:
        assert state_class.value == expected


@pytest.mark.parametrize(
    ("unit", "expected"),
    [
        ("s", "s"),
        ("min", "min"),
        ("h", "h"),
        ("V", "V"),
        (None, None),
    ],
)
def test_mqtt_entity_unit_mapping(unit, expected) -> None:
    """Verify unit mapping for MQTT metrics."""
    metric = _metric(
        metric_type=MetricType.POWER,
        metric_nature=MetricNature.INSTANTANEOUS,
        unit=unit,
    )
    mapped = VRMMqttBaseEntity._map_unit(metric)
    assert mapped == expected


async def test_mqtt_entity_update_callback(hass: HomeAssistant) -> None:
    """Ensure update callbacks set values when hass is available."""
    device = FakeDevice(unique_id="device", device_id="1", name="Device")
    metric = _metric(
        metric_type=MetricType.POWER, metric_nature=MetricNature.INSTANTANEOUS, unit="W"
    )
    entity = _TestEntity(device, metric, _device_info(), 123)

    entity._on_update(metric, 5)
    assert entity.last_value is None

    entity.hass = hass
    entity._on_update(metric, 5)
    assert entity.last_value == 5

    await entity.async_added_to_hass()
    assert metric.on_update is not None
    await entity.async_will_remove_from_hass()
    assert metric.on_update is None


def test_mqtt_hub_callback_registration() -> None:
    """Verify MQTT hub callback registration and dispatch."""
    hub = VRMMqttHub(site_id=123)
    called = SimpleNamespace(count=0)

    def callback(*_args) -> None:
        called.count += 1

    hub.register_new_metric_callback(MetricKind.SENSOR, callback)
    hub.register_new_metric_callback(MetricKind.SENSOR, callback)

    device = FakeDevice(unique_id="device", device_id="1", name="Device")
    metric = _metric(
        metric_type=MetricType.POWER, metric_nature=MetricNature.INSTANTANEOUS, unit="W"
    )
    hub._on_new_metric(SimpleNamespace(), device, metric)

    assert called.count == 1


def test_binary_sensor_update(hass: HomeAssistant) -> None:
    """Verify binary sensor update behavior."""
    device = FakeDevice(unique_id="device", device_id="1", name="Device")
    metric = _metric(
        metric_type=MetricType.TIME, metric_nature=MetricNature.INSTANTANEOUS, unit=None
    )
    metric.value = "Off"
    entity = VRMMqttBinarySensor(device, metric, _device_info(), 123)
    entity.hass = hass
    _set_entity_id(entity, "binary_sensor")
    entity._on_update_task("Off")
    entity._on_update_task("On")
    assert entity.is_on


def test_button_press() -> None:
    """Verify button press updates underlying metric."""
    device = FakeDevice(unique_id="device", device_id="1", name="Device")
    metric = FakeWritableMetric(
        metric_kind=MetricKind.BUTTON,
        metric_type=MetricType.TIME,
        metric_nature=MetricNature.INSTANTANEOUS,
        unit_of_measurement=None,
        precision=None,
        short_id="button",
        unique_id="button_1",
        name="Button",
        value=None,
    )
    entity = VRMMqttButton(device, metric, _device_info(), 123)
    entity._on_update_task(None)
    entity.press()
    assert metric.value == "On"


def test_number_updates(hass: HomeAssistant) -> None:
    """Verify number update and set operations."""
    device = FakeDevice(unique_id="device", device_id="1", name="Device")
    metric = FakeWritableMetric(
        metric_kind=MetricKind.NUMBER,
        metric_type=MetricType.CURRENT,
        metric_nature=MetricNature.INSTANTANEOUS,
        unit_of_measurement="A",
        precision=1,
        short_id="number",
        unique_id="number_1",
        name="Number",
        value=1.0,
        min_value=0.0,
        max_value=10.0,
        step=0.5,
    )
    entity = VRMMqttNumber(device, metric, _device_info(), 123)
    entity.hass = hass
    _set_entity_id(entity, "number")
    entity._on_update_task(1.0)
    entity._on_update_task(2.0)
    entity.set_native_value(3.0)
    assert metric.value == 3.0


def test_sensor_updates(hass: HomeAssistant) -> None:
    """Verify sensor update handling."""
    device = FakeDevice(unique_id="device", device_id="1", name="Device")
    metric = _metric(
        metric_type=MetricType.VOLTAGE,
        metric_nature=MetricNature.INSTANTANEOUS,
        unit="V",
    )
    entity = VRMMqttSensor(device, metric, _device_info(), 123)
    entity.hass = hass
    _set_entity_id(entity, "sensor")
    entity._on_update_task(1)
    entity._on_update_task(2)
    assert entity.native_value == 2


def test_select_updates(hass: HomeAssistant) -> None:
    """Verify select update and option handling."""
    device = FakeDevice(unique_id="device", device_id="1", name="Device")
    metric = FakeWritableMetric(
        metric_kind=MetricKind.SELECT,
        metric_type=MetricType.TIME,
        metric_nature=MetricNature.INSTANTANEOUS,
        unit_of_measurement=None,
        precision=None,
        short_id="select",
        unique_id="select_1",
        name="Select",
        value="On",
        enum_values=["On", "Off"],
    )
    entity = VRMMqttSelect(device, metric, _device_info(), 123)
    entity.hass = hass
    _set_entity_id(entity, "select")
    entity._on_update_task("On")
    entity._on_update_task("Off")
    entity.select_option("Invalid")
    entity.select_option("On")
    assert metric.value == "On"


def test_switch_updates(hass: HomeAssistant) -> None:
    """Verify switch update and turn operations."""
    device = FakeDevice(unique_id="device", device_id="1", name="Device")
    metric = FakeWritableMetric(
        metric_kind=MetricKind.SWITCH,
        metric_type=MetricType.TIME,
        metric_nature=MetricNature.INSTANTANEOUS,
        unit_of_measurement=None,
        precision=None,
        short_id="switch",
        unique_id="switch_1",
        name="Switch",
        value="Off",
    )
    entity = VRMMqttSwitch(device, metric, _device_info(), 123)
    entity.hass = hass
    _set_entity_id(entity, "switch")
    entity._on_update_task("Off")
    entity._on_update_task("On")
    entity.turn_on()
    entity.turn_off()
    assert metric.value == "Off"


def test_time_updates(hass: HomeAssistant) -> None:
    """Verify time update and set operations."""
    assert VRMMqttTime._to_time(None) is None
    assert VRMMqttTime._to_minutes(dt_time(hour=1, minute=0)) == 60
    device = FakeDevice(unique_id="device", device_id="1", name="Device")
    metric = FakeWritableMetric(
        metric_kind=MetricKind.TIME,
        metric_type=MetricType.TIME,
        metric_nature=MetricNature.INSTANTANEOUS,
        unit_of_measurement="min",
        precision=None,
        short_id="time",
        unique_id="time_1",
        name="Time",
        value=60,
    )
    entity = VRMMqttTime(device, metric, _device_info(), 123)
    entity.hass = hass
    _set_entity_id(entity, "time")
    entity._on_update_task(60)
    entity._on_update_task(90)
    entity.set_value(dt_time(hour=2, minute=30))
    assert metric.value == 150
