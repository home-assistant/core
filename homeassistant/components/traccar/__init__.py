"""Support for Traccar Client."""

from http import HTTPStatus
from json import JSONDecodeError
import logging

from aiohttp import web
import voluptuous as vol
from voluptuous.humanize import humanize_error

from homeassistant.components import webhook
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ID, CONF_WEBHOOK_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_flow, config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    ATTR_ACCURACY,
    ATTR_ALTITUDE,
    ATTR_BATTERY,
    ATTR_BEARING,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    ATTR_SPEED,
    DOMAIN,
)

PLATFORMS = [Platform.DEVICE_TRACKER]


TRACKER_UPDATE = f"{DOMAIN}_tracker_update"

LOGGER = logging.getLogger(__name__)

DEFAULT_ACCURACY = 200
DEFAULT_BATTERY = -1


def _id(value: str) -> str:
    """Coerce id by removing '-'."""
    return value.replace("-", "")


WEBHOOK_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ID): vol.All(cv.string, _id),
        vol.Required(ATTR_LATITUDE): cv.latitude,
        vol.Required(ATTR_LONGITUDE): cv.longitude,
        vol.Optional(ATTR_ACCURACY, default=DEFAULT_ACCURACY): vol.Coerce(float),
        vol.Optional(ATTR_ALTITUDE): vol.Coerce(float),
        vol.Optional(ATTR_BATTERY, default=DEFAULT_BATTERY): vol.Coerce(float),
        vol.Optional(ATTR_BEARING): vol.Coerce(float),
        vol.Optional(ATTR_SPEED): vol.Coerce(float),
    },
    extra=vol.REMOVE_EXTRA,
)


def _parse_json_body(json_body: dict) -> dict:
    """Parse JSON body from request."""
    location = json_body.get("location", {})
    coords = location.get("coords", {})
    battery_level = location.get("battery", {}).get("level")
    return {
        "id": json_body.get("device_id"),
        "lat": coords.get("latitude"),
        "lon": coords.get("longitude"),
        "accuracy": coords.get("accuracy"),
        "altitude": coords.get("altitude"),
        "batt": battery_level * 100 if battery_level is not None else DEFAULT_BATTERY,
        "bearing": coords.get("heading"),
        "speed": coords.get("speed"),
    }


async def handle_webhook(
    hass: HomeAssistant,
    webhook_id: str,
    request: web.Request,
) -> web.Response:
    """Handle incoming webhook with Traccar Client request."""
    if not (requestdata := dict(request.query)):
        try:
            requestdata = _parse_json_body(await request.json())
        except JSONDecodeError as error:
            LOGGER.error("Error parsing JSON body: %s", error)
            return web.Response(
                text="Invalid JSON",
                status=HTTPStatus.UNPROCESSABLE_ENTITY,
            )
    try:
        data = WEBHOOK_SCHEMA(requestdata)
    except vol.MultipleInvalid as error:
        LOGGER.warning(humanize_error(requestdata, error))
        return web.Response(
            text=error.error_message,
            status=HTTPStatus.UNPROCESSABLE_ENTITY,
        )

    attrs = {
        ATTR_ALTITUDE: data.get(ATTR_ALTITUDE),
        ATTR_BEARING: data.get(ATTR_BEARING),
        ATTR_SPEED: data.get(ATTR_SPEED),
    }

    device = data[ATTR_ID]

    async_dispatcher_send(
        hass,
        TRACKER_UPDATE,
        device,
        data[ATTR_LATITUDE],
        data[ATTR_LONGITUDE],
        data[ATTR_BATTERY],
        data[ATTR_ACCURACY],
        attrs,
    )

    return web.Response(text=f"Setting location for {device}")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Configure based on config entry."""
    hass.data.setdefault(DOMAIN, {"devices": set(), "unsub_device_tracker": {}})
    webhook.async_register(
        hass, DOMAIN, "Traccar", entry.data[CONF_WEBHOOK_ID], handle_webhook
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    webhook.async_unregister(hass, entry.data[CONF_WEBHOOK_ID])
    hass.data[DOMAIN]["unsub_device_tracker"].pop(entry.entry_id)()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async_remove_entry = config_entry_flow.webhook_async_remove_entry
