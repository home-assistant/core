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
    CONF_PROFILES,
    CONF_USE_DEFLECTIONS,
    CONF_USE_PORT,
    CONF_USE_PROFILES,
    CONF_USE_TRACKER,
    CONF_USE_WIFI,
    DATA_FRITZ_TOOLS_INSTANCE,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_PROFILES,
    DEFAULT_USE_DEFLECTIONS,
    DEFAULT_USE_PORT,
    DEFAULT_USE_PROFILES,
    DEFAULT_USE_TRACKER,
    DEFAULT_USE_WIFI,
    DOMAIN,
    ERROR_CONNECTION_ERROR,
    SUPPORTED_DOMAINS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Set up FRITZ!Box Tools component."""
    if DOMAIN in config:
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
    profile_list = entry.data.get(CONF_PROFILES, DEFAULT_PROFILES)
    use_profiles = entry.data.get(CONF_USE_PROFILES, DEFAULT_USE_PROFILES)
    use_wifi = entry.data.get(CONF_USE_WIFI, DEFAULT_USE_WIFI)
    use_port = entry.data.get(CONF_USE_PORT, DEFAULT_USE_PORT)
    use_deflections = entry.data.get(CONF_USE_DEFLECTIONS, DEFAULT_USE_DEFLECTIONS)
    use_tracker = entry.data.get(CONF_USE_TRACKER, DEFAULT_USE_TRACKER)

    fritz_tools = await hass.async_add_executor_job(
        lambda: FritzBoxTools(
            hass=hass,
            host=host,
            port=port,
            username=username,
            password=password,
            profile_list=profile_list,
            use_wifi=use_wifi,
            use_deflections=use_deflections,
            use_port=use_port,
            use_profiles=use_profiles,
            use_tracker=use_tracker,
        )
    )

    success, error = await hass.async_add_executor_job(fritz_tools.is_ok)
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

    return True
