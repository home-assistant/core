"""Support to trigger Maker IFTTT recipes."""

import json
import logging

from aiohttp import web
import probatio

from homeassistant.components import webhook
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_flow, config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DATA_API_KEYS, DOMAIN
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

EVENT_RECEIVED = "ifttt_webhook_received"

CONF_KEY = "key"

CONFIG_SCHEMA = probatio.Schema(
    {
        probatio.Optional(DOMAIN): probatio.Schema(
            {
                probatio.Required(probatio.Secret(CONF_KEY)): probatio.Any(
                    {cv.string: cv.string}, cv.string
                )
            }
        )
    },
    extra=probatio.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the IFTTT service component."""
    async_setup_services(hass)

    if DOMAIN not in config:
        return True

    api_keys = config[DOMAIN][CONF_KEY]
    if isinstance(api_keys, str):
        api_keys = {"default": api_keys}
    hass.data[DATA_API_KEYS] = api_keys

    return True


async def handle_webhook(
    hass: HomeAssistant, webhook_id: str, request: web.Request
) -> None:
    """Handle webhook callback."""
    body = await request.text()
    try:
        data = json.loads(body) if body else {}
    except ValueError:
        _LOGGER.error(
            "Received invalid data from IFTTT. Data needs to be formatted as JSON: %s",
            body,
        )
        return

    if not isinstance(data, dict):
        _LOGGER.error(
            "Received invalid data from IFTTT. Data needs to be a dictionary: %s", data
        )
        return

    data["webhook_id"] = webhook_id
    hass.bus.async_fire(EVENT_RECEIVED, data)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Configure based on config entry."""
    webhook.async_register(
        hass, DOMAIN, "IFTTT", entry.data[CONF_WEBHOOK_ID], handle_webhook
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    webhook.async_unregister(hass, entry.data[CONF_WEBHOOK_ID])
    return True


async_remove_entry = config_entry_flow.webhook_async_remove_entry
