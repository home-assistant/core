"""Support for Ambiclimate ac."""
import asyncio
import logging
from typing import Any

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

    _attr_temperature_unit = TEMP_CELSIUS
    _attr_target_temperature_step = 1
    _attr_supported_features = SUPPORT_FLAGS
    _attr_hvac_modes = [HVAC_MODE_HEAT, HVAC_MODE_OFF]

    def __init__(self, heater, store):
        """Initialize the thermostat."""
        self._heater = heater
        self._store = store
        self._attr_unique_id = heater.device_id
        self._attr_name = heater.name
        self._attr_device_info = {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.name,
            "manufacturer": "Ambiclimate",
        }

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        await self._heater.set_target_temperature(temperature)

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target hvac mode."""
        if hvac_mode == HVAC_MODE_HEAT:
            await self._heater.turn_on()
            return
        if hvac_mode == HVAC_MODE_OFF:
            await self._heater.turn_off()

    async def async_update(self) -> None:
        """Retrieve latest state."""
        try:
            token_info = await self._heater.control.refresh_access_token()
        except ambiclimate.AmbiclimateOauthError:
            _LOGGER.error("Failed to refresh access token")
            return

        if token_info:
            await self._store.async_save(token_info)

        data = await self._heater.update_device()
        self._attr_min_temp = self._heater.get_min_temp()
        self._attr_max_temp = self._heater.get_max_temp()
        self._attr_target_temperature = data.get("target_temperature")
        self._attr_current_temperature = data.get("temperature")
        self._attr_current_humidity = data.get("humidity")
        self._attr_hvac_mode = (
            HVAC_MODE_HEAT if data.get("power", "").lower() == "on" else HVAC_MODE_OFF
        )
