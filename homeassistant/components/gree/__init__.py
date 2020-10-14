"""The Gree Climate integration."""
import logging

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .bridge import CannotConnect, DeviceHelper
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Gree Climate component."""
    hass.data[DOMAIN] = {}
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Gree Climate from a config entry."""
    devices = []

    # First we'll grab as many devices as we can find on the network
    # it's necessary to bind static devices anyway
    _LOGGER.debug("Scanning network for Gree devices")

    for device_info in await DeviceHelper.find_devices():
        try:
            device = await DeviceHelper.try_bind_device(device_info)
        except CannotConnect:
            _LOGGER.error("Unable to bind to gree device: %s", device_info)
            continue

        _LOGGER.debug(
            "Adding Gree device at %s:%i (%s)",
            device.device_info.ip,
            device.device_info.port,
            device.device_info.name,
        )
        devices.append(device)

    hass.data[DOMAIN]["devices"] = devices
    hass.data[DOMAIN]["pending"] = devices
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, CLIMATE_DOMAIN)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_forward_entry_unload(
        entry, CLIMATE_DOMAIN
    )

    if unload_ok:
        hass.data[DOMAIN].pop("devices", None)
        hass.data[DOMAIN].pop("pending", None)

    return unload_ok
