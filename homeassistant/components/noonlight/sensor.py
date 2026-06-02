"""Sensors exposing the Noonlight dispatch state and last event."""

from datetime import datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DISPATCH_STATES
from .coordinator import NoonlightConfigEntry, NoonlightCoordinator
from .entity import NoonlightEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NoonlightConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Noonlight sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            NoonlightDispatchState(coordinator),
            NoonlightLastEvent(coordinator),
            NoonlightLastHealthCheck(coordinator),
        ]
    )


class NoonlightDispatchState(NoonlightEntity, SensorEntity):
    """Enum sensor that is the single source of truth for dispatch state."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = DISPATCH_STATES

    def __init__(self, coordinator: NoonlightCoordinator) -> None:
        """Initialize the dispatch state sensor."""
        super().__init__(coordinator, "dispatch_state")

    @property
    def native_value(self) -> str:
        """Return the current dispatch state."""
        return self.coordinator.data["state"]

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Return the alarm ID and granted services as attributes."""
        data = self.coordinator.data
        return {
            "alarm_id": data.get("alarm_id"),
            "services": data.get("services", []),
        }


class NoonlightLastEvent(NoonlightEntity, SensorEntity):
    """Timestamp of the most recent state transition (event type as attr)."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: NoonlightCoordinator) -> None:
        """Initialize the last event sensor."""
        super().__init__(coordinator, "last_event")

    @property
    def native_value(self) -> datetime | None:
        """Return the timestamp of the most recent state transition."""
        last_event = self.coordinator.data.get("last_event")
        if not last_event:
            return None
        return dt_util.parse_datetime(last_event["timestamp"])

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Return the type and state of the most recent event as attributes."""
        last_event = self.coordinator.data.get("last_event") or {}
        return {
            "event_type": last_event.get("type"),
            "state": last_event.get("state"),
        }


class NoonlightLastHealthCheck(NoonlightEntity, SensorEntity):
    """Timestamp of the last successful Noonlight heartbeat probe."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: NoonlightCoordinator) -> None:
        """Initialize the last health check sensor."""
        super().__init__(coordinator, "last_health_check")

    @property
    def native_value(self) -> datetime | None:
        """Return the timestamp of the last successful heartbeat probe."""
        checked = self.coordinator.data.get("last_health_check")
        if not checked:
            return None
        return dt_util.parse_datetime(checked)
