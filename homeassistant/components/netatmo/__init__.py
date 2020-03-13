"""The Netatmo integration."""
import asyncio
import logging
import secrets

import pyatmo
import voluptuous as vol

from homeassistant.components import cloud
from homeassistant.components.webhook import (
    async_register as webhook_register,
    async_unregister as webhook_unregister,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_DISCOVERY,
    CONF_USERNAME,
    CONF_WEBHOOK_ID,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow, config_validation as cv

from . import api, config_flow
from .const import (
    AUTH,
    CONF_CLOUDHOOK_URL,
    DATA_PERSONS,
    DOMAIN,
    OAUTH2_AUTHORIZE,
    OAUTH2_TOKEN,
)
from .webhook import handle_webhook

_LOGGER = logging.getLogger(__name__)

CONF_SECRET_KEY = "secret_key"
CONF_WEBHOOKS = "webhooks"

WAIT_FOR_CLOUD = 5

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_CLIENT_ID): cv.string,
                vol.Required(CONF_CLIENT_SECRET): cv.string,
                cv.deprecated(CONF_SECRET_KEY): cv.match_all,
                cv.deprecated(CONF_USERNAME): cv.match_all,
                cv.deprecated(CONF_WEBHOOKS): cv.match_all,
                cv.deprecated(CONF_DISCOVERY): cv.match_all,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = ["camera", "climate", "sensor"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Netatmo component."""
    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][DATA_PERSONS] = {}

    if DOMAIN not in config:
        return True

    config_flow.NetatmoFlowHandler.async_register_implementation(
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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Netatmo from a config entry."""
    implementation = await config_entry_oauth2_flow.async_get_config_entry_implementation(
        hass, entry
    )

    hass.data[DOMAIN][entry.entry_id] = {
        AUTH: api.ConfigEntryNetatmoAuth(hass, entry, implementation)
    }

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    async def unregister_webhook(event):
        _LOGGER.debug("Unregister Netatmo webhook (%s)", entry.data[CONF_WEBHOOK_ID])
        webhook_unregister(hass, entry.data[CONF_WEBHOOK_ID])

    async def register_webhook(event):
        # Wait for the could integration to be ready
        await asyncio.sleep(WAIT_FOR_CLOUD)

        if CONF_WEBHOOK_ID not in entry.data:
            data = {**entry.data, CONF_WEBHOOK_ID: secrets.token_hex()}
            hass.config_entries.async_update_entry(entry, data=data)

        if hass.components.cloud.async_active_subscription():
            if CONF_CLOUDHOOK_URL not in entry.data:
                webhook_url = await hass.components.cloud.async_create_cloudhook(
                    entry.data[CONF_WEBHOOK_ID]
                )
                data = {**entry.data, CONF_CLOUDHOOK_URL: webhook_url}
                hass.config_entries.async_update_entry(entry, data=data)
            else:
                webhook_url = entry.data[CONF_CLOUDHOOK_URL]
        else:
            webhook_url = hass.components.webhook.async_generate_url(
                entry.data[CONF_WEBHOOK_ID]
            )

        try:
            await hass.async_add_executor_job(
                hass.data[DOMAIN][entry.entry_id][AUTH].addwebhook, webhook_url
            )
            webhook_register(
                hass, DOMAIN, "Netatmo", entry.data[CONF_WEBHOOK_ID], handle_webhook
            )
            _LOGGER.info("Register Netatmo webhook: %s", webhook_url)
        except pyatmo.ApiError as err:
            _LOGGER.error("Error during webhook registration - %s", err)

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, unregister_webhook)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, register_webhook)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    if CONF_WEBHOOK_ID in entry.data:
        await hass.async_add_executor_job(
            hass.data[DOMAIN][entry.entry_id][AUTH].dropwebhook()
        )

    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Cleanup when entry is removed."""
    if CONF_WEBHOOK_ID in entry.data:
        try:
            _LOGGER.debug(
                "Removing Netatmo cloudhook (%s)", entry.data[CONF_WEBHOOK_ID]
            )
            await cloud.async_delete_cloudhook(hass, entry.data[CONF_WEBHOOK_ID])
        except cloud.CloudNotAvailable:
            pass
