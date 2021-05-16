"""Support for Honeywell (US) Total Connect Comfort climate systems."""
from datetime import timedelta

import somecomfort
import voluptuous as vol

from homeassistant.components.climate import PLATFORM_SCHEMA
from homeassistant.const import CONF_PASSWORD, CONF_REGION, CONF_USERNAME
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

from .const import (
    _LOGGER,
    CONF_COOL_AWAY_TEMPERATURE,
    CONF_DEV_ID,
    CONF_HEAT_AWAY_TEMPERATURE,
    CONF_LOC_ID,
    DEFAULT_COOL_AWAY_TEMPERATURE,
    DEFAULT_HEAT_AWAY_TEMPERATURE,
    DOMAIN,
)

PLATFORM_SCHEMA = vol.All(
    cv.deprecated(CONF_REGION),
    PLATFORM_SCHEMA.extend(
        {
            vol.Required(CONF_USERNAME): cv.string,
            vol.Required(CONF_PASSWORD): cv.string,
            vol.Optional(
                CONF_COOL_AWAY_TEMPERATURE, default=DEFAULT_COOL_AWAY_TEMPERATURE
            ): vol.Coerce(int),
            vol.Optional(
                CONF_HEAT_AWAY_TEMPERATURE, default=DEFAULT_HEAT_AWAY_TEMPERATURE
            ): vol.Coerce(int),
            vol.Optional(CONF_REGION): cv.string,
            vol.Optional(CONF_DEV_ID): cv.string,
            vol.Optional(CONF_LOC_ID): cv.string,
        }
    ),
)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=180)
PLATFORMS = ["climate"]


async def async_setup_entry(hass, config):
    """Set up the Honeywell thermostat."""
    username = config.data[CONF_USERNAME]
    password = config.data[CONF_PASSWORD]

    try:
        client = await hass.async_add_executor_job(
            somecomfort.SomeComfort, username, password
        )
    except somecomfort.AuthError:
        _LOGGER.error("Failed to login to honeywell account %s", username)
        return False
    except somecomfort.SomeComfortError:
        _LOGGER.error(
            "Failed to initialize the Honeywell client: "
            "Check your configuration (username, password), "
            "or maybe you have exceeded the API rate limit?"
        )
        return False

    loc_id = config.data.get(CONF_LOC_ID)
    dev_id = config.data.get(CONF_DEV_ID)

    for location in client.locations_by_id.values():
        for device in location.devices_by_id.values():
            if (not loc_id or location.locationid == loc_id) and (
                not dev_id or device.deviceid == dev_id
            ):
                data = HoneywellService(hass, client, username, password, device)
                await data.update()
                hass.data[DOMAIN] = data
                hass.config_entries.async_setup_platforms(config, PLATFORMS)

    return True


class HoneywellService:
    """Get the latest data and update."""

    def __init__(self, hass, client, username, password, device):
        """Initialize the data object."""
        self._hass = hass
        self._client = client
        self._username = username
        self._password = password
        self._device = device

    def _retry(self) -> bool:
        """Recreate a new somecomfort client.

        When we got an error, the best way to be sure that the next query
        will succeed, is to recreate a new somecomfort client.
        """
        try:
            self._client = somecomfort.SomeComfort(self._username, self._password)
        except somecomfort.AuthError:
            _LOGGER.error("Failed to login to honeywell account %s", self._username)
            return False
        except somecomfort.SomeComfortError as ex:
            _LOGGER.error("Failed to initialize honeywell client: %s", str(ex))
            return False

        devices = [
            device
            for location in self._client.locations_by_id.values()
            for device in location.devices_by_id.values()
            if device.name == self._device.name
        ]

        if len(devices) != 1:
            _LOGGER.error("Failed to find device %s", self._device.name)
            return False

        self._device = devices[0]
        return True

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def update(self) -> None:
        """Update the state."""
        retries = 3
        while retries > 0:
            try:
                await self._hass.async_add_executor_job(self._device.refresh)
                break
            except (
                somecomfort.client.APIRateLimited,
                OSError,
                somecomfort.client.ConnectionTimeout,
            ) as exp:
                retries -= 1
                if retries == 0:
                    raise exp
                if not self._retry():
                    raise exp
                _LOGGER.error("SomeComfort update failed, Retrying - Error: %s", exp)

        _LOGGER.debug(
            "latestData = %s ", self._device._data  # pylint: disable=protected-access
        )
