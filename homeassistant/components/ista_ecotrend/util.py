"""Utility functions for Ista EcoTrend integration."""

from __future__ import annotations

import datetime
from typing import Any, Literal

from homeassistant.util import dt as dt_util


def get_consumptions(
    data: dict[str, Any], is_costs: bool = False
) -> list[dict[str, Any]]:
    """Get consumption readings and sort in ascending order by date."""
    result: list = []
    if consumptions := data.get("costs" if is_costs else "consumptions", []):
        result = [
            {
                "readings": readings["readings"],
                "date": last_day_of_month(**readings["date"]),
            }
            for readings in consumptions
        ]
        result.sort(key=lambda d: d["date"])
    return result


def get_values_by_type(
    consumptions: dict[str, Any], type: Literal["heating", "warmwater", "water"]
) -> dict[str, Any]:
    """Get the readings of a certain type."""

    readings: list = consumptions.get("readings", []) or consumptions.get(
        "costsByEnergyType", []
    )

    return next((values for values in readings if values.get("type") == type), {})


def as_number(value: str | None) -> float | int | None:
    """Convert readings to float or int.

    Readings in the json response are returned as strings,
    float values have comma as decimal separator
    """
    if value is None:
        return None
    return int(value) if value.isdigit() else float(value.replace(",", "."))


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
    consumption_type: Literal["heating", "warmwater", "water"],
    value_type: Literal["costs", "energy"] | None = None,
) -> int | float | None:
    """Determine the latest value for the sensor."""

    if last_value := get_statistics(data, consumption_type, value_type):
        return last_value[-1].get("value")
    return None


def get_statistics(
    data,
    consumption_type: Literal["heating", "warmwater", "water"],
    value_type: Literal["costs", "energy"] | None = None,
) -> list[dict[str, Any]] | None:
    """Determine the latest value for the sensor."""

    if monthly_consumptions := get_consumptions(data, bool(value_type == "costs")):
        return [
            {
                "value": as_number(
                    get_values_by_type(
                        consumptions=consumptions,
                        type=consumption_type,
                    ).get("additionalValue" if value_type == "energy" else "value")
                ),
                "date": consumptions["date"],
            }
            for consumptions in monthly_consumptions
            if get_values_by_type(
                consumptions=consumptions,
                type=consumption_type,
            ).get("additionalValue" if value_type == "energy" else "value")
        ]
    return None
