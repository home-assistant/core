"""Diagnostics support for GKP."""

import dataclasses
import time
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import GkpConfigEntry

TO_REDACT = ("refresh_token", "id_token", "profile_info", "unique_id")


def _isoformat(timestamp: float | None) -> str | None:
    """Return a timestamp as ISO string."""
    if timestamp is None:
        return None
    return dt_util.utc_from_timestamp(timestamp).isoformat()


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: GkpConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    runtime_data = entry.runtime_data
    hub_coordinator = runtime_data.hub_coordinator
    device_coordinators = runtime_data.device_coordinators
    now = time.time()

    return async_redact_data(
        {
            "entry": entry.as_dict(),
            "hub_coordinator": {
                "last_update_success": hub_coordinator.last_update_success,
                "last_exception": (
                    str(hub_coordinator.last_exception)
                    if hub_coordinator.last_exception
                    else None
                ),
                "last_discovery": _isoformat(hub_coordinator.last_discovery),
                "last_user_connected": _isoformat(hub_coordinator.last_user_connected),
                "total_devices": len(hub_coordinator.data),
            },
            "installations": {
                installation_id: dataclasses.asdict(installation)
                for installation_id, installation in hub_coordinator.installations.items()
            },
            "devices": {
                device_id: {
                    "thermostat": dataclasses.asdict(coordinator.data.thermostat),
                    "last_update_success": coordinator.last_update_success,
                    "fast_polling_until": _isoformat(
                        coordinator.fast_polling_until
                        if coordinator.fast_polling_until is not None
                        and coordinator.fast_polling_until > now
                        else None
                    ),
                }
                for device_id, coordinator in device_coordinators.items()
            },
        },
        {CONF_ACCESS_TOKEN, *TO_REDACT},
    )
