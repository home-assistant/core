"""The 1-Wire component."""
import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.typing import HomeAssistantType

from .const import DOMAIN, PLATFORMS
from .onewirehub import CannotConnect, OneWireHub

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Set up 1-Wire integrations."""
    return True


async def async_setup_entry(hass: HomeAssistantType, config_entry: ConfigEntry):
    """Set up a 1-Wire proxy for a config entry."""
    hass.data.setdefault(DOMAIN, {})

    onewirehub = OneWireHub(hass)
    try:
        await onewirehub.initialize(config_entry)
    except CannotConnect as exc:
        raise ConfigEntryNotReady() from exc

    hass.data[DOMAIN][config_entry.unique_id] = onewirehub

    async def cleanup_registry() -> None:
        # Get registries
        device_registry, entity_registry = await asyncio.gather(
            hass.helpers.device_registry.async_get_registry(),
            hass.helpers.entity_registry.async_get_registry(),
        )
        # Generate list of all device entries
        registry_devices = [
            entry.id
            for entry in dr.async_entries_for_config_entry(
                device_registry, config_entry.entry_id
            )
        ]
        # Remove devices that don't belong to any entity
        for device_id in registry_devices:
            if not er.async_entries_for_device(
                entity_registry, device_id, include_disabled_entities=True
            ):
                _LOGGER.debug(
                    "Removing device `%s` because it does not have any entities",
                    device_id,
                )
                device_registry.async_remove_device(device_id)

    async def start_platforms() -> None:
        """Start platforms and cleanup devices."""
        # wait until all required platforms are ready
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_setup(config_entry, platform)
                for platform in PLATFORMS
            ]
        )
        await cleanup_registry()

    hass.async_create_task(start_platforms())

    return True


async def async_unload_entry(hass: HomeAssistantType, config_entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(config_entry, platform)
                for platform in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.unique_id)
    return unload_ok
