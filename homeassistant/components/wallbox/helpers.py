"""Helpers for Wallbox integration."""

from datetime import datetime as datetime_sys

from dateutil import tz

import homeassistant.util.dt as dt_util


def map_schedule_item_to_ha(item: dict) -> dict:
    """Map local schedule item to be more usable with HA."""
    converted = {}
    converted["start"] = _convert_to_local_time(item["start"])
    converted["stop"] = _convert_to_local_time(item["stop"])
    converted["id"] = item["id"]
    converted["enable"] = item["enable"]
    converted["days"] = item["days"]
    if "max_current" in item:
        converted["max_current"] = item["max_current"]
    if "max_energy" in item:
        converted["max_energy"] = item["max_energy"]
    converted["created_at"] = item["created_at"]
    return converted


def map_ha_item_to_schedule(item: dict) -> dict:
    """Map HA schedule item for API."""
    converted = {}
    converted["start"] = _convert_to_utc_time_str(item["start"])
    converted["stop"] = _convert_to_utc_time_str(item["stop"])
    converted["id"] = item["id"]
    converted["enable"] = item["enable"]
    converted["days"] = item["days"]
    if "max_current" in item:
        converted["max_current"] = item["max_current"]
    if "max_energy" in item:
        converted["max_energy"] = item["max_energy"]
    return converted


def _convert_to_local_time(time: str) -> str:
    time_obj = datetime_sys.strptime(time, "%H%M").time()
    utc_time = dt_util.now().replace(
        hour=time_obj.hour,
        minute=time_obj.minute,
        second=0,
        microsecond=0,
        tzinfo=tz.UTC,
    )
    return dt_util.as_local(utc_time).time().strftime("%H:%M")


def _convert_to_utc_time_str(time: str) -> str:
    time_obj = datetime_sys.strptime(time, "%H:%M")
    local_time = dt_util.now().replace(
        hour=time_obj.hour, minute=time_obj.minute, second=0, microsecond=0
    )

    return dt_util.as_utc(local_time).strftime("%H%M")
