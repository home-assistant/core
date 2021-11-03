"""Monitors home energy use for the ELIQ Online service."""
import asyncio
from datetime import timedelta
import logging

import eliqonline
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
)
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_NAME, POWER_WATT
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_CHANNEL_ID = "channel_id"

DEFAULT_NAME = "ELIQ Online"

ICON = "mdi:gauge"

SCAN_INTERVAL = timedelta(seconds=60)

UNIT_OF_MEASUREMENT = POWER_WATT

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ACCESS_TOKEN): cv.string,
        vol.Required(CONF_CHANNEL_ID): cv.positive_int,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the ELIQ Online sensor."""
    access_token = config.get(CONF_ACCESS_TOKEN)
    name = config.get(CONF_NAME, DEFAULT_NAME)
    channel_id = config.get(CONF_CHANNEL_ID)
    session = async_get_clientsession(hass)

    api = eliqonline.API(session=session, access_token=access_token)

    try:
        _LOGGER.debug("Probing for access to ELIQ Online API")
        await api.get_data_now(channelid=channel_id)
    except OSError as error:
        _LOGGER.error("Could not access the ELIQ Online API: %s", error)
        return False

    async_add_entities([EliqSensor(api, channel_id, name)], True)


class EliqSensor(SensorEntity):
    """Implementation of an ELIQ Online sensor."""

    _attr_state_class = STATE_CLASS_MEASUREMENT

    def __init__(self, api, channel_id, name):
        """Initialize the sensor."""
        self._name = name
        self._state = None
        self._api = api
        self._channel_id = channel_id

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Return icon."""
        return ICON

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return UNIT_OF_MEASUREMENT

    @property
    def native_value(self):
        """Return the state of the device."""
        return self._state

    async def async_update(self):
        """Get the latest data."""
        try:
            response = await self._api.get_data_now(channelid=self._channel_id)
            self._state = int(response["power"])
            _LOGGER.debug("Updated power from server %d W", self._state)
        except KeyError:
            _LOGGER.warning("Invalid response from ELIQ Online API")
        except (OSError, asyncio.TimeoutError) as error:
            _LOGGER.warning("Could not connect to the ELIQ Online API: %s", error)
