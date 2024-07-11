"""The Dremel 3D Printer (3D20, 3D40, 3D45) integration."""

from __future__ import annotations

from dremel3dpy import Dremel3DPrinter
from requests.exceptions import ConnectTimeout, HTTPError

from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CAMERA_MODEL
from .coordinator import Dremel3DPrinterDataUpdateCoordinator, DremelConfigEntry

PLATFORMS = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.CAMERA, Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, config_entry: DremelConfigEntry
) -> bool:
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
    config_entry.runtime_data = coordinator
    platforms = list(PLATFORMS)
    if api.get_model() != CAMERA_MODEL:
        platforms.remove(Platform.CAMERA)
    await hass.config_entries.async_forward_entry_setups(config_entry, platforms)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: DremelConfigEntry) -> bool:
    """Unload Dremel config entry."""
    platforms = list(PLATFORMS)
    if entry.runtime_data.api.get_model() != CAMERA_MODEL:
        platforms.remove(Platform.CAMERA)
    return await hass.config_entries.async_unload_platforms(entry, platforms)
