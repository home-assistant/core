"""Tests for Daikin sensors."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from homeassistant.components.daikin_onecta.const import (
    SENSOR_PERIOD_MONTHLY,
    SENSOR_PERIOD_WEEKLY,
)
from homeassistant.components.daikin_onecta.sensor import DaikinEnergySensor

EXPECTED_CURRENT_ROLLING_CONSUMPTION = 4
EXPECTED_MARCH_CONSUMPTION = 5


def _energy_sensor(
    period: str, day: list[int | None], week: list[int | None], month: list[int | None]
) -> DaikinEnergySensor:
    """Build an energy sensor with one electrical heating series."""
    series = SimpleNamespace(day=day, week=week, month=month)
    source = SimpleNamespace(heating=series)
    point = SimpleNamespace(
        consumption_data=SimpleNamespace(value=SimpleNamespace(electrical=source)),
        output_data=None,
    )
    device = MagicMock()
    device.management_point.return_value = point
    sensor = object.__new__(DaikinEnergySensor)
    attributes = {
        "_device": device,
        "_embedded_id": "point",
        "_datatype": "consumption",
        "_sensor_type": "electrical",
        "_operation_mode": "heating",
        "_period": period,
    }
    for attribute, value in attributes.items():
        setattr(sensor, attribute, value)
    return sensor


@pytest.mark.parametrize(
    ("period", "day", "week", "month"),
    [
        ("d", [1] * 12 + [1, None, 3] + [0] * 9, [0] * 14, [0] * 24),
        (SENSOR_PERIOD_WEEKLY, [0] * 24, [1] * 7 + [1, None, 3] + [0] * 4, [0] * 24),
        ("m", [0] * 24, [0] * 14, [1] * 12 + [1, None, 3] + [0] * 9),
    ],
)
def test_energy_sensor_uses_current_rolling_period(
    period: str,
    day: list[int | None],
    week: list[int | None],
    month: list[int | None],
) -> None:
    """Use only the current half of Daikin's rolling arrays and treat nulls as zero."""
    sensor = _energy_sensor(period, day, week, month)

    assert sensor.sensor_value() == EXPECTED_CURRENT_ROLLING_CONSUMPTION


@pytest.mark.freeze_time("2026-03-01 12:00:00+00:00")
def test_energy_sensor_uses_current_month_and_treats_null_as_zero() -> None:
    """Use March's current-year slot when calculating monthly consumption."""
    sensor = _energy_sensor(
        SENSOR_PERIOD_MONTHLY,
        [0] * 24,
        [0] * 14,
        [1] * 12 + [0, None, 5] + [0] * 9,
    )

    assert sensor.sensor_value() == EXPECTED_MARCH_CONSUMPTION
