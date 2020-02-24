"""The Netatmo integration."""
import asyncio
import logging
import secrets

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

PLATFORMS = ["binary_sensor", "camera", "climate", "sensor"]


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

    webhook_id = secrets.token_hex()
    data = hass.data[DOMAIN][entry.entry_id]

    if hass.components.cloud.async_active_subscription():
        data[CONF_CLOUDHOOK_URL] = await hass.components.cloud.async_create_cloudhook(
            webhook_id
        )

    data[CONF_WEBHOOK_ID] = webhook_id

    if CONF_CLOUDHOOK_URL in data:
        webhook_url = data[CONF_CLOUDHOOK_URL]
    else:
        webhook_url = hass.components.webhook.async_generate_url(data[CONF_WEBHOOK_ID])

    webhook_register(hass, DOMAIN, "Netatmo", webhook_id, handle_webhook)
    await hass.async_add_executor_job(data[AUTH].addwebhook, webhook_url)
    _LOGGER.info("Netatmo webhook url: %s", webhook_url)

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

    data = hass.data[DOMAIN][entry.entry_id]

    webhook_unregister(hass, data[CONF_WEBHOOK_ID])
    await hass.async_add_executor_job(data[AUTH].dropwebhook())

    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Cleanup when entry is removed."""
    if CONF_CLOUDHOOK_URL in entry.data:
        try:
            await cloud.async_delete_cloudhook(hass, entry.data[CONF_WEBHOOK_ID])
        except cloud.CloudNotAvailable:
            pass
