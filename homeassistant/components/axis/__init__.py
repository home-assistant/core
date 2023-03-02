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


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the Axis integration."""
    hass.data.setdefault(AXIS_DOMAIN, {})

    try:
        api = await get_axis_device(hass, config_entry.data)
    except CannotConnect as err:
        raise ConfigEntryNotReady from err
    except AuthenticationRequired as err:
        raise ConfigEntryAuthFailed from err

    device = AxisNetworkDevice(hass, config_entry, api)
    hass.data[AXIS_DOMAIN][config_entry.entry_id] = device
    await device.async_update_device_registry()
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    device.async_setup_events()

    config_entry.add_update_listener(device.async_new_address_callback)
    config_entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, device.shutdown)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload Axis device config entry."""
    device: AxisNetworkDevice = hass.data[AXIS_DOMAIN].pop(config_entry.entry_id)
    return await device.async_reset()


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version != 3:
        # Home Assistant 2023.2
        config_entry.version = 3
        hass.config_entries.async_update_entry(config_entry)

    _LOGGER.info("Migration to version %s successful", config_entry.version)

    return True
