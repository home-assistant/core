"""Utils for CO2 signal."""
from __future__ import annotations

from collections.abc import Mapping

from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE

from .const import CONF_COUNTRY_CODE


def get_extra_name(config: Mapping) -> str | None:
    """Return the extra name describing the location if not home."""
    if CONF_COUNTRY_CODE in config:
        return config[CONF_COUNTRY_CODE]

    if CONF_LATITUDE in config:
        return f"{round(config[CONF_LATITUDE], 2)}, {round(config[CONF_LONGITUDE], 2)}"

    return None
