"""Diagnostics support for UniFi Network."""

from typing import Any, cast

from uiprotect.test_util.anonymize import anonymize_data

from homeassistant.core import HomeAssistant

from .data import UFPConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: UFPConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    data = config_entry.runtime_data
    api = data.api
    bootstrap = cast(dict[str, Any], anonymize_data(api.bootstrap.unifi_dict()))
    diagnostics: dict[str, Any] = {
        "bootstrap": bootstrap,
        "options": dict(config_entry.options),
    }
    # Alarm hubs live in the public bootstrap (not the private one above) and
    # are absent on firmware/configs without the public Integration API.
    if api.has_public_bootstrap:
        diagnostics["alarm_hubs"] = [
            anonymize_data(hub.unifi_dict())
            for hub in api.public_bootstrap.alarm_hubs.values()
        ]
    return diagnostics
