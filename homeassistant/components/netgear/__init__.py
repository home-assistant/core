"""Support for Netgear routers."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.typing import HomeAssistantType

from .const import DOMAIN, PLATFORMS
from .errors import CannotLoginException
from .router import NetgearRouter

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Set up Netgear component."""
    router = NetgearRouter(hass, entry)
    try:
        await router.async_setup()
    except CannotLoginException as ex:
        raise ConfigEntryNotReady from ex

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.unique_id] = router

    entry.async_on_unload(entry.add_update_listener(update_listener))

    device_registry = await dr.async_get_registry(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.unique_id)},
        manufacturer="Netgear",
        name=router.device_name,
        model=router.model,
        sw_version=router.firmware_version,
    )

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    await _async_remove_untracked_registries(hass, entry)

    if unload_ok:
        await hass.data[DOMAIN][entry.unique_id].async_unload()
        hass.data[DOMAIN].pop(entry.unique_id)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)

    return unload_ok


async def _async_remove_untracked_registries(
    hass: HomeAssistantType, entry: ConfigEntry
):
    """Remove entities and devices that are no longer tracked from the registries."""
    # Remove devices that are no longer tracked
    device_registry = dr.async_get(hass)
    devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
    for device_entry in devices:
        device_mac = dict(device_entry.connections).get(dr.CONNECTION_NETWORK_MAC)
        if device_mac and device_mac not in tracked_list:
            device_registry.async_update_device(
                device_entry.id, remove_config_entry_id=entry.entry_id
            )


async def update_listener(hass: HomeAssistant, config_entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)
