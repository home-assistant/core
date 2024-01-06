"""The Dremel 3D Printer (3D20, 3D40, 3D45) integration."""
from __future__ import annotations

from dremel3dpy import Dremel3DPrinter
from requests.exceptions import ConnectTimeout, HTTPError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CAMERA_MODEL, DOMAIN
from .coordinator import Dremel3DPrinterDataUpdateCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.CAMERA, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up Dremel 3D Printer from a config entry."""
    try:
        api = await hass.async_add_executor_job(
            Dremel3DPrinter, config_entry.data[CONF_HOST]
        )

    except (ConnectTimeout, HTTPError) as ex:
        raise ConfigEntryNotReady(
            f"Unable to connect to Dremel 3D Printer: {ex}"
        ) from ex

    coordinator = Dremel3DPrinterDataUpdateCoordinator(hass, api)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = coordinator
    platforms = list(PLATFORMS)
    if api.get_model() != CAMERA_MODEL:
        platforms.remove(Platform.CAMERA)
    await hass.config_entries.async_forward_entry_setups(config_entry, platforms)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Dremel config entry."""
    platforms = list(PLATFORMS)
    api: Dremel3DPrinter = hass.data[DOMAIN][entry.entry_id].api
    if api.get_model() != CAMERA_MODEL:
        platforms.remove(Platform.CAMERA)
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, platforms):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
