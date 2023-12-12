"""Helper functions for swiss_public_transport."""
from typing import Any

import homeassistant.util.dt as dt_util

from .const import (
    CONF_ACCESSIBILITY,
    CONF_BIKE,
    CONF_COUCHETTE,
    CONF_DATE,
    CONF_DESTINATION,
    CONF_DIRECT,
    CONF_IS_ARRIVAL,
    CONF_LIMIT,
    CONF_OFFSET,
    CONF_PAGE,
    CONF_SLEEPER,
    CONF_START,
    CONF_TIME,
    CONF_TRANSPORTATIONS,
    CONF_VIA,
    DEFAULT_LIMIT,
    DEFAULT_PAGE,
    SELECTOR_TRANSPORTATION_TYPES,
)


def offset_opendata(opendata, offset: str) -> None:
    """In place offset the opendata connector."""

    duration = dt_util.parse_duration(offset)
    if duration:
        now_offset = dt_util.as_local(dt_util.now() + duration)
        opendata.date = now_offset.date()
        opendata.time = now_offset.time()


def dict_duration_to_str_duration(
    d: dict[str, int],
) -> str:
    """Build a string from a dict duration."""
    return f"{d['hours']:02d}:{d['minutes']:02d}:{d['seconds']:02d}"


def entry_title_from_config(config: dict[str, Any]) -> str:
    """Build a identifiable entry name from a config entry."""
    return (
        (
            f"{config[CONF_START]} {config[CONF_DESTINATION]}"
            + (" direct" if CONF_DIRECT in config and config[CONF_DIRECT] else "")
            + (
                " via " + ", ".join(config[CONF_VIA])
                if CONF_VIA in config and len(config[CONF_VIA]) > 0
                else ""
            )
        )
        + (" arrival" if CONF_IS_ARRIVAL in config and config[CONF_IS_ARRIVAL] else "")
        + (
            " on " + config[CONF_DATE]
            if CONF_DATE in config and config[CONF_DATE]
            else ""
        )
        + (
            " at " + config[CONF_TIME]
            if CONF_TIME in config and config[CONF_TIME]
            else ""
        )
        + (
            " in " + dict_duration_to_str_duration(config[CONF_OFFSET])
            if CONF_OFFSET in config and config[CONF_OFFSET]
            else ""
        )
        + (
            " limited to " + str(int(config[CONF_LIMIT]))
            if CONF_LIMIT in config and config[CONF_LIMIT] != DEFAULT_LIMIT
            else ""
        )
        + (
            " on page " + str(int(config[CONF_PAGE]))
            if CONF_PAGE in config and config[CONF_PAGE] != DEFAULT_PAGE
            else ""
        )
        + (
            " using " + ", ".join(config[CONF_TRANSPORTATIONS])
            if CONF_TRANSPORTATIONS in config
            and len(config[CONF_TRANSPORTATIONS]) < len(SELECTOR_TRANSPORTATION_TYPES)
            else ""
        )
        + (
            " providing " + ", ".join(config[CONF_ACCESSIBILITY])
            if CONF_ACCESSIBILITY in config and len(config[CONF_ACCESSIBILITY]) > 0
            else ""
        )
        + (" with bike" if CONF_BIKE in config and config[CONF_BIKE] else "")
        + (
            " with couchette"
            if CONF_COUCHETTE in config and config[CONF_COUCHETTE]
            else ""
        )
        + (" with sleeper" if CONF_SLEEPER in config and config[CONF_SLEEPER] else "")
    )
