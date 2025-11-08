"""Diagnostics support for Switcher."""

from __future__ import annotations

from dataclasses import asdict
import logging
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import SwitcherConfigEntry

TO_REDACT = {"device_id", "device_key", "ip_address", "mac_address"}

_LOGGER = logging.getLogger(__name__)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SwitcherConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinators = entry.runtime_data

    devices = []
    for device_id, coordinator in coordinators.items():
        if coordinator.data is not None:
            devices.append(asdict(coordinator.data))
        else:
            _LOGGER.debug(
                "Coordinator for device %s has no data yet (possibly still initializing)",
                device_id,
            )

    return async_redact_data(
        {
            "entry": entry.as_dict(),
            "devices": devices,
        },
        TO_REDACT,
    )
