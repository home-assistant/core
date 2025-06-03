"""The Seko Pooldose integration."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DEFAULT_SCAN_INTERVAL, DEFAULT_TIMEOUT
from .coordinator import PooldoseCoordinator
from .pooldose_api import PooldoseAPIClient

_PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
]

"""Configure the Seko Pooldose entry."""


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Seko Pooldose from a config entry."""
    config = entry.data
    host = config["host"]
    serial = config["serialnumber"]
    scan_interval = config.get("scan_interval", DEFAULT_SCAN_INTERVAL)
    timeout = config.get("timeout", DEFAULT_TIMEOUT)

    api = PooldoseAPIClient(
        host=host,
        serial_number=serial,
        timeout=timeout,
        scan_interval=scan_interval,
    )

    coordinator = PooldoseCoordinator(hass, api, timedelta(seconds=scan_interval))
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault("pooldose", {})[entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the Seko Pooldose entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
