"""Support for OPNsense Routers."""

import logging

from pyopnsense import diagnostics
from pyopnsense.exceptions import APIException
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL, Platform
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_API_SECRET,
    CONF_AVAILABLE_INTERFACES,
    CONF_INTERFACE_CLIENT,
    CONF_TRACKER_INTERFACES,
    DATA_HASS_CONFIG,
    DOMAIN,
    OPNSENSE_DATA,
)
from .types import APIData, Interfaces

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


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the OPNsense component."""
    hass.data[DATA_HASS_CONFIG] = config
    if config.get(DOMAIN) is not None:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=config[DOMAIN]
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the OPNsense component from a config entry."""

    api_data: APIData = {
        "api_key": entry.data[CONF_API_KEY],
        "api_secret": entry.data[CONF_API_SECRET],
        "base_url": entry.data[CONF_URL],
        "verify_cert": entry.data[CONF_VERIFY_SSL],
    }

    tracker_interfaces = entry.data.get(CONF_TRACKER_INTERFACES)

    interfaces_client = diagnostics.InterfaceClient(**api_data)

    # Test connection
    try:
        await hass.async_add_executor_job(interfaces_client.get_arp)
    except APIException:
        _LOGGER.exception("Failure while connecting to OPNsense API endpoint")
        return False

    hass.data[OPNSENSE_DATA] = {
        CONF_INTERFACE_CLIENT: interfaces_client,
        CONF_TRACKER_INTERFACES: tracker_interfaces,
    }

    hass.async_add_executor_job(
        _load_available_interfaces, hass, api_data, tracker_interfaces
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = entry.data
    hass.async_create_task(
        async_load_platform(
            hass,
            Platform.DEVICE_TRACKER,
            DOMAIN,
            tracker_interfaces,
            hass.data[DATA_HASS_CONFIG],
        )
    )
    return True


def _load_available_interfaces(
    hass: HomeAssistant, api_data: APIData, tracker_interfaces: Interfaces | None
) -> None:
    """Verify that specified tracker interfaces are valid."""
    netinsight_client = diagnostics.NetworkInsightClient(**api_data)
    interfaces = list(netinsight_client.get_interfaces().values())
    hass.data[OPNSENSE_DATA][CONF_AVAILABLE_INTERFACES] = interfaces
    if tracker_interfaces:
        # Verify that specified interfaces are valid
        for interface in tracker_interfaces:
            if interface not in interfaces:
                _LOGGER.error(
                    "Specified OPNsense tracker interface %s is not found", interface
                )
