"""The yolink integration."""
from __future__ import annotations

from datetime import timedelta
import logging

import voluptuous as vol
from yolink.client import YoLinkClient
from yolink.const import OAUTH2_AUTHORIZE, OAUTH2_TOKEN
from yolink.mqtt_client import MqttClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import (
    aiohttp_client,
    config_entry_oauth2_flow,
    config_validation as cv,
)
from homeassistant.helpers.typing import ConfigType

from . import api, config_flow
from .const import ATTR_CLIENT, ATTR_COORDINATOR, ATTR_MQTT_CLIENT, DOMAIN
from .coordinator import YoLinkCoordinator

SCAN_INTERVAL = timedelta(minutes=5)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_CLIENT_ID): cv.string,
                vol.Required(CONF_CLIENT_SECRET): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = [Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the yolink component."""
    hass.data[DOMAIN] = {}
    if DOMAIN not in config:
        return True

    config_flow.OAuth2FlowHandler.async_register_implementation(
        hass,
        config_entry_oauth2_flow.LocalOAuth2Implementation(
            hass,
            DOMAIN,
            config[DOMAIN][CONF_CLIENT_ID],
            config[DOMAIN][CONF_CLIENT_SECRET],
            OAUTH2_AUTHORIZE,
            OAUTH2_TOKEN,
        ),
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up yolink from a config entry."""
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )

    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)

    auth_mgr = api.ConfigEntryAuth(
        hass, aiohttp_client.async_get_clientsession(hass), session
    )

    yolink_http_client = YoLinkClient(auth_mgr)
    yolink_mqtt_client = MqttClient(auth_mgr)
    coordinator = YoLinkCoordinator(hass, yolink_http_client, yolink_mqtt_client)
    await coordinator.init_coordinator()
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady as ex:
        _LOGGER.error("Fetching initial data failed: %s", ex)

    hass.data[DOMAIN][entry.entry_id] = {
        ATTR_CLIENT: yolink_http_client,
        ATTR_MQTT_CLIENT: yolink_mqtt_client,
        ATTR_COORDINATOR: coordinator,
    }
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
