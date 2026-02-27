"""The EARN-E P1 Meter integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .coordinator import EarnEP1Coordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

type EarnEP1ConfigEntry = ConfigEntry[EarnEP1Coordinator]


async def async_setup_entry(hass: HomeAssistant, entry: EarnEP1ConfigEntry) -> bool:
    """Set up EARN-E P1 Meter from a config entry."""
    host = entry.data[CONF_HOST]
    serial = entry.data.get("serial")

    if serial is None:
        _LOGGER.warning(
            "No serial stored for EARN-E P1 entry %s; consider reconfiguring "
            "to pick up the device serial for stable unique IDs",
            entry.title,
        )

    coordinator = EarnEP1Coordinator(hass, host, serial=serial)

    try:
        await coordinator.async_start()
    except OSError as err:
        raise ConfigEntryNotReady(
            f"Cannot start UDP listener on port 16121: {err}"
        ) from err

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EarnEP1ConfigEntry) -> bool:
    """Unload a config entry."""
    await entry.runtime_data.async_stop()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
