"""Utility functions for the Reolink component."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .host import ReolinkHost


@dataclass
class ReolinkData:
    """Data for the Reolink integration."""

    host: ReolinkHost
    device_coordinator: DataUpdateCoordinator[None]
    firmware_coordinator: DataUpdateCoordinator[None]


def is_connected(hass: HomeAssistant, config_entry: config_entries.ConfigEntry) -> bool:
    """Check if an existing entry has a proper connection."""
    reolink_data: ReolinkData | None = hass.data.get(DOMAIN, {}).get(
        config_entry.entry_id
    )
    return (
        reolink_data is not None
        and config_entry.state == config_entries.ConfigEntryState.LOADED
        and reolink_data.device_coordinator.last_update_success
    )


def get_device_uid_and_ch(
    device: dr.DeviceEntry, host: ReolinkHost
) -> tuple[list[str], int | None, bool]:
    """Get the channel and the split device_uid from a reolink DeviceEntry."""
    device_uid = [
        dev_id[1].split("_") for dev_id in device.identifiers if dev_id[0] == DOMAIN
    ][0]

    is_chime = False
    if len(device_uid) < 2:
        # NVR itself
        ch = None
    elif device_uid[1].startswith("ch") and len(device_uid[1]) <= 5:
        ch = int(device_uid[1][2:])
    elif device_uid[1].startswith("chime"):
        ch = int(device_uid[1][5:])
        is_chime = True
    else:
        ch = host.api.channel_for_uid(device_uid[1])
    return (device_uid, ch, is_chime)
