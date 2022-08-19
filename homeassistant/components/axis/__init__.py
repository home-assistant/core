"""Support for Axis devices."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE, CONF_MAC, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.entity_registry import async_migrate_entries

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
    hass.data[AXIS_DOMAIN][config_entry.unique_id] = device
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
    device: AxisNetworkDevice = hass.data[AXIS_DOMAIN].pop(config_entry.unique_id)
    return await device.async_reset()


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    #  Flatten configuration but keep old data if user rollbacks HASS prior to 0.106
    if config_entry.version == 1:
        unique_id = config_entry.data[CONF_MAC]
        data = {**config_entry.data, **config_entry.data[CONF_DEVICE]}
        hass.config_entries.async_update_entry(
            config_entry, unique_id=unique_id, data=data
        )
        config_entry.version = 2

    # Normalise MAC address of device which also affects entity unique IDs
    if config_entry.version == 2 and (old_unique_id := config_entry.unique_id):
        new_unique_id = format_mac(old_unique_id)

        @callback
        def update_unique_id(entity_entry):
            """Update unique ID of entity entry."""
            return {
                "new_unique_id": entity_entry.unique_id.replace(
                    old_unique_id, new_unique_id
                )
            }

        if old_unique_id != new_unique_id:
            await async_migrate_entries(hass, config_entry.entry_id, update_unique_id)

            hass.config_entries.async_update_entry(
                config_entry, unique_id=new_unique_id
            )

    _LOGGER.info("Migration to version %s successful", config_entry.version)

    return True
