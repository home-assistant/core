"""Support for ZoneMinder sensors."""

from zoneminder.monitor import Monitor, TimePeriod
from zoneminder.zm import ZoneMinder

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import ZoneMinderConfigEntry
from .const import CONF_INCLUDE_ARCHIVED

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="all",
        name="Events",
    ),
    SensorEntityDescription(
        key="hour",
        entity_registry_enabled_default=False,
        name="Events Last Hour",
    ),
    SensorEntityDescription(
        key="day",
        entity_registry_enabled_default=False,
        name="Events Last Day",
    ),
    SensorEntityDescription(
        key="week",
        entity_registry_enabled_default=False,
        name="Events Last Week",
    ),
    SensorEntityDescription(
        key="month",
        entity_registry_enabled_default=False,
        name="Events Last Month",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZoneMinderConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the ZoneMinder sensor platform."""
    include_archived = entry.options[CONF_INCLUDE_ARCHIVED]

    sensors: list[SensorEntity] = []
    for monitor in entry.runtime_data.monitors:
        sensors.append(ZMSensorMonitors(monitor, entry.entry_id))
        sensors.extend(
            ZMSensorEvents(monitor, entry.entry_id, include_archived, description)
            for description in SENSOR_TYPES
        )
    sensors.append(ZMSensorRunState(entry.runtime_data.client, entry.entry_id))
    async_add_entities(sensors)


class ZMSensorMonitors(SensorEntity):
    """Get the status of each ZoneMinder monitor."""

    def __init__(self, monitor: Monitor, entry_id: str) -> None:
        """Initialize monitor sensor."""
        self._monitor = monitor
        self._attr_available = False
        self._attr_name = f"{self._monitor.name} Status"
        self._attr_unique_id = f"{entry_id}_{monitor.id}_status"

    def update(self) -> None:
        """Update the sensor."""
        self._monitor.update_monitor()
        if not (state := self._monitor.function):
            self._attr_native_value = None
        else:
            self._attr_native_value = state.value
        self._attr_available = self._monitor.is_available


class ZMSensorEvents(SensorEntity):
    """Get the number of events for each monitor."""

    _attr_native_unit_of_measurement = "Events"

    def __init__(
        self,
        monitor: Monitor,
        entry_id: str,
        include_archived: bool,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize event sensor."""
        self.entity_description = description

        self._monitor = monitor
        self._include_archived = include_archived
        self.time_period = TimePeriod.get_time_period(description.key)
        self._attr_name = f"{monitor.name} {self.time_period.title}"
        self._attr_unique_id = f"{entry_id}_{monitor.id}_{description.key}"

    def update(self) -> None:
        """Update the sensor."""
        self._attr_native_value = self._monitor.get_events(
            self.time_period, self._include_archived
        )


class ZMSensorRunState(SensorEntity):
    """Get the ZoneMinder run state."""

    _attr_name = "Run State"

    def __init__(self, client: ZoneMinder, entry_id: str) -> None:
        """Initialize run state sensor."""
        self._attr_available = False
        self._attr_unique_id = f"{entry_id}_run_state"
        self._client = client

    def update(self) -> None:
        """Update the sensor."""
        self._attr_native_value = self._client.get_active_state()
        self._attr_available = self._client.is_available
