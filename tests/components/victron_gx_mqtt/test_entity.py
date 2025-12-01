"""Unit tests for Victron GX MQTT entities."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from victron_mqtt import (
    Device as VictronVenusDevice,
    Metric as VictronVenusMetric,
    MetricNature,
    MetricType,
)

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.components.victron_gx_mqtt.binary_sensor import VictronBinarySensor
from homeassistant.components.victron_gx_mqtt.sensor import VictronSensor
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo


@pytest.fixture
def mock_device() -> VictronVenusDevice:
    """Return a mocked Victron device."""
    device = MagicMock(spec=VictronVenusDevice)
    device.name = "Test Device"
    return device


@pytest.fixture
def base_metric() -> VictronVenusMetric:
    """Return a mocked Victron metric with common defaults."""
    metric = MagicMock(spec=VictronVenusMetric)
    metric.unique_id = "metric_1"
    metric.short_id = "metric.short"
    metric.generic_short_id = "{phase}_voltage"
    metric.key_values = {"phase": "L1"}
    metric.precision = 2
    metric.unit_of_measurement = "V"
    metric.metric_type = MetricType.VOLTAGE
    metric.metric_nature = MetricNature.INSTANTANEOUS
    metric.value = 12.34
    return metric


async def test_sensor_repr_and_unique_id(
    hass: HomeAssistant, mock_device, base_metric
) -> None:
    """Test repr and unique_id formatting."""
    device_info: DeviceInfo = {"identifiers": {("victron_gx_mqtt", "dev_1")}}

    # simple_naming = False -> include installation_id
    sensor = VictronSensor(
        mock_device,
        base_metric,
        device_info,
        simple_naming=False,
        installation_id="inst",
    )

    assert sensor.unique_id == "sensor.victron_inst_metric_1"
    rep = repr(sensor)
    assert "VictronSensor(" in rep
    assert "metric.short" in rep

    # simple_naming = True -> omit installation_id
    sensor2 = VictronSensor(
        mock_device,
        base_metric,
        device_info,
        simple_naming=True,
        installation_id="inst",
    )
    assert sensor2.unique_id == "sensor.victron_metric_1"


async def test_sensor_update_task_triggers_state_update(
    hass: HomeAssistant, mock_device, base_metric
) -> None:
    """_on_update_task should schedule update on value change and not on same value."""
    device_info: DeviceInfo = {"identifiers": {("victron_gx_mqtt", "dev_1")}}
    sensor = VictronSensor(
        mock_device, base_metric, device_info, simple_naming=True, installation_id="x"
    )

    with patch.object(sensor, "schedule_update_ha_state") as mock_sched:
        # Change value
        sensor._on_update_task(56.78)
        assert sensor.native_value == 56.78
        mock_sched.assert_called_once()

    with patch.object(sensor, "schedule_update_ha_state") as mock_sched2:
        # Same value -> no schedule
        sensor._on_update_task(56.78)
        mock_sched2.assert_not_called()


async def test_binary_sensor_update_task_transitions(
    hass: HomeAssistant, mock_device, base_metric
) -> None:
    """Binary sensor should toggle based on On/Off strings and schedule when changed."""
    # Start with empty value to result in is_on False
    base_metric.value = ""
    device_info: DeviceInfo = {"identifiers": {("victron_gx_mqtt", "dev_1")}}
    bin_entity = VictronBinarySensor(
        mock_device, base_metric, device_info, simple_naming=True, installation_id="x"
    )

    assert bin_entity.is_on is False

    with patch.object(bin_entity, "schedule_update_ha_state") as mock_sched:
        bin_entity._on_update_task("On")
        assert bin_entity.is_on is True
        mock_sched.assert_called_once()

    with patch.object(bin_entity, "schedule_update_ha_state") as mock_sched2:
        bin_entity._on_update_task("On")
        mock_sched2.assert_not_called()


async def test_async_added_sets_update_callback(
    hass: HomeAssistant, mock_device, base_metric
) -> None:
    """Verify async_added_to_hass registers metric on_update and forwards updates when hass is set."""
    device_info: DeviceInfo = {"identifiers": {("victron_gx_mqtt", "dev_1")}}
    sensor = VictronSensor(
        mock_device, base_metric, device_info, simple_naming=True, installation_id="x"
    )

    # Entity not added yet -> _on_update should early return (hass is None)
    with patch.object(sensor, "_on_update_task") as mock_task:
        sensor._on_update(base_metric, 99)
        mock_task.assert_not_called()

    # Now add to hass and ensure updates propagate
    sensor.hass = hass
    await sensor.async_added_to_hass()

    with patch.object(sensor, "_on_update_task") as mock_task2:
        assert base_metric.on_update is not None
        # Simulate callback from metric
        base_metric.on_update(base_metric, 101)
        mock_task2.assert_called_once_with(101)


async def test_metric_mappings(hass: HomeAssistant, mock_device, base_metric) -> None:
    """Verify device_class, state_class, and unit mappings across all cases."""
    device_info: DeviceInfo = {"identifiers": {("victron_gx_mqtt", "dev_1")}}

    # Device class mapping for all MetricType values we support
    device_class_cases = [
        (MetricType.POWER, SensorDeviceClass.POWER),
        (MetricType.APPARENT_POWER, SensorDeviceClass.APPARENT_POWER),
        (MetricType.ENERGY, SensorDeviceClass.ENERGY),
        (MetricType.VOLTAGE, SensorDeviceClass.VOLTAGE),
        (MetricType.CURRENT, SensorDeviceClass.CURRENT),
        (MetricType.FREQUENCY, SensorDeviceClass.FREQUENCY),
        (MetricType.ELECTRIC_STORAGE_PERCENTAGE, SensorDeviceClass.BATTERY),
        (MetricType.TEMPERATURE, SensorDeviceClass.TEMPERATURE),
        (MetricType.SPEED, SensorDeviceClass.SPEED),
        (MetricType.LIQUID_VOLUME, SensorDeviceClass.VOLUME),
        (MetricType.TIME, SensorDeviceClass.DURATION),
    ]

    for metric_type, expected_device_class in device_class_cases:
        base_metric.metric_type = metric_type
        sensor = VictronSensor(
            mock_device,
            base_metric,
            device_info,
            simple_naming=True,
            installation_id="x",
        )
        assert sensor.device_class == expected_device_class

    # Unknown/unsupported device class should map to None
    base_metric.metric_type = MagicMock()
    sensor = VictronSensor(
        mock_device, base_metric, device_info, simple_naming=True, installation_id="x"
    )
    assert sensor.device_class is None

    # State class mapping
    base_metric.metric_nature = MetricNature.INSTANTANEOUS
    sensor = VictronSensor(
        mock_device, base_metric, device_info, simple_naming=True, installation_id="x"
    )
    assert sensor.state_class == SensorStateClass.MEASUREMENT

    base_metric.metric_nature = MetricNature.CUMULATIVE
    sensor = VictronSensor(
        mock_device, base_metric, device_info, simple_naming=True, installation_id="x"
    )
    assert sensor.state_class == SensorStateClass.TOTAL

    base_metric.metric_nature = MagicMock()
    sensor = VictronSensor(
        mock_device, base_metric, device_info, simple_naming=True, installation_id="x"
    )
    assert sensor.state_class is None

    # Unit of measurement mapping
    for unit, expected in (
        ("s", UnitOfTime.SECONDS),
        ("min", UnitOfTime.MINUTES),
        ("h", UnitOfTime.HOURS),
        ("V", "V"),  # passthrough
    ):
        base_metric.unit_of_measurement = unit
        sensor = VictronSensor(
            mock_device,
            base_metric,
            device_info,
            simple_naming=True,
            installation_id="x",
        )
        assert sensor.native_unit_of_measurement == expected


async def test_translation_fields(
    hass: HomeAssistant, mock_device, base_metric
) -> None:
    """Translation key is normalized and placeholders passed through."""
    device_info: DeviceInfo = {"identifiers": {("victron_gx_mqtt", "dev_1")}}
    sensor = VictronSensor(
        mock_device, base_metric, device_info, simple_naming=True, installation_id="x"
    )

    assert sensor.translation_key == "phase_voltage"
    assert sensor.translation_placeholders == {"phase": "L1"}
