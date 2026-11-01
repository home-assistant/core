"""Diagnostics support for the Helty Flow Cloud integration."""

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .coordinator import HeltyCloudConfigEntry

TO_REDACT_ENTRY = {CONF_EMAIL, CONF_PASSWORD}
# The board serial is the MAC address of the panel.
TO_REDACT_DEVICE = {"serial_number", "board_serial"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: HeltyCloudConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return {
        "entry_data": async_redact_data(entry.data, TO_REDACT_ENTRY),
        "devices": [
            {
                # The raw installation record is left out: it is the
                # account's own record of the site and may hold personal
                # details beyond what support needs.
                "device": async_redact_data(
                    {
                        "serial_number": coordinator.device.serial_number,
                        "board_serial": coordinator.device.board_serial,
                        "name": coordinator.device.name,
                        "model": coordinator.device.model,
                        "firmware": coordinator.device.firmware,
                    },
                    TO_REDACT_DEVICE,
                ),
                "last_update_success": coordinator.last_update_success,
                "state": asdict(coordinator.data) if coordinator.data else None,
            }
            for coordinator in entry.runtime_data
        ],
    }
