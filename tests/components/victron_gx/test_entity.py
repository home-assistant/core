"""Unit tests for Victron GX MQTT entities."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from victron_mqtt import (
    Device as VictronVenusDevice,
    FormulaMetric as VictronFormulaMetric,
    Metric as VictronVenusMetric,
    MetricKind,
    MetricNature,
    MetricType,
)

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.components.victron_gx.sensor import VictronSensor
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
    metric.metric_kind = MetricKind.SENSOR
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


async def test_sensor_update_task_triggers_state_update(
    hass: HomeAssistant, mock_device, base_metric
) -> None:
    """_on_update_cb should schedule update on value change and not on same value."""
    device_info: DeviceInfo = {"identifiers": {("victron_gx", "dev_1")}}
    sensor = VictronSensor(mock_device, base_metric, device_info)

    with patch.object(sensor, "async_write_ha_state") as mock_sched:
        # Change value
        sensor._on_update_cb(56.78)
        assert sensor.native_value == 56.78
        mock_sched.assert_called_once()

    with patch.object(sensor, "async_write_ha_state") as mock_sched2:
        # Same value -> no schedule
        sensor._on_update_cb(56.78)
        mock_sched2.assert_not_called()


async def test_metric_mappings(hass: HomeAssistant, mock_device, base_metric) -> None:
    """Verify device_class, state_class, and unit mappings across all cases."""
    device_info: DeviceInfo = {"identifiers": {("victron_gx", "dev_1")}}

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
        (MetricType.LIQUID_VOLUME, SensorDeviceClass.VOLUME_STORAGE),
        (MetricType.DURATION, SensorDeviceClass.DURATION),
        (MetricType.TIME, None),
    ]

    for metric_type, expected_device_class in device_class_cases:
        base_metric.metric_type = metric_type
        sensor = VictronSensor(
            mock_device,
            base_metric,
            device_info,
        )
        assert sensor.device_class == expected_device_class

    # Unknown/unsupported device class should map to None
    base_metric.metric_type = MagicMock()
    sensor = VictronSensor(mock_device, base_metric, device_info)
    assert sensor.device_class is None

    # State class mapping
    base_metric.metric_nature = MetricNature.INSTANTANEOUS
    sensor = VictronSensor(mock_device, base_metric, device_info)
    assert sensor.state_class == SensorStateClass.MEASUREMENT

    base_metric.metric_nature = MetricNature.CUMULATIVE
    sensor = VictronSensor(mock_device, base_metric, device_info)
    assert sensor.state_class == SensorStateClass.TOTAL_INCREASING

    base_metric.metric_nature = MagicMock()
    sensor = VictronSensor(mock_device, base_metric, device_info)
    assert sensor.state_class is None

    # Unit of measurement mapping
    for unit, expected in (
        ("s", UnitOfTime.SECONDS),
        ("min", UnitOfTime.MINUTES),
        ("h", UnitOfTime.HOURS),
        ("V", "V"),  # passthrough
    ):
        base_metric.unit_of_measurement = unit
        sensor = VictronSensor(mock_device, base_metric, device_info)
        assert sensor.native_unit_of_measurement == expected


async def test_translation_fields(
    hass: HomeAssistant, mock_device, base_metric
) -> None:
    """Translation key is normalized and placeholders passed through."""
    device_info: DeviceInfo = {"identifiers": {("victron_gx", "dev_1")}}
    sensor = VictronSensor(mock_device, base_metric, device_info)

    assert sensor.translation_key == "phase_voltage"
    assert sensor.translation_placeholders == {"phase": "L1"}


async def test_sensor_update_task_uses_baseline(
    hass: HomeAssistant, mock_device, base_metric
) -> None:
    """_on_update_cb should add baseline before updating state."""
    device_info: DeviceInfo = {"identifiers": {("victron_gx", "dev_1")}}
    sensor = VictronSensor(mock_device, base_metric, device_info)
    sensor._baseline = 10.0

    with patch.object(sensor, "async_write_ha_state") as mock_sched:
        sensor._on_update_cb(2.5)
        assert sensor.native_value == 12.5
        mock_sched.assert_called_once()


async def test_sensor_async_added_restores_formula_metric_baseline(
    hass: HomeAssistant, mock_device
) -> None:
    """Restore baseline for cumulative formula metrics."""
    metric = MagicMock(spec=VictronFormulaMetric)
    metric.metric_kind = MetricKind.SENSOR
    metric.unique_id = "metric_restore"
    metric.short_id = "metric.restore"
    metric.generic_short_id = "energy"
    metric.key_values = {}
    metric.precision = 2
    metric.unit_of_measurement = "kWh"
    metric.metric_type = MetricType.ENERGY
    metric.metric_nature = MetricNature.CUMULATIVE
    metric.value = 1.5

    device_info: DeviceInfo = {"identifiers": {("victron_gx", "dev_1")}}
    sensor = VictronSensor(mock_device, metric, device_info)

    last_state = MagicMock()
    last_state.state = "2.0"

    with (
        patch(
            "homeassistant.components.victron_gx.sensor.VictronBaseEntity.async_added_to_hass",
            new=AsyncMock(),
        ) as mock_super_added,
        patch.object(
            sensor, "async_get_last_state", new=AsyncMock(return_value=last_state)
        ),
    ):
        await sensor.async_added_to_hass()

    assert sensor.native_value == 3.5
    assert sensor._baseline == 2.0
    mock_super_added.assert_awaited_once()


async def test_sensor_async_added_ignores_invalid_restored_value(
    hass: HomeAssistant, mock_device
) -> None:
    """Invalid stored state should not crash and should not set baseline."""
    metric = MagicMock(spec=VictronFormulaMetric)
    metric.metric_kind = MetricKind.SENSOR
    metric.unique_id = "metric_invalid_restore"
    metric.short_id = "metric.restore"
    metric.generic_short_id = "energy"
    metric.key_values = {}
    metric.precision = 2
    metric.unit_of_measurement = "kWh"
    metric.metric_type = MetricType.ENERGY
    metric.metric_nature = MetricNature.CUMULATIVE
    metric.value = 4.0

    device_info: DeviceInfo = {"identifiers": {("victron_gx", "dev_1")}}
    sensor = VictronSensor(mock_device, metric, device_info)

    last_state = MagicMock()
    last_state.state = "not-a-number"

    with (
        patch(
            "homeassistant.components.victron_gx.sensor.VictronBaseEntity.async_added_to_hass",
            new=AsyncMock(),
        ) as mock_super_added,
        patch.object(
            sensor, "async_get_last_state", new=AsyncMock(return_value=last_state)
        ),
    ):
        await sensor.async_added_to_hass()

    assert sensor.native_value == 4.0
    assert sensor._baseline is None
    mock_super_added.assert_awaited_once()


async def test_sensor_async_added_skips_baseline_for_non_numeric_value(
    hass: HomeAssistant, mock_device
) -> None:
    """Non-numeric current value should skip baseline restoration."""
    metric = MagicMock(spec=VictronFormulaMetric)
    metric.metric_kind = MetricKind.SENSOR
    metric.unique_id = "metric_non_numeric"
    metric.short_id = "metric.restore"
    metric.generic_short_id = "energy"
    metric.key_values = {}
    metric.precision = 2
    metric.unit_of_measurement = "kWh"
    metric.metric_type = MetricType.ENERGY
    metric.metric_nature = MetricNature.CUMULATIVE
    metric.value = "not-a-number"

    device_info: DeviceInfo = {"identifiers": {("victron_gx", "dev_1")}}
    sensor = VictronSensor(mock_device, metric, device_info)

    last_state = MagicMock()
    last_state.state = "2.0"

    with (
        patch(
            "homeassistant.components.victron_gx.sensor.VictronBaseEntity.async_added_to_hass",
            new=AsyncMock(),
        ) as mock_super_added,
        patch.object(
            sensor, "async_get_last_state", new=AsyncMock(return_value=last_state)
        ),
    ):
        await sensor.async_added_to_hass()

    assert sensor.native_value == "not-a-number"
    assert sensor._baseline is None
    mock_super_added.assert_awaited_once()
