"""Utils for CO2 signal."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.const import CONF_COUNTRY_CODE, CONF_LATITUDE, CONF_LONGITUDE

if TYPE_CHECKING:
    from collections.abc import Mapping


def get_extra_name(config: Mapping[str, Any]) -> str | None:
    """Return the extra name describing the location if not home."""
    if CONF_COUNTRY_CODE in config:
        return config[CONF_COUNTRY_CODE]  # type: ignore[no-any-return]

    if CONF_LATITUDE in config:
        return f"{round(config[CONF_LATITUDE], 2)}, {round(config[CONF_LONGITUDE], 2)}"

    return None
