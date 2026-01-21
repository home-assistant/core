"""Support for OPNsense Routers."""

import logging

from pyopnsense import diagnostics
from pyopnsense.exceptions import APIException
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_API_SECRET,
    CONF_INTERFACE_CLIENT,
    CONF_TRACKER_INTERFACES,
    DOMAIN,
)
from .types import APIData

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_URL): cv.url,
                vol.Required(CONF_API_KEY): cv.string,
                vol.Required(CONF_API_SECRET): cv.string,
                vol.Optional(CONF_VERIFY_SSL, default=False): cv.boolean,
                vol.Optional(CONF_TRACKER_INTERFACES, default=[]): vol.All(
                    cv.ensure_list, [cv.string]
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = [Platform.DEVICE_TRACKER]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the OPNsense component."""
    if config.get(DOMAIN) is not None:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=config[DOMAIN]
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the OPNsense component from a config entry."""
    api_data: APIData = {
        "api_key": config_entry.data[CONF_API_KEY],
        "api_secret": config_entry.data[CONF_API_SECRET],
        "base_url": config_entry.data[CONF_URL],
        "verify_cert": config_entry.data[CONF_VERIFY_SSL],
    }

    tracker_interfaces = config_entry.data.get(CONF_TRACKER_INTERFACES)

    interfaces_client = diagnostics.InterfaceClient(**api_data)

    # Test connection
    try:
        await hass.async_add_executor_job(interfaces_client.get_arp)
    except APIException as err:
        raise ConfigEntryNotReady(f"Unable to connect to OPNsense API: {err}") from err

    config_entry.runtime_data = {
        CONF_INTERFACE_CLIENT: interfaces_client,
        CONF_TRACKER_INTERFACES: tracker_interfaces,
    }

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
