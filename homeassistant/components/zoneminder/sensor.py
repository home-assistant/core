"""Support for ZoneMinder sensors."""
import logging
from typing import Callable, List, Optional

import voluptuous as vol
from zoneminder.monitor import Monitor, TimePeriod
from zoneminder.zm import ZoneMinder

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MONITORED_CONDITIONS
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

from .common import get_client_from_data

_LOGGER = logging.getLogger(__name__)

CONF_INCLUDE_ARCHIVED = "include_archived"

DEFAULT_INCLUDE_ARCHIVED = False

SENSOR_TYPES = {
    "all": ["Events"],
    "hour": ["Events Last Hour"],
    "day": ["Events Last Day"],
    "week": ["Events Last Week"],
    "month": ["Events Last Month"],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(
            CONF_INCLUDE_ARCHIVED, default=DEFAULT_INCLUDE_ARCHIVED
        ): cv.boolean,
        vol.Optional(CONF_MONITORED_CONDITIONS, default=["all"]): vol.All(
            cv.ensure_list, [vol.In(list(SENSOR_TYPES))]
        ),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the ZoneMinder sensor platform."""
    _LOGGER.warning(
        "ZoneMinder sensor platform configuration through yaml configuration is no longer supported. Previousally available entities are automatcally created for you and disabled by default."
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], Optional[bool]], None],
) -> None:
    """Set up the sensor config entry."""
    zm_client = get_client_from_data(hass, config_entry.unique_id)
    monitors = await hass.async_add_job(zm_client.get_monitors)
    if not monitors:
        _LOGGER.warning("Could not fetch any monitors from ZoneMinder")

    entities: List[Entity] = [ZMSensorRunState(zm_client, config_entry)]
    for monitor in monitors:
        entities.append(ZMSensorMonitors(monitor, config_entry))

        for time_period in TimePeriod:
            entities.append(ZMSensorEvents(monitor, False, time_period, config_entry))
            entities.append(ZMSensorEvents(monitor, True, time_period, config_entry))

    async_add_entities(entities, True)


class ZMSensorMonitors(Entity):
    """Get the status of each ZoneMinder monitor."""

    def __init__(self, monitor: Monitor, config_entry: ConfigEntry):
        """Initialize monitor sensor."""
        self._monitor = monitor
        self._config_entry = config_entry
        self._state = None
        self._is_available = None

    @property
    def unique_id(self) -> Optional[str]:
        """Return a unique ID."""
        return f"{self._config_entry.unique_id}_{self._monitor.id}_status"

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._monitor.name} Status"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def available(self):
        """Return True if Monitor is available."""
        return self._is_available

    def update(self):
        """Update the sensor."""
        state = self._monitor.function
        if not state:
            self._state = None
        else:
            self._state = state.value
        self._is_available = self._monitor.is_available


class ZMSensorEvents(Entity):
    """Get the number of events for each monitor."""

    def __init__(
        self,
        monitor: Monitor,
        include_archived: bool,
        time_period: TimePeriod,
        config_entry: ConfigEntry,
    ):
        """Initialize event sensor."""

        self._monitor = monitor
        self._include_archived = include_archived
        self.time_period = time_period
        self._config_entry = config_entry
        self._state = None

    @property
    def unique_id(self) -> Optional[str]:
        """Return a unique ID."""
        return f"{self._config_entry.unique_id}_{self._monitor.id}_{self.time_period.value}_{self._include_archived}_events"

    @property
    def name(self):
        """Return the name of the sensor."""
        with_archived = " with archived" if self._include_archived else ""
        return f"{self._monitor.name} {self.time_period.title}{with_archived}"

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return False

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return "Events"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def update(self):
        """Update the sensor."""
        self._state = self._monitor.get_events(self.time_period, self._include_archived)


class ZMSensorRunState(Entity):
    """Get the ZoneMinder run state."""

    def __init__(self, client: ZoneMinder, config_entry: ConfigEntry):
        """Initialize run state sensor."""
        self._state = None
        self._is_available = None
        self._client = client
        self._config_entry = config_entry

    @property
    def unique_id(self) -> Optional[str]:
        """Return a unique ID."""
        return f"{self._config_entry.unique_id}_runstate"

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Run State"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def available(self):
        """Return True if ZoneMinder is available."""
        return self._is_available

    def update(self):
        """Update the sensor."""
        self._state = self._client.get_active_state()
        self._is_available = self._client.is_available
