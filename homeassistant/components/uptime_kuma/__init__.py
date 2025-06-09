"""The Uptime Kuma integration."""

from __future__ import annotations

from pyuptimekuma import UptimeKuma
from yarl import URL

from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntry

from .coordinator import UptimeKumaConfigEntry, UptimeKumaDataUpdateCoordinator

_PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: UptimeKumaConfigEntry) -> bool:
    """Set up Uptime Kuma from a config entry."""
    url = URL(entry.data[CONF_URL])
    if url.path.endswith("/"):
        url = url.with_path(url.path[:-1])
    session = async_get_clientsession(hass)
    uptime_kuma = UptimeKuma(
        session,
        str(url),
        "",
        entry.data[CONF_API_KEY],
        entry.data[CONF_VERIFY_SSL],
    )
    coordinator = UptimeKumaDataUpdateCoordinator(hass, entry, uptime_kuma)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: UptimeKumaConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: UptimeKumaConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Remove a config entry from a device.

    If a monitor is not returned by the API it might be that it is
    just paused, therefore we can't delete stale devices automatically.
    Renaming a monitor also leads to a stale device entry as the API endpoint does
    not expose unique identifiers.
    """

    return device_entry.name not in config_entry.runtime_data.data
