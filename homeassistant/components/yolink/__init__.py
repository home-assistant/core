"""The yolink integration."""
from __future__ import annotations

from datetime import timedelta
import logging

import async_timeout
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    aiohttp_client,
    config_entry_oauth2_flow,
    config_validation as cv,
)
from homeassistant.helpers.typing import ConfigType

from . import api, config_flow
from .client import YoLinkHttpClient
from .const import DOMAIN, OAUTH2_AUTHORIZE, OAUTH2_TOKEN

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

# TODO List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
PLATFORMS = ["sensor"]


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
    authMgr = api.ConfigEntryAuth(
        hass, aiohttp_client.async_get_clientsession(hass), session
    )
    yolinkClient = YoLinkHttpClient(authMgr)

    # If using a requests-based API lib
    # hass.data[DOMAIN][entry.entry_id] = api.ConfigEntryAuth(hass, session)
    hass.data[DOMAIN][entry.entry_id] = {
        "client": yolinkClient,
        "devices": [
            {
                "deviceId": "Test1",
                "name": "Test1",
                "type": "Outlet",
                "token": "asdfasdf",
            }
        ],
    }
    try:
        # Note: asyncio.TimeoutError and aiohttp.ClientError are already
        # handled by the data update coordinator.
        async with async_timeout.timeout(5):
            testResponse = await yolinkClient.getDeviceList()
            if not (testResponse.data["list"] is None):
                hass.data[DOMAIN][entry.entry_id]["devices"] = testResponse.data["list"]
    except BaseException as err:
        _LOGGER.warn("Call yolink api failed:%s", err)

    # If using an aiohttp-based API lib
    # hass.data[DOMAIN][entry.entry_id] = api.AsyncConfigEntryAuth(
    #     aiohttp_client.async_get_clientsession(hass), session
    # )

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
