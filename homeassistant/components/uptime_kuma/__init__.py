"""The Uptime Kuma integration."""

from __future__ import annotations

from pythonkuma.update import UpdateChecker

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN
from .coordinator import (
    UptimeKumaConfigEntry,
    UptimeKumaDataUpdateCoordinator,
    UptimeKumaSoftwareUpdateCoordinator,
)

_PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.UPDATE]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
UPTIME_KUMA_KEY: HassKey[UptimeKumaSoftwareUpdateCoordinator] = HassKey(DOMAIN)


async def async_setup_entry(hass: HomeAssistant, entry: UptimeKumaConfigEntry) -> bool:
    """Set up Uptime Kuma from a config entry."""
    if UPTIME_KUMA_KEY not in hass.data:
        session = async_get_clientsession(hass)
        update_checker = UpdateChecker(session)

        update_coordinator = UptimeKumaSoftwareUpdateCoordinator(hass, update_checker)
        await update_coordinator.async_request_refresh()

        hass.data[UPTIME_KUMA_KEY] = update_coordinator

    coordinator = UptimeKumaDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: UptimeKumaConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)

    if not hass.config_entries.async_loaded_entries(DOMAIN):
        await hass.data[UPTIME_KUMA_KEY].async_shutdown()
        hass.data.pop(UPTIME_KUMA_KEY)
    return unload_ok
