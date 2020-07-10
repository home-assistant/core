"""The syncthru component."""

from pysyncthru import SyncThru

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .const import DOMAIN
from .exceptions import SyncThruNotSupported


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Set up."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Set up config entry."""

    session = aiohttp_client.async_get_clientsession(hass)
    printer = hass.data[DOMAIN][entry.data[CONF_URL]] = SyncThru(
        entry.data[CONF_URL], session
    )

    try:
        await printer.update()
    except ValueError as ex:
        raise SyncThruNotSupported from ex
    else:
        if printer.is_unknown_state():
            raise ConfigEntryNotReady

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, SENSOR_DOMAIN)
    )
    return True


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Unload the config entry."""
    await hass.config_entries.async_forward_entry_unload(entry, SENSOR_DOMAIN)
    hass.data[DOMAIN].pop(entry.data[CONF_URL], None)
    return True
