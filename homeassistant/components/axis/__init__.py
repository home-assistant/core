"""Support for Axis devices."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import DOMAIN as AXIS_DOMAIN, PLATFORMS
from .device import AxisNetworkDevice, get_axis_device
from .errors import AuthenticationRequired, CannotConnect

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the Axis integration."""
    hass.data.setdefault(AXIS_DOMAIN, {})

    try:
        api = await get_axis_device(hass, entry.data)
    except CannotConnect as err:
        raise ConfigEntryNotReady from err
    except AuthenticationRequired as err:
        raise ConfigEntryAuthFailed from err

    device = AxisNetworkDevice(hass, entry, api)
    hass.data[AXIS_DOMAIN][entry.entry_id] = device
    await device.async_update_device_registry()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    device.async_setup_events()

    entry.add_update_listener(device.async_new_address_callback)
    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, device.shutdown)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Axis device config entry."""
    device: AxisNetworkDevice = hass.data[AXIS_DOMAIN].pop(entry.entry_id)
    return await device.async_reset()


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", entry.version)

    if entry.version != 3:
        # Home Assistant 2023.2
        entry.version = 3

    _LOGGER.info("Migration to version %s successful", entry.version)

    return True
