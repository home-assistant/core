"""Diagnostics support for Husqvarna Automower."""

import logging
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from . import AutomowerConfigEntry
from .const import DOMAIN

CONF_REFRESH_TOKEN = "refresh_token"
POSITIONS = "positions"

TO_REDACT = {
    CONF_ACCESS_TOKEN,
    CONF_REFRESH_TOKEN,
    POSITIONS,
}
_LOGGER = logging.getLogger(__name__)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: AutomowerConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return async_redact_data(entry.as_dict(), TO_REDACT)


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: AutomowerConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device entry."""
    coordinator = entry.runtime_data
    mower_id: str | None = None
    for identifier in device.identifiers:
        if identifier[0] != DOMAIN:
            continue

        device_id = identifier[1]

        # Parent device: identifier is the mower ID.
        if device_id in coordinator.data:
            mower_id = device_id
            break

        # Work-area child device: identifier is <mower_id>_<area_id>.
        for candidate_mower_id in coordinator.data:
            if device_id.startswith(f"{candidate_mower_id}_"):
                mower_id = candidate_mower_id
                break

        if mower_id is not None:
            break

    if mower_id is None:
        return {}

    return async_redact_data(
        coordinator.data[mower_id].to_dict(),
        TO_REDACT,
    )
