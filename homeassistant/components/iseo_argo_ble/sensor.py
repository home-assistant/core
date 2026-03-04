"""ISEO BLE Lock — sensors (last event, battery)."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from iseo_argo_ble import LogEntry, battery_enum_to_pct

from .const import CONF_ADDRESS, DOMAIN
from .coordinator import (
    IseoLogCoordinator,
    _resolve_actor,
    entry_message,
    event_name,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ISEO sensor entities from a config entry."""
    from . import IseoRuntimeData  # noqa: PLC0415

    runtime_data: IseoRuntimeData = entry.runtime_data
    coordinator = runtime_data.coordinator
    async_add_entities(
        [
            IseoLastEventSensor(coordinator, entry),
            IseoBatterySensor(coordinator, entry),
        ]
    )


class IseoLastEventSensor(CoordinatorEntity[IseoLogCoordinator], SensorEntity):
    """Shows the most recent access-log entry from the lock."""

    _attr_has_entity_name = True
    _attr_translation_key = "last_event"

    def __init__(
        self, coordinator: IseoLogCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = (
            f"{entry.data[CONF_ADDRESS].replace(':', '').lower()}_last_event"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
        )

    @property
    def native_value(self) -> str | None:
        """Return the most recent event description."""
        entry: LogEntry | None = self.coordinator.data
        if entry is None:
            return None
        return entry_message(entry, self.coordinator.user_dir)

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Return additional attributes for the last event."""
        entry: LogEntry | None = self.coordinator.data
        if entry is None:
            return {}
        raw_actor = entry.user_info.strip() or entry.extra_description.strip()
        actor = _resolve_actor(raw_actor, self.coordinator.user_dir) if raw_actor else None
        return {
            "event_code": entry.event_code,
            "event_name": event_name(entry.event_code),
            "actor": actor or None,
            "timestamp": entry.timestamp.isoformat(),
            "battery": entry.battery,
        }


class IseoBatterySensor(CoordinatorEntity[IseoLogCoordinator], SensorEntity):
    """Shows battery level reported in the most recent access-log entry."""

    _attr_has_entity_name = True
    _attr_translation_key = "battery"
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, coordinator: IseoLogCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = (
            f"{entry.data[CONF_ADDRESS].replace(':', '').lower()}_battery"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
        )

    @property
    def native_value(self) -> int | None:
        """Return battery percentage."""
        entry: LogEntry | None = self.coordinator.data
        return battery_enum_to_pct(entry.battery) if entry is not None else None
