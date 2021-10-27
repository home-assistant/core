"""The 1-Wire component."""
import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, PLATFORMS
from .onewirehub import CannotConnect, OneWireHub

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a 1-Wire proxy for a config entry."""
    hass.data.setdefault(DOMAIN, {})

    onewirehub = OneWireHub(hass)
    try:
        await onewirehub.initialize(entry)
    except CannotConnect as exc:
        raise ConfigEntryNotReady() from exc

    hass.data[DOMAIN][entry.entry_id] = onewirehub

    async def cleanup_registry(onewirehub: OneWireHub) -> None:
        # Get registries
        device_registry = dr.async_get(hass)
        # Generate list of all device entries
        registry_devices = list(
            dr.async_entries_for_config_entry(device_registry, entry.entry_id)
        )
        # Remove devices that don't belong to any entity
        for device in registry_devices:
            if not onewirehub.has_device_in_cache(device):
                _LOGGER.debug(
                    "Removing device `%s` because it is no longer available",
                    device.id,
                )
                device_registry.async_remove_device(device.id)

    async def start_platforms(onewirehub: OneWireHub) -> None:
        """Start platforms and cleanup devices."""
        # wait until all required platforms are ready
        await asyncio.gather(
            *(
                hass.config_entries.async_forward_entry_setup(entry, platform)
                for platform in PLATFORMS
            )
        )
        await cleanup_registry(onewirehub)

    hass.async_create_task(start_platforms(onewirehub))

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )
    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)
    return unload_ok
