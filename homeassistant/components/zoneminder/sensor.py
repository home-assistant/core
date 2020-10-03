"""Support for ZoneMinder sensors."""
import logging
from typing import Any, Callable, Dict, List, Optional

from zoneminder.monitor import Monitor, TimePeriod
from zoneminder.zm import ZoneMinder

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import StateType

from .common import get_config_data

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], Optional[bool]], None],
) -> None:
    """Set up the sensor config entry."""
    config_data = get_config_data(hass, config_entry)
    client = config_data.client
    entities = [ZMSensorRunState(config_data.client, config_entry)]

    for monitor in await hass.async_add_executor_job(client.get_monitors):
        entities.append(ZMSensorMonitors(monitor, config_entry))

        for time_period in TimePeriod:
            for include_archived in (True, False):
                entities.append(
                    ZMSensorEvents(monitor, include_archived, time_period, config_entry)
                )

    async_add_entities(entities, True)


class ZMSensorMonitors(Entity):
    """Get the status of each ZoneMinder monitor."""

    def __init__(self, monitor: Monitor, config_entry: ConfigEntry) -> None:
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
    def name(self) -> Optional[str]:
        """Return the name of the sensor."""
        return f"Zoneminder {self._monitor.name} Status"

    @property
    def state(self) -> StateType:
        """Return the state of the sensor."""
        return self._state

    @property
    def available(self) -> bool:
        """Return True if Monitor is available."""
        return self._is_available

    def update(self) -> None:
        """Update the sensor."""

        try:
            state = self._monitor.function
            self._state = state.value if state else None
            self._is_available = self._monitor.is_available
        except Exception:  # pylint: disable=broad-except
            self._is_available = False


class ZMSensorEvents(Entity):
    """Get the number of events for each monitor."""

    def __init__(
        self,
        monitor: Monitor,
        include_archived: bool,
        time_period: TimePeriod,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize event sensor."""

        self._monitor = monitor
        self._include_archived = include_archived
        self.time_period = time_period
        self._config_entry = config_entry
        archived_name = ZMSensorEvents.get_archived_name(include_archived)
        self._unique_id = f"{self._config_entry.unique_id}_{self._monitor.id}_{self.time_period.period}_{archived_name}_events"
        self._name = ZMSensorEvents.get_name(
            monitor.name, time_period, include_archived
        )
        self._is_available = False
        self._state = None

    @property
    def unique_id(self) -> Optional[str]:
        """Return a unique ID."""
        return self._unique_id

    @property
    def name(self) -> Optional[str]:
        """Return the name of the sensor."""
        return self._name

    @property
    def unit_of_measurement(self) -> Optional[str]:
        """Return the unit of measurement of this entity, if any."""
        return "Events"

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return False

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._is_available

    @property
    def state(self) -> StateType:
        """Return the state of the sensor."""
        return self._state

    def update(self) -> None:
        """Update the sensor."""

        try:
            self._state = self._monitor.get_events(
                self.time_period, self._include_archived
            )
            self._is_available = True
        except Exception:  # pylint: disable=broad-except
            self._is_available = False

    @staticmethod
    def get_name(
        monitor_name: str, time_period: TimePeriod, include_archived: bool
    ) -> str:
        """Get a formatted name."""
        archived_name = ZMSensorEvents.get_archived_name(include_archived)
        return f"Zoneminder {monitor_name} Events {time_period.period}_{archived_name}"

    @staticmethod
    def get_archived_name(include_archived: bool) -> str:
        """Get archived name."""
        return "with_archived" if include_archived else "without_archived"


class ZMSensorRunState(Entity):
    """Get the ZoneMinder run state."""

    def __init__(self, client: ZoneMinder, config_entry: ConfigEntry) -> None:
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
    def name(self) -> Optional[str]:
        """Return the name of the sensor."""
        return "Zoneminder Run State"

    @property
    def state(self) -> StateType:
        """Return the state of the sensor."""
        return self._state

    @property
    def available(self) -> bool:
        """Return True if ZoneMinder is available."""
        return self._is_available

    @property
    def state_attributes(self) -> Optional[Dict[str, Any]]:
        """Return the camera state attributes."""
        return {CONF_HOST: self._config_entry.data[CONF_HOST]}

    def update(self) -> None:
        """Update the sensor."""

        try:
            self._state = self._client.get_active_state()
            self._is_available = self._client.is_available
        except Exception:  # pylint: disable=broad-except
            self._is_available = False
