"""Helper functions for swiss_public_transport."""

from collections.abc import Mapping
from datetime import timedelta
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
)


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


def unique_id_from_config(config: Mapping[str, Any]) -> str:
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
