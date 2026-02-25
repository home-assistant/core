"""Sensor platform for Kiosker."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import KioskerConfigEntry
from .coordinator import KioskerDataUpdateCoordinator
from .entity import KioskerEntity

# Limit concurrent updates to prevent overwhelming the API
PARALLEL_UPDATES = 3


@dataclass(frozen=True)
class KioskerSensorEntityDescription(SensorEntityDescription):
    """Kiosker sensor description."""

    value_fn: Callable[[Any], StateType | datetime] | None = None


def parse_datetime(value: Any) -> datetime | None:
    """Parse datetime from various formats."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except ValueError, TypeError:
        return None


SENSORS: tuple[KioskerSensorEntityDescription, ...] = (
    KioskerSensorEntityDescription(
        key="batteryLevel",
        translation_key="battery_level",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda x: x.battery_level,
    ),
    KioskerSensorEntityDescription(
        key="batteryState",
        translation_key="battery_state",
        value_fn=lambda x: x.battery_state,
    ),
    KioskerSensorEntityDescription(
        key="lastInteraction",
        translation_key="last_interaction",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda x: parse_datetime(x.last_interaction),
    ),
    KioskerSensorEntityDescription(
        key="lastMotion",
        translation_key="last_motion",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda x: parse_datetime(x.last_motion),
    ),
    KioskerSensorEntityDescription(
        key="ambientLight",
        translation_key="ambient_light",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda x: x.ambient_light,
    ),
    KioskerSensorEntityDescription(
        key="lastUpdate",
        translation_key="last_update",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda x: parse_datetime(x.last_update),
    ),
    KioskerSensorEntityDescription(
        key="blackoutState",
        translation_key="blackout_state",
        icon="mdi:monitor-off",
        value_fn=lambda x: "active" if x is not None and x.visible else "inactive",
    ),
    KioskerSensorEntityDescription(
        key="screensaverVisibility",
        translation_key="screensaver_visibility",
        value_fn=lambda x: (
            "visible" if hasattr(x, "visible") and x.visible else "hidden"
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KioskerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Kiosker sensors based on a config entry."""
    coordinator = entry.runtime_data

    # Create all sensors - they will handle missing data gracefully
    async_add_entities(
        KioskerSensor(coordinator, description) for description in SENSORS
    )


class KioskerSensor(KioskerEntity, SensorEntity):
    """Representation of a Kiosker sensor."""

    entity_description: KioskerSensorEntityDescription

    def __init__(
        self,
        coordinator: KioskerDataUpdateCoordinator,
        description: KioskerSensorEntityDescription,
    ) -> None:
        """Initialize the sensor entity."""
        super().__init__(coordinator, description)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        value = None

        if self.entity_description.key == "blackoutState":
            # Special handling for blackout state
            blackout_data = (
                self.coordinator.data.blackout if self.coordinator.data else None
            )
            if self.entity_description.value_fn:
                value = self.entity_description.value_fn(blackout_data)

            # Add all blackout data as extra attributes
            if blackout_data is not None:
                self._attr_extra_state_attributes = {
                    key: getattr(blackout_data, key)
                    for key in blackout_data.__dataclass_fields__
                    if not key.startswith("_")
                }
            else:
                self._attr_extra_state_attributes = {}
        elif self.entity_description.key == "screensaverVisibility":
            # Special handling for screensaver visibility
            screensaver_data = (
                self.coordinator.data.screensaver if self.coordinator.data else None
            )
            if self.entity_description.value_fn:
                value = self.entity_description.value_fn(screensaver_data)
            # Clear extra attributes for screensaver sensor
            self._attr_extra_state_attributes = {}
        elif self.coordinator.data:
            # Handle status-based sensors
            status = self.coordinator.data.status
            if self.entity_description.value_fn:
                value = self.entity_description.value_fn(status)
            # Clear extra attributes for non-blackout sensors
            self._attr_extra_state_attributes = {}
        else:
            # Clear extra attributes if no data
            self._attr_extra_state_attributes = {}

        self._attr_native_value = value
        self.async_write_ha_state()
