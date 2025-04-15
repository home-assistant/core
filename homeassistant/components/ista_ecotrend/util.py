"""Utility functions for Ista EcoTrend integration."""

from __future__ import annotations

import datetime
from enum import StrEnum
from typing import Any

from homeassistant.util import dt as dt_util


class IstaConsumptionType(StrEnum):
    """Types of consumptions from ista."""

    HEATING = "heating"
    HOT_WATER = "warmwater"
    WATER = "water"


class IstaValueType(StrEnum):
    """Values type Costs or energy."""

    COSTS = "costs"
    ENERGY = "energy"


def get_consumptions(
    data: dict[str, Any], value_type: IstaValueType | None = None
) -> list[dict[str, Any]]:
    """Get consumption readings and sort in ascending order by date."""
    result: list = []
    if consumptions := data.get(
        "costs" if value_type == IstaValueType.COSTS else "consumptions", []
    ):
        result = [
            {
                "readings": readings.get("costsByEnergyType")
                if value_type == IstaValueType.COSTS
                else readings.get("readings"),
                "date": last_day_of_month(**readings["date"]),
            }
            for readings in consumptions
        ]
        result.sort(key=lambda d: d["date"])
    return result


def get_values_by_type(
    consumptions: dict[str, Any], consumption_type: IstaConsumptionType
) -> dict[str, Any]:
    """Get the readings of a certain type."""

    readings: list = consumptions.get("readings", []) or consumptions.get(
        "costsByEnergyType", []
    )

    return next(
        (values for values in readings if values.get("type") == consumption_type.value),
        {},
    )


def as_number(value: str | float | None) -> float | int | None:
    """Convert readings to float or int.

    Readings in the json response are returned as strings,
    float values have comma as decimal separator
    """
    if isinstance(value, str):
        return int(value) if value.isdigit() else float(value.replace(",", "."))

    return value


def last_day_of_month(month: int, year: int) -> datetime.datetime:
    """Get the last day of the month."""

    return dt_util.as_local(
        datetime.datetime(
            month=month + 1 if month < 12 else 1,
            year=year if month < 12 else year + 1,
            day=1,
            tzinfo=datetime.UTC,
        )
        + datetime.timedelta(days=-1)
    )


def get_native_value(
    data,
    consumption_type: IstaConsumptionType,
    value_type: IstaValueType | None = None,
) -> int | float | None:
    """Determine the latest value for the sensor."""

    if last_value := get_statistics(data, consumption_type, value_type):
        return last_value[-1].get("value")
    return None


def get_statistics(
    data,
    consumption_type: IstaConsumptionType,
    value_type: IstaValueType | None = None,
) -> list[dict[str, Any]] | None:
    """Determine the latest value for the sensor."""

    if monthly_consumptions := get_consumptions(data, value_type):
        return [
            {
                "value": as_number(
                    get_values_by_type(
                        consumptions=consumptions,
                        consumption_type=consumption_type,
                    ).get(
                        "additionalValue"
                        if value_type == IstaValueType.ENERGY
                        else "value"
                    )
                ),
                "date": consumptions["date"],
            }
            for consumptions in monthly_consumptions
            if get_values_by_type(
                consumptions=consumptions,
                consumption_type=consumption_type,
            ).get("additionalValue" if value_type == IstaValueType.ENERGY else "value")
        ]
    return None
