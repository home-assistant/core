"""The EHEIM Digital integration."""

from __future__ import annotations

from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .coordinator import EheimDigitalUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.LIGHT]

type EheimDigitalConfigEntry = ConfigEntry[EheimDigitalUpdateCoordinator]


async def async_setup_entry(
    hass: HomeAssistant, entry: EheimDigitalConfigEntry
) -> bool:
    """Set up EHEIM Digital from a config entry."""

    if (
        serivce_info := await (
            await zeroconf.async_get_async_instance(hass)
        ).async_get_service_info("_http._tcp.local.", "eheimdigital._http._tcp.local.")
    ) is None or (zeroconf_info := zeroconf.info_from_service(serivce_info)) is None:
        raise ConfigEntryNotReady

    coordinator = EheimDigitalUpdateCoordinator(hass, entry, zeroconf_info)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: EheimDigitalConfigEntry
) -> bool:
    """Unload a config entry."""
    await entry.runtime_data.hub.close()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
