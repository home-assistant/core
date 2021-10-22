"""Support for Netgear routers."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
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


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.unique_id)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)

    return unload_ok


async def update_listener(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)
