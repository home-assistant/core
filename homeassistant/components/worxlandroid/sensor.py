"""Support for Worx Landroid mower."""
from __future__ import annotations

import asyncio
import logging

import aiohttp
import async_timeout
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_HOST, CONF_PIN, CONF_TIMEOUT, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

CONF_ALLOW_UNREACHABLE = "allow_unreachable"

DEFAULT_TIMEOUT = 5

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PIN): vol.All(vol.Coerce(str), vol.Match(r"\d{4}")),
        vol.Optional(CONF_ALLOW_UNREACHABLE, default=True): cv.boolean,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
    }
)

ERROR_STATE = [
    "blade-blocked",
    "repositioning-error",
    "wire-bounced",
    "blade-blocked",
    "outside-wire",
    "mower-lifted",
    "alarm-6",
    "upside-down",
    "alarm-8",
    "collision-sensor-blocked",
    "mower-tilted",
    "charge-error",
    "battery-error",
]


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Worx Landroid sensors."""
    for typ in ("battery", "state"):
        async_add_entities([WorxLandroidSensor(typ, config)])


class WorxLandroidSensor(SensorEntity):
    """Implementation of a Worx Landroid sensor."""

    def __init__(self, sensor, config):
        """Initialize a Worx Landroid sensor."""
        self._state = None
        self.sensor = sensor
        self.host = config.get(CONF_HOST)
        self.pin = config.get(CONF_PIN)
        self.timeout = config.get(CONF_TIMEOUT)
        self.allow_unreachable = config.get(CONF_ALLOW_UNREACHABLE)
        self.url = f"http://{self.host}/jsondata.cgi"

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"worxlandroid-{self.sensor}"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement of the sensor."""
        if self.sensor == "battery":
            return PERCENTAGE
        return None

    async def async_update(self) -> None:
        """Update the sensor data from the mower."""
        connection_error = False

        try:
            session = async_get_clientsession(self.hass)
            async with async_timeout.timeout(self.timeout):
                auth = aiohttp.helpers.BasicAuth("admin", self.pin)
                mower_response = await session.get(self.url, auth=auth)
        except (asyncio.TimeoutError, aiohttp.ClientError):
            if self.allow_unreachable is False:
                _LOGGER.error("Error connecting to mower at %s", self.url)

            connection_error = True

        # connection error
        if connection_error is True and self.allow_unreachable is False:
            if self.sensor == "error":
                self._state = "yes"
            elif self.sensor == "state":
                self._state = "connection-error"

        # connection success
        elif connection_error is False:
            # set the expected content type to be text/html
            # since the mover incorrectly returns it...
            data = await mower_response.json(content_type="text/html")

            # sensor battery
            if self.sensor == "battery":
                self._state = data["perc_batt"]

            # sensor error
            elif self.sensor == "error":
                self._state = "no" if self.get_error(data) is None else "yes"

            # sensor state
            elif self.sensor == "state":
                self._state = self.get_state(data)

        elif self.sensor == "error":
            self._state = "no"

    @staticmethod
    def get_error(obj):
        """Get the mower error."""
        for i, err in enumerate(obj["allarmi"]):
            if i != 2 and err == 1:  # ignore wire bounce errors
                return ERROR_STATE[i]

        return None

    def get_state(self, obj):
        """Get the state of the mower."""
        if (state := self.get_error(obj)) is None:
            if obj["batteryChargerState"] == "charging":
                return obj["batteryChargerState"]

            return obj["state"]

        return state
