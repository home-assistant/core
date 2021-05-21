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

    def __init__(self, launches: PyLaunches, name: str) -> None:
        """Initialize the sensor."""
        self.launches = launches
        self.next_launch = None
        self._name = name

    async def async_update(self) -> None:
        """Get the latest data."""
        try:
            launches = await self.launches.upcoming_launches()
        except PyLaunchesException as exception:
            _LOGGER.error("Error getting data, %s", exception)
        else:
            if launches:
                self.next_launch = launches[0]

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self) -> str | None:
        """Return the state of the sensor."""
        if self.next_launch:
            return self.next_launch.name
        return None

    @property
    def icon(self) -> str:
        """Return the icon of the sensor."""
        return "mdi:rocket"

    @property
    def extra_state_attributes(self) -> dict | None:
        """Return attributes for the sensor."""
        if self.next_launch:
            return {
                ATTR_LAUNCH_TIME: self.next_launch.net,
                ATTR_AGENCY: self.next_launch.launch_service_provider.name,
                ATTR_AGENCY_COUNTRY_CODE: self.next_launch.pad.location.country_code,
                ATTR_STREAM: self.next_launch.webcast_live,
                ATTR_ATTRIBUTION: ATTRIBUTION,
            }
        return None
