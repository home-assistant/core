"""Diagnostics for Besen chargers."""

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_ADDRESS, CONF_NAME, CONF_PIN
from homeassistant.core import HomeAssistant

from . import BesenConfigEntry

TO_REDACT = {
    CONF_ADDRESS,
    CONF_NAME,
    CONF_PIN,
    "advertised_name",
    "device_name",
    "serial",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: BesenConfigEntry
) -> dict[str, Any]:
    """Return a redacted snapshot without sending commands to the charger."""

    diagnostics: dict[str, Any] = {
        "entry_data": async_redact_data(entry.data, TO_REDACT),
    }
    if (coordinator := getattr(entry, "runtime_data", None)) is None:
        return diagnostics

    data = coordinator.data
    # Raw command replies and exception messages can contain credentials or names.
    diagnostics["data"] = async_redact_data(
        {
            "info": asdict(data.info),
            "config": asdict(data.config),
            "charge": asdict(data.charge),
            "available": data.available,
            "authenticated": data.authenticated,
            "auth_failed": data.auth_failed,
        },
        TO_REDACT,
    )
    return diagnostics
