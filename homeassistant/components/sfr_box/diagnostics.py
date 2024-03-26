"""SFR Box diagnostics platform."""

from __future__ import annotations

import dataclasses
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .models import DomainData

TO_REDACT = {"mac_addr", "serial_number", "ip_addr", "ipv6_addr"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data: DomainData = hass.data[DOMAIN][entry.entry_id]

    return {
        "entry": {
            "title": entry.title,
            "data": dict(entry.data),
        },
        "data": {
            "dsl": async_redact_data(
                dataclasses.asdict(
                    await data.system.box.dsl_get_info()  # type:ignore [call-overload]
                ),
                TO_REDACT,
            ),
            "ftth": async_redact_data(
                dataclasses.asdict(
                    await data.system.box.ftth_get_info()  # type:ignore [call-overload]
                ),
                TO_REDACT,
            ),
            "system": async_redact_data(
                dataclasses.asdict(
                    await data.system.box.system_get_info()  # type:ignore [call-overload]
                ),
                TO_REDACT,
            ),
            "wan": async_redact_data(
                dataclasses.asdict(
                    await data.system.box.wan_get_info()  # type:ignore [call-overload]
                ),
                TO_REDACT,
            ),
        },
    }
