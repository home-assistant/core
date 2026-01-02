"""Support for OPNsense Routers."""

from __future__ import annotations

import logging
from typing import Any

from pyopnsense import diagnostics
from pyopnsense.exceptions import APIException
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.discovery import load_platform
from homeassistant.helpers.typing import ConfigType

from .config_flow import normalize_url
from .const import (
    CONF_API_SECRET,
    CONF_INTERFACE_CLIENT,
    CONF_TRACKER_INTERFACES,
    CONF_TRACKER_MAC_ADDRESSES,
    DOMAIN,
    OPNSENSE_DATA,
)
from .coordinator import OPNsenseDataUpdateCoordinator

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


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the opnsense component (legacy YAML configuration)."""
    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]
    url = conf[CONF_URL]
    api_key = conf[CONF_API_KEY]
    api_secret = conf[CONF_API_SECRET]
    verify_ssl = conf[CONF_VERIFY_SSL]
    tracker_interfaces = conf[CONF_TRACKER_INTERFACES]

    interfaces_client = diagnostics.InterfaceClient(
        api_key, api_secret, url, verify_ssl, timeout=20
    )
    try:
        interfaces_client.get_arp()
    except APIException:
        _LOGGER.exception("Failure while connecting to OPNsense API endpoint")
        return False

    if tracker_interfaces:
        # Verify that specified tracker interfaces are valid
        netinsight_client = diagnostics.NetworkInsightClient(
            api_key, api_secret, url, verify_ssl, timeout=20
        )
        interfaces = list(netinsight_client.get_interfaces().values())
        for interface in tracker_interfaces:
            if interface not in interfaces:
                _LOGGER.error(
                    "Specified OPNsense tracker interface %s is not found", interface
                )
                return False

    hass.data[OPNSENSE_DATA] = {
        CONF_INTERFACE_CLIENT: interfaces_client,
        CONF_TRACKER_INTERFACES: tracker_interfaces,
        CONF_TRACKER_MAC_ADDRESSES: [],
    }

    load_platform(hass, Platform.DEVICE_TRACKER, DOMAIN, tracker_interfaces, config)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up OPNsense from a config entry."""
    url = normalize_url(entry.data[CONF_URL])
    api_key = entry.data[CONF_API_KEY]
    api_secret = entry.data[CONF_API_SECRET]
    verify_ssl = entry.data.get(CONF_VERIFY_SSL, False)
    tracker_interfaces = entry.data.get(CONF_TRACKER_INTERFACES, [])
    tracker_mac_addresses = entry.data.get(CONF_TRACKER_MAC_ADDRESSES, [])

    interface_client = diagnostics.InterfaceClient(
        api_key, api_secret, url, verify_ssl, timeout=20
    )

    coordinator = OPNsenseDataUpdateCoordinator(hass, entry, interface_client)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(OPNSENSE_DATA, {})
    hass.data[OPNSENSE_DATA][entry.entry_id] = {
        CONF_INTERFACE_CLIENT: interface_client,
        CONF_TRACKER_INTERFACES: tracker_interfaces,
        CONF_TRACKER_MAC_ADDRESSES: tracker_mac_addresses,
        "coordinator": coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(
        entry, [Platform.DEVICE_TRACKER]
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, [Platform.DEVICE_TRACKER]
    )
    if unload_ok and OPNSENSE_DATA in hass.data:
        hass.data[OPNSENSE_DATA].pop(entry.entry_id, None)
    return unload_ok
