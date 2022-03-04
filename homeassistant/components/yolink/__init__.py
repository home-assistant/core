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
from .client import HomeEventMQTTSubscription, YoLinkHttpClient, YoLinkMQTTClient
from .const import DOMAIN, HOME_ID, HOME_SUBSCRIPTION, OAUTH2_AUTHORIZE, OAUTH2_TOKEN
from .services import async_setup_services

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
    yolinkMQTTClient = YoLinkMQTTClient(authMgr, hass)

    # If using a requests-based API lib
    # hass.data[DOMAIN][entry.entry_id] = api.ConfigEntryAuth(hass, session)
    hass.data[DOMAIN][entry.entry_id] = {
        "client": yolinkClient,
        "mqttClient": yolinkMQTTClient,
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
            homeResponse = await yolinkClient.getGeneralInfo()
            if not (homeResponse.data["id"] is None):
                hass.data[DOMAIN][entry.entry_id][HOME_ID] = homeResponse.data["id"]
                hass.data[DOMAIN][entry.entry_id][
                    HOME_SUBSCRIPTION
                ] = HomeEventMQTTSubscription(homeResponse.data["id"])
                yolinkMQTTClient.subscribeHome(
                    hass.data[DOMAIN][entry.entry_id][HOME_SUBSCRIPTION]
                )
        async with async_timeout.timeout(5):
            devicesResponse = await yolinkClient.getDeviceList()
            if not (devicesResponse.data["devices"] is None):
                hass.data[DOMAIN][entry.entry_id]["devices"] = devicesResponse.data[
                    "devices"
                ]

        await yolinkMQTTClient.async_connect()
        # yolinkMQTTClient.subHomeEvents(hass.data[DOMAIN][entry.entry_id]["homeId"])
    except BaseException as err:
        _LOGGER.warning("Call yolink api failed: %s", err)
        return False

    await async_setup_services(hass, entry)

    # If using an aiohttp-based API lib
    # hass.data[DOMAIN][entry.entry_id] = api.AsyncConfigEntryAuth(
    #     aiohttp_client.async_get_clientsession(hass), session
    # )
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    # services register

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
