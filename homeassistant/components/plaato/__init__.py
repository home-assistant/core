"""Support for Plaato devices."""

import asyncio
from datetime import timedelta
import logging

from aiohttp import web
from pyplaato.plaato import Plaato, PlaatoDeviceType
import voluptuous as vol

from homeassistant.components.sensor import DOMAIN as SENSOR
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_TOKEN,
    CONF_WEBHOOK_ID,
    HTTP_OK,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    VOLUME_GALLONS,
    VOLUME_LITERS,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, InvalidStateError
from homeassistant.helpers import aiohttp_client
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_DEVICE_NAME,
    CONF_DEVICE_TYPE,
    CONF_USE_WEBHOOK,
    DOMAIN,
    PLATFORMS,
)

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

SCAN_INTERVAL = timedelta(minutes=10)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Plaato component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Configure based on config entry."""

    use_webhook = entry.data.get(CONF_USE_WEBHOOK, False)

    if use_webhook:
        setup_webhook(hass, entry)
    else:
        await async_setup_coordinator(hass, entry)

    for platform in PLATFORMS:
        if entry.options.get(platform, True):
            hass.async_create_task(
                hass.config_entries.async_forward_entry_setup(entry, platform)
            )

    entry.add_update_listener(async_reload_entry)
    return True


def setup_webhook(hass: HomeAssistant, entry: ConfigEntry):
    """Init webhook based on config entry."""
    if entry.data[CONF_WEBHOOK_ID] is not None:
        webhook_id = entry.data[CONF_WEBHOOK_ID]
        device_name = entry.data[CONF_DEVICE_NAME]
        hass.components.webhook.async_register(
            DOMAIN, f"{DOMAIN}.{device_name}", webhook_id, handle_webhook
        )
    else:
        raise InvalidStateError


async def async_setup_coordinator(hass: HomeAssistant, entry: ConfigEntry):
    """Init auth token based on config entry."""
    auth_token = entry.data.get(CONF_TOKEN)
    device_type = entry.data.get(CONF_DEVICE_TYPE)

    coordinator = PlaatoCoordinator(hass, auth_token, device_type)
    await coordinator.async_refresh()
    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    hass.data[DOMAIN][entry.entry_id] = coordinator

    for platform in PLATFORMS:
        if entry.options.get(platform, True):
            coordinator.platforms.append(platform)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    use_webhook = entry.data.get(CONF_USE_WEBHOOK)

    if use_webhook:
        return await async_unload_webhook(hass, entry)

    return await async_unload_coordinator(hass, entry)


async def async_unload_webhook(hass: HomeAssistant, entry: ConfigEntry):
    """Unload webhook based entry."""
    if entry.data[CONF_WEBHOOK_ID] is not None:
        hass.components.webhook.async_unregister(entry.data[CONF_WEBHOOK_ID])

    unloaded = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )
    if unloaded:
        hass.data[SENSOR_DATA_KEY]()

    return unloaded


async def async_unload_coordinator(hass: HomeAssistant, entry: ConfigEntry):
    """Unload auth token based entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    unloaded = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
                if platform in coordinator.platforms
            ]
        )
    )
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unloaded


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


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


class PlaatoCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    def __init__(self, hass, auth_token, device_type: PlaatoDeviceType):
        """Initialize."""
        self.api = Plaato(auth_token=auth_token)
        self.hass = hass
        self.device_type = device_type
        self.platforms = []

        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self):
        """Update data via library."""
        try:
            data = await self.api.get_data(
                session=aiohttp_client.async_get_clientsession(self.hass),
                device_type=self.device_type,
            )
            return data
        except Exception as exception:
            raise UpdateFailed(exception)
