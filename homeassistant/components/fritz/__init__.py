"""Support for AVM Fritz!Box functions."""
import logging

from fritzconnection.core.exceptions import FritzConnectionException, FritzSecurityError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .common import FritzBoxTools
from .const import DEFAULT_HOST, DEFAULT_PORT, DOMAIN, SUPPORTED_DOMAINS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Set up fritzboxtools from config entry."""
    _LOGGER.debug("Setting up FRITZ!Box Tools component")
    host = entry.data.get(CONF_HOST, DEFAULT_HOST)
    port = entry.data.get(CONF_PORT, DEFAULT_PORT)
    username = entry.data.get(CONF_USERNAME)
    password = entry.data.get(CONF_PASSWORD)

    fritz_tools = FritzBoxTools(
        hass=hass,
        host=host,
        port=port,
        username=username,
        password=password,
    )

    try:
        await fritz_tools.async_setup()
    except FritzSecurityError as ex:
        raise ConfigEntryAuthFailed from ex
    except FritzConnectionException as ex:
        raise ConfigEntryNotReady from ex

    fritz_tools.start()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = fritz_tools

    # Load the other platforms like switch
    for domain in SUPPORTED_DOMAINS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, domain)
        )

    return True


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigType) -> bool:
    """Unload FRITZ!Box Tools config entry."""
    fritzbox: FritzBoxTools = hass.data[DOMAIN][entry.entry_id]
    fritzbox.unload()

    hass.data[DOMAIN].pop(entry.entry_id)

    for domain in SUPPORTED_DOMAINS:
        await hass.config_entries.async_forward_entry_unload(entry, domain)
    return True
