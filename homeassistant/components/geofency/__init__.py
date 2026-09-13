"""Support for Geofency."""

from http import HTTPStatus

from aiohttp import web
import probatio

from homeassistant.components import webhook
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    ATTR_NAME,
    CONF_WEBHOOK_ID,
    STATE_NOT_HOME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_flow, config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import slugify
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN

type GeofencyConfigEntry = ConfigEntry[set[str]]

PLATFORMS = [Platform.DEVICE_TRACKER]

CONF_MOBILE_BEACONS = "mobile_beacons"

CONFIG_SCHEMA = probatio.Schema(
    {
        probatio.Optional(DOMAIN): probatio.Schema(
            {
                probatio.Optional(CONF_MOBILE_BEACONS, default=[]): probatio.All(
                    cv.ensure_list, [cv.string]
                )
            }
        )
    },
    extra=probatio.ALLOW_EXTRA,
)

ATTR_ADDRESS = "address"
ATTR_BEACON_ID = "beaconUUID"
ATTR_CURRENT_LATITUDE = "currentLatitude"
ATTR_CURRENT_LONGITUDE = "currentLongitude"
ATTR_DEVICE = "device"
ATTR_ENTRY = "entry"

BEACON_DEV_PREFIX = "beacon"

LOCATION_ENTRY = "1"
LOCATION_EXIT = "0"

TRACKER_UPDATE = f"{DOMAIN}_tracker_update"


def _address(value: str) -> str:
    r"""Coerce address by replacing '\n' with ' '."""
    return value.replace("\n", " ")


WEBHOOK_SCHEMA = probatio.Schema(
    {
        probatio.Required(ATTR_ADDRESS): probatio.All(cv.string, _address),
        probatio.Required(ATTR_DEVICE): probatio.All(cv.string, slugify),
        probatio.Required(ATTR_ENTRY): probatio.Any(LOCATION_ENTRY, LOCATION_EXIT),
        probatio.Required(ATTR_LATITUDE): cv.latitude,
        probatio.Required(ATTR_LONGITUDE): cv.longitude,
        probatio.Required(ATTR_NAME): probatio.All(cv.string, slugify),
        probatio.Optional(ATTR_CURRENT_LATITUDE): cv.latitude,
        probatio.Optional(ATTR_CURRENT_LONGITUDE): cv.longitude,
        probatio.Optional(ATTR_BEACON_ID): cv.string,
    },
    extra=probatio.ALLOW_EXTRA,
)

_DATA_GEOFENCY: HassKey[list[str]] = HassKey(DOMAIN)


async def async_setup(hass: HomeAssistant, hass_config: ConfigType) -> bool:
    """Set up the Geofency component."""
    mobile_beacons = hass_config.get(DOMAIN, {}).get(CONF_MOBILE_BEACONS, [])
    hass.data[_DATA_GEOFENCY] = [slugify(beacon) for beacon in mobile_beacons]
    return True


async def handle_webhook(
    hass: HomeAssistant, webhook_id: str, request: web.Request
) -> web.Response:
    """Handle incoming webhook from Geofency."""
    try:
        data = WEBHOOK_SCHEMA(dict(await request.post()))
    except probatio.MultipleInvalid as error:
        return web.Response(
            text=error.error_message, status=HTTPStatus.UNPROCESSABLE_ENTITY
        )

    if _is_mobile_beacon(data, hass.data[_DATA_GEOFENCY]):
        return _set_location(hass, data, None)
    if data["entry"] == LOCATION_ENTRY:
        location_name = data["name"]
    else:
        location_name = STATE_NOT_HOME
        if ATTR_CURRENT_LATITUDE in data:
            data[ATTR_LATITUDE] = data[ATTR_CURRENT_LATITUDE]
            data[ATTR_LONGITUDE] = data[ATTR_CURRENT_LONGITUDE]

    return _set_location(hass, data, location_name)


def _is_mobile_beacon(data, mobile_beacons):
    """Check if we have a mobile beacon."""
    return ATTR_BEACON_ID in data and data["name"] in mobile_beacons


def _device_name(data):
    """Return name of device tracker."""
    if ATTR_BEACON_ID in data:
        return f"{BEACON_DEV_PREFIX}_{data['name']}"
    return data["device"]


def _set_location(hass, data, location_name):
    """Fire HA event to set location."""
    device = _device_name(data)

    async_dispatcher_send(
        hass,
        TRACKER_UPDATE,
        device,
        (data[ATTR_LATITUDE], data[ATTR_LONGITUDE]),
        location_name,
        data,
    )

    return web.Response(text=f"Setting location for {device}")


async def async_setup_entry(hass: HomeAssistant, entry: GeofencyConfigEntry) -> bool:
    """Configure based on config entry."""
    entry.runtime_data = set()
    webhook.async_register(
        hass, DOMAIN, "Geofency", entry.data[CONF_WEBHOOK_ID], handle_webhook
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: GeofencyConfigEntry) -> bool:
    """Unload a config entry."""
    webhook.async_unregister(hass, entry.data[CONF_WEBHOOK_ID])
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async_remove_entry = config_entry_flow.webhook_async_remove_entry
