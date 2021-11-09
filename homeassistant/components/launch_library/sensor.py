"""A sensor platform that give you information about the next space launch."""
from __future__ import annotations

from datetime import timedelta
import logging

from pylaunches import PyLaunches, PyLaunchesException
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import ATTR_ATTRIBUTION, CONF_NAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import (
    ATTR_AGENCY,
    ATTR_AGENCY_COUNTRY_CODE,
    ATTR_LAUNCH_TIME,
    ATTR_STREAM,
    ATTRIBUTION,
    DEFAULT_NAME,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(hours=1)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string}
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Create the launch sensor."""
    name = config[CONF_NAME]
    session = async_get_clientsession(hass)
    launches = PyLaunches(session)

    async_add_entities([LaunchLibrarySensor(launches, name)], True)


class LaunchLibrarySensor(SensorEntity):
    """Representation of a launch_library Sensor."""

    _attr_icon = "mdi:rocket"

    def __init__(self, api: PyLaunches, name: str) -> None:
        """Initialize the sensor."""
        self.api = api
        self._attr_name = name

    async def async_update(self) -> None:
        """Get the latest data."""
        try:
            launches = await self.api.upcoming_launches()
        except PyLaunchesException as exception:
            _LOGGER.error("Error getting data, %s", exception)
            self._attr_available = False
        else:
            if next_launch := next((launch for launch in launches), None):
                self._attr_available = True
                self._attr_native_value = next_launch.name
                self._attr_extra_state_attributes = {
                    ATTR_LAUNCH_TIME: next_launch.net,
                    ATTR_AGENCY: next_launch.launch_service_provider.name,
                    ATTR_AGENCY_COUNTRY_CODE: next_launch.pad.location.country_code,
                    ATTR_STREAM: next_launch.webcast_live,
                    ATTR_ATTRIBUTION: ATTRIBUTION,
                }
