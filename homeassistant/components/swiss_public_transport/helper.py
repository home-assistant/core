"""Helper functions for swiss_public_transport."""

from dataclasses import dataclass, field
from datetime import timedelta
from types import MappingProxyType
from typing import Any

from opendata_transport import OpendataTransport

from homeassistant.util import dt as dt_util

from .const import (
    CONF_DESTINATION,
    CONF_START,
    CONF_TIME_FIXED,
    CONF_TIME_OFFSET,
    CONF_TIME_STATION,
    CONF_VIA,
    DEFAULT_TIME_STATION,
    DIAGNOSE_STATS_MAX_AGE,
)


@dataclass
class Stats:
    """A stats data class."""

    count: int = 0
    errors: int = 0
    timestamps_success: list[str] = field(default_factory=list)
    timestamps_error: list[str] = field(default_factory=list)


def offset_opendata(opendata: OpendataTransport, offset: dict[str, int]) -> None:
    """In place offset the opendata connector."""

    duration = timedelta(**offset)
    if duration:
        now_offset = dt_util.as_local(dt_util.now() + duration)
        opendata.date = now_offset.date()
        opendata.time = now_offset.time()


def dict_duration_to_str_duration(
    d: dict[str, int],
) -> str:
    """Build a string from a dict duration."""
    return f"{d['hours']:02d}:{d['minutes']:02d}:{d['seconds']:02d}"


def unique_id_from_config(config: MappingProxyType[str, Any] | dict[str, Any]) -> str:
    """Build a unique id from a config entry."""
    return (
        f"{config[CONF_START]} {config[CONF_DESTINATION]}"
        + (
            " via " + ", ".join(config[CONF_VIA])
            if CONF_VIA in config and len(config[CONF_VIA]) > 0
            else ""
        )
        + (
            " arrival"
            if config.get(CONF_TIME_STATION, DEFAULT_TIME_STATION) == "arrival"
            else ""
        )
        + (" at " + config[CONF_TIME_FIXED] if CONF_TIME_FIXED in config else "")
        + (
            " in " + dict_duration_to_str_duration(config[CONF_TIME_OFFSET])
            if CONF_TIME_OFFSET in config
            else ""
        )
    )


def update_stats(stats: dict[str, Stats], success: bool = True) -> None:
    """Update the stats and record every call for the last couple of days."""
    today = dt_util.now().date()
    today_key = today.isoformat()
    keep_dates = [
        (today - timedelta(days=i)).isoformat() for i in range(DIAGNOSE_STATS_MAX_AGE)
    ]
    if today_key not in stats:
        stats[today_key] = Stats()
    for key in [key for key in stats if key not in keep_dates]:
        del stats[key]

    time_value = dt_util.now().time().isoformat()
    stats[today_key].count += 1
    if success:
        stats[today_key].timestamps_success.append(time_value)
    else:
        stats[today_key].errors += 1
        stats[today_key].timestamps_error.append(time_value)
