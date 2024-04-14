"""Support for Locative."""

from __future__ import annotations

from http import HTTPStatus
import logging

from aiohttp import web
import voluptuous as vol

from homeassistant.components import webhook
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ID,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_WEBHOOK_ID,
    STATE_NOT_HOME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_flow
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send

_LOGGER = logging.getLogger(__name__)

DOMAIN = "locative"
TRACKER_UPDATE = f"{DOMAIN}_tracker_update"

PLATFORMS = [Platform.DEVICE_TRACKER]

ATTR_DEVICE_ID = "device"
ATTR_TRIGGER = "trigger"


def _id(value: str) -> str:
    """Coerce id by removing '-'."""
    return value.replace("-", "")


def _validate_test_mode(obj: dict) -> dict:
    """Validate that id is provided outside of test mode."""
    if ATTR_ID not in obj and obj[ATTR_TRIGGER] != "test":
        raise vol.Invalid("Location id not specified")
    return obj


WEBHOOK_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required(ATTR_LATITUDE): cv.latitude,
            vol.Required(ATTR_LONGITUDE): cv.longitude,
            vol.Required(ATTR_DEVICE_ID): cv.string,
            vol.Required(ATTR_TRIGGER): cv.string,
            vol.Optional(ATTR_ID): vol.All(cv.string, _id),
        },
        extra=vol.ALLOW_EXTRA,
    ),
    _validate_test_mode,
)


async def handle_webhook(hass, webhook_id, request):
    """Handle incoming webhook from Locative."""
    try:
        data = WEBHOOK_SCHEMA(dict(await request.post()))
    except vol.MultipleInvalid as error:
        return web.Response(
            text=error.error_message, status=HTTPStatus.UNPROCESSABLE_ENTITY
        )

    device = data[ATTR_DEVICE_ID]
    location_name = data.get(ATTR_ID, data[ATTR_TRIGGER]).lower()
    direction = data[ATTR_TRIGGER]
    gps_location = (data[ATTR_LATITUDE], data[ATTR_LONGITUDE])

    if direction == "enter":
        async_dispatcher_send(hass, TRACKER_UPDATE, device, gps_location, location_name)
        return web.Response(text=f"Setting location to {location_name}")

    if direction == "exit":
        current_state = hass.states.get(f"{Platform.DEVICE_TRACKER}.{device}")

        if current_state is None or current_state.state == location_name:
            location_name = STATE_NOT_HOME
            async_dispatcher_send(
                hass, TRACKER_UPDATE, device, gps_location, location_name
            )
            return web.Response(text="Setting location to not home")

        # Ignore the message if it is telling us to exit a zone that we
        # aren't currently in. This occurs when a zone is entered
        # before the previous zone was exited. The enter message will
        # be sent first, then the exit message will be sent second.
        return web.Response(
            text=f"Ignoring exit from {location_name} (already in {current_state})",
        )

    if direction == "test":
        # In the app, a test message can be sent. Just return something to
        # the user to let them know that it works.
        return web.Response(text="Received test message.")

    _LOGGER.error("Received unidentified message from Locative: %s", direction)
    return web.Response(
        text=f"Received unidentified message: {direction}",
        status=HTTPStatus.UNPROCESSABLE_ENTITY,
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Configure based on config entry."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {"devices": set(), "unsub_device_tracker": {}}
    webhook.async_register(
        hass, DOMAIN, "Locative", entry.data[CONF_WEBHOOK_ID], handle_webhook
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    webhook.async_unregister(hass, entry.data[CONF_WEBHOOK_ID])
    hass.data[DOMAIN]["unsub_device_tracker"].pop(entry.entry_id)()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async_remove_entry = config_entry_flow.webhook_async_remove_entry
