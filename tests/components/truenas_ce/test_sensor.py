"""Unit tests for sensor.py."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.truenas_ce.const import CONF_DATA_UNIT
from homeassistant.components.truenas_ce.sensor import (
    TrueNASSensor,
    TrueNASUptimeSensor,
)
from homeassistant.components.truenas_ce.sensor_types import (
    TrueNASSensorEntityDescription,
)
from homeassistant.const import UnitOfInformation

from ._fakes import make_config_entry, make_coordinator


def _make_sensor(
    cls,
    data: dict,
    path: str = "disk",
    desc: TrueNASSensorEntityDescription | None = None,
):
    description = desc or TrueNASSensorEntityDescription(
        key="k", name="N", data_path=path, data_attribute="value"
    )
    coordinator = make_coordinator(data={path: {"o1": data}})
    return cls(coordinator, description, "o1")


# ---------------------------
#   TrueNASSensor
# ---------------------------
def test_native_value_returns_data_attribute() -> None:
    """native_value returns the raw value of the configured data attribute."""
    sensor = _make_sensor(TrueNASSensor, {"value": 42})
    assert sensor.native_value == 42


def test_native_unit_of_measurement_plain() -> None:
    """A plain, non-`data_`-prefixed unit is returned unchanged."""
    desc = TrueNASSensorEntityDescription(
        key="k",
        name="N",
        data_path="disk",
        data_attribute="value",
        native_unit_of_measurement="MB",
    )
    sensor = _make_sensor(TrueNASSensor, {"value": 1}, desc=desc)
    assert sensor.native_unit_of_measurement == "MB"


def test_native_unit_of_measurement_none_when_not_configured() -> None:
    """No configured unit yields native_unit_of_measurement of None."""
    sensor = _make_sensor(TrueNASSensor, {"value": 1})
    assert sensor.native_unit_of_measurement is None


def test_native_unit_of_measurement_data_prefixed_present() -> None:
    """A `data__field` unit resolves to that field's value when present."""
    desc = TrueNASSensorEntityDescription(
        key="k",
        name="N",
        data_path="disk",
        data_attribute="value",
        native_unit_of_measurement="data__uom",
    )
    sensor = _make_sensor(TrueNASSensor, {"value": 1, "uom": "GB"}, desc=desc)
    assert sensor.native_unit_of_measurement == "GB"


def test_native_unit_of_measurement_data_prefixed_missing_falls_back() -> None:
    """A `data__field` unit falls back to the raw spec string when field is absent."""
    desc = TrueNASSensorEntityDescription(
        key="k",
        name="N",
        data_path="disk",
        data_attribute="value",
        native_unit_of_measurement="data__uom",
    )
    sensor = _make_sensor(TrueNASSensor, {"value": 1}, desc=desc)
    assert sensor.native_unit_of_measurement == "data__uom"


def test_init_scales_gib_suggested_unit_from_options() -> None:
    """A GiB data-unit option keeps the suggested unit at GIBIBYTES."""
    desc = TrueNASSensorEntityDescription(
        key="k",
        name="N",
        data_path="disk",
        data_attribute="value",
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
    )
    entry = make_config_entry(options={CONF_DATA_UNIT: "GiB"})
    coordinator = make_coordinator(
        data={"disk": {"o1": {"value": 5 * 1024**3}}}, config_entry=entry
    )
    sensor = TrueNASSensor(coordinator, desc, "o1")
    assert sensor._attr_suggested_unit_of_measurement == UnitOfInformation.GIBIBYTES


def test_init_scales_gb_suggested_unit_from_entry_data_fallback() -> None:
    """A GB data-unit entry falls back from entry.data, scaling the suggested unit."""
    desc = TrueNASSensorEntityDescription(
        key="k",
        name="N",
        data_path="disk",
        data_attribute="value",
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
    )
    entry = make_config_entry(data={CONF_DATA_UNIT: "GB"})
    coordinator = make_coordinator(
        data={"disk": {"o1": {"value": 5 * 1000**3}}}, config_entry=entry
    )
    sensor = TrueNASSensor(coordinator, desc, "o1")
    assert sensor._attr_suggested_unit_of_measurement == UnitOfInformation.GIGABYTES


def test_init_does_not_scale_non_gb_suggested_unit() -> None:
    """A non-data-size suggested unit (e.g. MB/s) is left untouched."""
    desc = TrueNASSensorEntityDescription(
        key="k",
        name="N",
        data_path="disk",
        data_attribute="value",
        suggested_unit_of_measurement="MB/s",
    )
    sensor = _make_sensor(TrueNASSensor, {"value": 1}, desc=desc)
    assert sensor._attr_suggested_unit_of_measurement == "MB/s"


# ---------------------------
#   TrueNASUptimeSensor
# ---------------------------
def test_uptime_native_value_positive() -> None:
    """A positive uptime timestamp is returned as a datetime."""
    sensor = _make_sensor(TrueNASUptimeSensor, {"value": 1735689600})
    assert isinstance(sensor.native_value, datetime)


def test_uptime_native_value_zero_is_none() -> None:
    """An uptime value of zero yields native_value of None."""
    sensor = _make_sensor(TrueNASUptimeSensor, {"value": 0})
    assert sensor.native_value is None
