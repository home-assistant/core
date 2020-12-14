"""Support for Ambiclimate ac."""
import asyncio
import logging

import ambiclimate
import voluptuous as vol

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import (
    ATTR_NAME,
    ATTR_TEMPERATURE,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    TEMP_CELSIUS,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    ATTR_VALUE,
    DOMAIN,
    SERVICE_COMFORT_FEEDBACK,
    SERVICE_COMFORT_MODE,
    SERVICE_TEMPERATURE_MODE,
    STORAGE_KEY,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE

SEND_COMFORT_FEEDBACK_SCHEMA = vol.Schema(
    {vol.Required(ATTR_NAME): cv.string, vol.Required(ATTR_VALUE): cv.string}
)

SET_COMFORT_MODE_SCHEMA = vol.Schema({vol.Required(ATTR_NAME): cv.string})

SET_TEMPERATURE_MODE_SCHEMA = vol.Schema(
    {vol.Required(ATTR_NAME): cv.string, vol.Required(ATTR_VALUE): cv.string}
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Ambicliamte device."""


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Ambicliamte device from config entry."""
    config = entry.data
    websession = async_get_clientsession(hass)
    store = hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)
    token_info = await store.async_load()

    oauth = ambiclimate.AmbiclimateOAuth(
        config[CONF_CLIENT_ID],
        config[CONF_CLIENT_SECRET],
        config["callback_url"],
        websession,
    )

    try:
        token_info = await oauth.refresh_access_token(token_info)
    except ambiclimate.AmbiclimateOauthError:
        token_info = None

    if not token_info:
        _LOGGER.error("Failed to refresh access token")
        return

    await store.async_save(token_info)

    data_connection = ambiclimate.AmbiclimateConnection(
        oauth, token_info=token_info, websession=websession
    )

    if not await data_connection.find_devices():
        _LOGGER.error("No devices found")
        return

    tasks = []
    for heater in data_connection.get_devices():
        tasks.append(heater.update_device_info())
    await asyncio.wait(tasks)

    devs = []
    for heater in data_connection.get_devices():
        devs.append(AmbiclimateEntity(heater, store))

    async_add_entities(devs, True)

    async def send_comfort_feedback(service):
        """Send comfort feedback."""
        device_name = service.data[ATTR_NAME]
        device = data_connection.find_device_by_room_name(device_name)
        if device:
            await device.set_comfort_feedback(service.data[ATTR_VALUE])

    hass.services.async_register(
        DOMAIN,
        SERVICE_COMFORT_FEEDBACK,
        send_comfort_feedback,
        schema=SEND_COMFORT_FEEDBACK_SCHEMA,
    )

    async def set_comfort_mode(service):
        """Set comfort mode."""
        device_name = service.data[ATTR_NAME]
        device = data_connection.find_device_by_room_name(device_name)
        if device:
            await device.set_comfort_mode()

    hass.services.async_register(
        DOMAIN, SERVICE_COMFORT_MODE, set_comfort_mode, schema=SET_COMFORT_MODE_SCHEMA
    )

    async def set_temperature_mode(service):
        """Set temperature mode."""
        device_name = service.data[ATTR_NAME]
        device = data_connection.find_device_by_room_name(device_name)
        if device:
            await device.set_temperature_mode(service.data[ATTR_VALUE])

    hass.services.async_register(
        DOMAIN,
        SERVICE_TEMPERATURE_MODE,
        set_temperature_mode,
        schema=SET_TEMPERATURE_MODE_SCHEMA,
    )


class AmbiclimateEntity(ClimateEntity):
    """Representation of a Ambiclimate Thermostat device."""

    def __init__(self, heater, store):
        """Initialize the thermostat."""
        self._heater = heater
        self._store = store
        self._data = {}

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._heater.device_id

    @property
    def name(self):
        """Return the name of the entity."""
        return self._heater.name

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.name,
            "manufacturer": "Ambiclimate",
        }

    @property
    def temperature_unit(self):
        """Return the unit of measurement which this thermostat uses."""
        return TEMP_CELSIUS

    @property
    def target_temperature(self):
        """Return the target temperature."""
        return self._data.get("target_temperature")

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return 1

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._data.get("temperature")

    @property
    def current_humidity(self):
        """Return the current humidity."""
        return self._data.get("humidity")

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return self._heater.get_min_temp()

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return self._heater.get_max_temp()

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def hvac_modes(self):
        """Return the list of available hvac operation modes."""
        return [HVAC_MODE_HEAT, HVAC_MODE_OFF]

    @property
    def hvac_mode(self):
        """Return current operation."""
        if self._data.get("power", "").lower() == "on":
            return HVAC_MODE_HEAT

        return HVAC_MODE_OFF

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        await self._heater.set_target_temperature(temperature)

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        if hvac_mode == HVAC_MODE_HEAT:
            await self._heater.turn_on()
            return
        if hvac_mode == HVAC_MODE_OFF:
            await self._heater.turn_off()

    async def async_update(self):
        """Retrieve latest state."""
        try:
            token_info = await self._heater.control.refresh_access_token()
        except ambiclimate.AmbiclimateOauthError:
            _LOGGER.error("Failed to refresh access token")
            return

        if token_info:
            await self._store.async_save(token_info)

        self._data = await self._heater.update_device()
