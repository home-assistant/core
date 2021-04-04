"""Support for AVM Fritz!Box functions."""
import logging

from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_REAUTH, ConfigEntry
from homeassistant.const import (
    CONF_DEVICES,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from .common import FritzBoxTools
from .const import (
    DATA_FRITZ_TOOLS_INSTANCE,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DOMAIN,
    ERROR_CONNECTION_ERROR,
    SUPPORTED_DOMAINS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Set up FRITZ!Box Tools component."""
    if DOMAIN not in config:
        return True
        for entry_config in config[DOMAIN][CONF_DEVICES]:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": SOURCE_IMPORT}, data=entry_config
                )
            )

    return True


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

    success, error = await fritz_tools.async_setup()

    if not success and error is ERROR_CONNECTION_ERROR:
        _LOGGER.error("Unable to setup FRITZ!Box Tools component")
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_REAUTH},
                data=entry,
            )
        )
        return False

    hass.data.setdefault(DOMAIN, {DATA_FRITZ_TOOLS_INSTANCE: {}, CONF_DEVICES: set()})
    hass.data[DOMAIN][DATA_FRITZ_TOOLS_INSTANCE][entry.entry_id] = fritz_tools

    # Load the other platforms like switch
    for domain in SUPPORTED_DOMAINS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, domain)
        )

    return True


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigType) -> bool:
    """Unload FRITZ!Box Tools config entry."""
    hass.data[DOMAIN][DATA_FRITZ_TOOLS_INSTANCE].pop(entry.entry_id)

    for domain in SUPPORTED_DOMAINS:
        await hass.config_entries.async_forward_entry_unload(entry, domain)

    fritzbox: FritzBoxTools = hass.data[DOMAIN][entry.entry_id]
    fritzbox.unload()

    return True
