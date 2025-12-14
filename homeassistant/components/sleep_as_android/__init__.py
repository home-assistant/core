"""The Sleep as Android integration."""

from __future__ import annotations

from http import HTTPStatus

from aiohttp.web import Request, Response
import voluptuous as vol

from homeassistant.components import webhook
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_WEBHOOK_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import ATTR_EVENT, ATTR_VALUE1, ATTR_VALUE2, ATTR_VALUE3, DOMAIN

PLATFORMS: list[Platform] = [Platform.EVENT, Platform.SENSOR]

type SleepAsAndroidConfigEntry = ConfigEntry

WEBHOOK_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_EVENT): str,
        vol.Optional(ATTR_VALUE1): str,
        vol.Optional(ATTR_VALUE2): str,
        vol.Optional(ATTR_VALUE3): str,
    }
)


async def handle_webhook(
    hass: HomeAssistant, webhook_id: str, request: Request
) -> Response:
    """Handle incoming Sleep as Android webhook request."""

    try:
        data = WEBHOOK_SCHEMA(await request.json())
    except vol.MultipleInvalid as error:
        return Response(
            text=error.error_message, status=HTTPStatus.UNPROCESSABLE_ENTITY
        )

    async_dispatcher_send(hass, DOMAIN, webhook_id, data)
    return Response(status=HTTPStatus.NO_CONTENT)


async def async_setup_entry(
    hass: HomeAssistant, entry: SleepAsAndroidConfigEntry
) -> bool:
    """Set up Sleep as Android from a config entry."""

    webhook.async_register(
        hass, DOMAIN, entry.title, entry.data[CONF_WEBHOOK_ID], handle_webhook
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: SleepAsAndroidConfigEntry
) -> bool:
    """Unload a config entry."""
    webhook.async_unregister(hass, entry.data[CONF_WEBHOOK_ID])
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
