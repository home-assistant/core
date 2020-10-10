"""Support for Plaato Airlock."""
import logging

from aiohttp import web
import voluptuous as vol

from homeassistant.components.sensor import DOMAIN as SENSOR
from homeassistant.const import (
    CONF_WEBHOOK_ID,
    HTTP_OK,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    VOLUME_GALLONS,
    VOLUME_LITERS,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ["webhook"]

PLAATO_DEVICE_SENSORS = "sensors"
PLAATO_DEVICE_ATTRS = "attrs"

ATTR_DEVICE_ID = "device_id"
ATTR_DEVICE_NAME = "device_name"
ATTR_TEMP_UNIT = "temp_unit"
ATTR_VOLUME_UNIT = "volume_unit"
ATTR_BPM = "bpm"
ATTR_TEMP = "temp"
ATTR_SG = "sg"
ATTR_OG = "og"
ATTR_BUBBLES = "bubbles"
ATTR_ABV = "abv"
ATTR_CO2_VOLUME = "co2_volume"
ATTR_BATCH_VOLUME = "batch_volume"

SENSOR_UPDATE = f"{DOMAIN}_sensor_update"
SENSOR_DATA_KEY = f"{DOMAIN}.{SENSOR}"

WEBHOOK_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_NAME): cv.string,
        vol.Required(ATTR_DEVICE_ID): cv.positive_int,
        vol.Required(ATTR_TEMP_UNIT): vol.Any(TEMP_CELSIUS, TEMP_FAHRENHEIT),
        vol.Required(ATTR_VOLUME_UNIT): vol.Any(VOLUME_LITERS, VOLUME_GALLONS),
        vol.Required(ATTR_BPM): cv.positive_int,
        vol.Required(ATTR_TEMP): vol.Coerce(float),
        vol.Required(ATTR_SG): vol.Coerce(float),
        vol.Required(ATTR_OG): vol.Coerce(float),
        vol.Required(ATTR_ABV): vol.Coerce(float),
        vol.Required(ATTR_CO2_VOLUME): vol.Coerce(float),
        vol.Required(ATTR_BATCH_VOLUME): vol.Coerce(float),
        vol.Required(ATTR_BUBBLES): cv.positive_int,
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, hass_config):
    """Set up the Plaato component."""
    return True


async def async_setup_entry(hass, entry):
    """Configure based on config entry."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    webhook_id = entry.data[CONF_WEBHOOK_ID]
    hass.components.webhook.async_register(DOMAIN, "Plaato", webhook_id, handle_webhook)

    hass.async_create_task(hass.config_entries.async_forward_entry_setup(entry, SENSOR))

    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    hass.components.webhook.async_unregister(entry.data[CONF_WEBHOOK_ID])
    hass.data[SENSOR_DATA_KEY]()

    await hass.config_entries.async_forward_entry_unload(entry, SENSOR)
    return True


async def handle_webhook(hass, webhook_id, request):
    """Handle incoming webhook from Plaato."""
    try:
        data = WEBHOOK_SCHEMA(await request.json())
    except vol.MultipleInvalid as error:
        _LOGGER.warning("An error occurred when parsing webhook data <%s>", error)
        return

    device_id = _device_id(data)

    attrs = {
        ATTR_DEVICE_NAME: data.get(ATTR_DEVICE_NAME),
        ATTR_DEVICE_ID: data.get(ATTR_DEVICE_ID),
        ATTR_TEMP_UNIT: data.get(ATTR_TEMP_UNIT),
        ATTR_VOLUME_UNIT: data.get(ATTR_VOLUME_UNIT),
    }

    sensors = {
        ATTR_TEMP: data.get(ATTR_TEMP),
        ATTR_BPM: data.get(ATTR_BPM),
        ATTR_SG: data.get(ATTR_SG),
        ATTR_OG: data.get(ATTR_OG),
        ATTR_ABV: data.get(ATTR_ABV),
        ATTR_CO2_VOLUME: data.get(ATTR_CO2_VOLUME),
        ATTR_BATCH_VOLUME: data.get(ATTR_BATCH_VOLUME),
        ATTR_BUBBLES: data.get(ATTR_BUBBLES),
    }

    hass.data[DOMAIN][device_id] = {
        PLAATO_DEVICE_ATTRS: attrs,
        PLAATO_DEVICE_SENSORS: sensors,
    }

    async_dispatcher_send(hass, SENSOR_UPDATE, device_id)

    return web.Response(text=f"Saving status for {device_id}", status=HTTP_OK)


def _device_id(data):
    """Return name of device sensor."""
    return f"{data.get(ATTR_DEVICE_NAME)}_{data.get(ATTR_DEVICE_ID)}"
