"""The Z-Wave-Me WS integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import PLATFORMS
from .controller import ZWaveMeConfigEntry, ZWaveMeController


async def async_setup_entry(hass: HomeAssistant, entry: ZWaveMeConfigEntry) -> bool:
    """Set up Z-Wave-Me from a config entry."""
    controller = ZWaveMeController(hass, entry)

    if not await controller.async_establish_connection():
        raise ConfigEntryNotReady

    entry.runtime_data = controller
    await async_setup_platforms(hass, entry, controller)
    registry = dr.async_get(hass)
    controller.remove_stale_devices(registry)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ZWaveMeConfigEntry) -> bool:
    """Unload a config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.zwave_api.close_ws()
    return unload_ok


async def async_setup_platforms(
    hass: HomeAssistant, entry: ConfigEntry, controller: ZWaveMeController
) -> None:
    """Set up platforms."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    controller.platforms_inited = True

    await hass.async_add_executor_job(controller.zwave_api.get_devices)
