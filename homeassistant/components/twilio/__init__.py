"""The Twilio integration."""
from __future__ import annotations

from aiohttp import web
from twilio.rest import Client
import voluptuous as vol

from homeassistant.components import webhook
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_flow
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType

from .const import CONF_ACCOUNT_SID, CONF_AUTH_TOKEN, DOMAIN, RECEIVED_DATA

DATA_TWILIO = DOMAIN

CONFIG_SCHEMA = vol.All(
    cv.deprecated(DOMAIN),
    vol.Schema(
        {
            vol.Optional(DOMAIN): vol.Schema(
                {
                    vol.Required(CONF_ACCOUNT_SID): cv.string,
                    vol.Required(CONF_AUTH_TOKEN): cv.string,
                }
            )
        },
        extra=vol.ALLOW_EXTRA,
    ),
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Twilio component."""
    if DOMAIN not in config:
        return True

    async_create_issue(
        hass,
        DOMAIN,
        "deprecated_yaml",
        breaks_in_ha_version="2022.12.0",
        is_fixable=False,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
    )
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config[DOMAIN]
        )
    )

    return True


async def handle_webhook(
    hass: HomeAssistant, webhook_id: str, request: web.Request
) -> web.Response:
    """Handle incoming webhook from Twilio for inbound messages and calls."""
    data = dict(await request.post())
    data["webhook_id"] = webhook_id
    hass.bus.async_fire(RECEIVED_DATA, data)

    return web.Response(text="")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Configure based on config entry."""

    hass.data[DOMAIN] = Client(
        entry.data[CONF_ACCOUNT_SID],
        entry.data[CONF_AUTH_TOKEN],
    )
    webhook.async_register(
        hass, DOMAIN, "Twilio", entry.data[CONF_WEBHOOK_ID], handle_webhook
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    webhook.async_unregister(hass, entry.data[CONF_WEBHOOK_ID])
    del hass.data[DOMAIN]
    return True


async_remove_entry = config_entry_flow.webhook_async_remove_entry
