"""Support for OPNsense Routers."""

import logging

from aiopnsense import (
    OPNsenseBelowMinFirmware,
    OPNsenseClient,
    OPNsenseConnectionError,
    OPNsenseInvalidAuth,
    OPNsenseInvalidURL,
    OPNsensePrivilegeMissing,
    OPNsenseSSLError,
    OPNsenseTimeoutError,
    OPNsenseUnknownFirmware,
)
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.discovery import load_platform
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

    session = async_get_clientsession(hass, verify_ssl=verify_ssl)
    client = OPNsenseClient(
        url,
        api_key,
        api_secret,
        session,
        opts={"verify_ssl": verify_ssl},
    )
    try:
        await client.validate()
        if tracker_interfaces:
            interfaces_resp = await client.get_interfaces()
    except OPNsenseUnknownFirmware:
        _LOGGER.error("Error checking the OPNsense firmware version at %s", url)
        return False
    except OPNsenseBelowMinFirmware:
        _LOGGER.error(
            "OPNsense Firmware is below the minimum supported version at %s", url
        )
        return False
    except OPNsenseInvalidURL:
        _LOGGER.error(
            "Invalid URL while connecting to OPNsense API endpoint at %s", url
        )
        return False
    except OPNsenseTimeoutError:
        _LOGGER.error("Timeout while connecting to OPNsense API endpoint at %s", url)
        return False
    except OPNsenseSSLError:
        _LOGGER.error(
            "Unable to verify SSL while connecting to OPNsense API endpoint at %s", url
        )
        return False
    except OPNsenseInvalidAuth:
        _LOGGER.error(
            "Authentication failure while connecting to OPNsense API endpoint at %s",
            url,
        )
        return False
    except OPNsensePrivilegeMissing:
        _LOGGER.error(
            "Invalid Permissions while connecting to OPNsense API endpoint at %s",
            url,
        )
        return False
    except OPNsenseConnectionError:
        _LOGGER.error(
            "Connection failure while connecting to OPNsense API endpoint at %s",
            url,
        )
        return False

    if tracker_interfaces:
        # Verify that specified tracker interfaces are valid
        known_interfaces = [
            ifinfo.get("name", "") for ifinfo in interfaces_resp.values()
        ]
        for intf_description in tracker_interfaces:
            if intf_description not in known_interfaces:
                _LOGGER.error(
                    "Specified OPNsense tracker interface %s is not found",
                    intf_description,
                )
                return False

    hass.data[OPNSENSE_DATA] = {
        CONF_INTERFACE_CLIENT: client,
        CONF_TRACKER_INTERFACES: tracker_interfaces,
    }

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
