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
    CONF_WEBHOOK_ID,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow, config_validation as cv

from . import api, config_flow
from .const import (
    AUTH,
    CONF_CLOUDHOOK_URL,
    DATA_DEVICE_IDS,
    DATA_HANDLER,
    DATA_HOMES,
    DATA_PERSONS,
    DATA_SCHEDULES,
    DOMAIN,
    OAUTH2_AUTHORIZE,
    OAUTH2_TOKEN,
)
from .data_handler import NetatmoDataHandler
from .webhook import handle_webhook

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

PLATFORMS = ["camera", "climate", "sensor"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Netatmo component."""
    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][DATA_PERSONS] = {}
    hass.data[DOMAIN][DATA_DEVICE_IDS] = {}
    hass.data[DOMAIN][DATA_SCHEDULES] = {}
    hass.data[DOMAIN][DATA_HOMES] = {}

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
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )

    # Set unique id if non was set (migration)
    if not entry.unique_id:
        hass.config_entries.async_update_entry(entry, unique_id=DOMAIN)

    hass.data[DOMAIN][entry.entry_id] = {
        AUTH: api.ConfigEntryNetatmoAuth(hass, entry, implementation)
    }

    data_handler = NetatmoDataHandler(hass, entry)
    await data_handler.async_setup()
    hass.data[DOMAIN][entry.entry_id][DATA_HANDLER] = data_handler

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    async def unregister_webhook(_):
        if CONF_WEBHOOK_ID not in entry.data:
            return
        _LOGGER.debug("Unregister Netatmo webhook (%s)", entry.data[CONF_WEBHOOK_ID])
        webhook_unregister(hass, entry.data[CONF_WEBHOOK_ID])

    async def register_webhook(event):
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

        if entry.data["auth_implementation"] == "cloud" and not webhook_url.startswith(
            "https://"
        ):
            _LOGGER.warning(
                "Webhook not registered - "
                "https and port 443 is required to register the webhook"
            )
            return

        try:
            webhook_register(
                hass, DOMAIN, "Netatmo", entry.data[CONF_WEBHOOK_ID], handle_webhook
            )
            await hass.async_add_executor_job(
                hass.data[DOMAIN][entry.entry_id][AUTH].addwebhook, webhook_url
            )
            _LOGGER.info("Register Netatmo webhook: %s", webhook_url)
            hass.async_create_task(
                hass.config_entries.async_forward_entry_setup(entry, "light")
            )
        except pyatmo.ApiError as err:
            _LOGGER.error("Error during webhook registration - %s", err)

        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, unregister_webhook)

    if hass.state == CoreState.running:
        await register_webhook(None)
    else:
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, register_webhook)

    hass.services.async_register(DOMAIN, "register_webhook", register_webhook)
    hass.services.async_register(DOMAIN, "unregister_webhook", unregister_webhook)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    if CONF_WEBHOOK_ID in entry.data:
        await hass.async_add_executor_job(
            hass.data[DOMAIN][entry.entry_id][AUTH].dropwebhook
        )
        _LOGGER.info("Unregister Netatmo webhook.")

    await hass.data[DOMAIN][entry.entry_id][DATA_HANDLER].async_cleanup()

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

    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Cleanup when entry is removed."""
    if (
        CONF_WEBHOOK_ID in entry.data
        and hass.components.cloud.async_active_subscription()
    ):
        try:
            _LOGGER.debug(
                "Removing Netatmo cloudhook (%s)", entry.data[CONF_WEBHOOK_ID]
            )
            await cloud.async_delete_cloudhook(hass, entry.data[CONF_WEBHOOK_ID])
        except cloud.CloudNotAvailable:
            pass
