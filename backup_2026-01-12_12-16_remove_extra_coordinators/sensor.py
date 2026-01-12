"""Sensor platform for Garmin Connect."""

from __future__ import annotations

import datetime
import logging
from typing import Any

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import GarminConnectConfigEntry
from .const import DOMAIN
from .coordinator import BaseGarminCoordinator, GearCoordinator
from .sensor_descriptions import (
    COORDINATOR_SENSOR_MAP,
    CoordinatorType,
    GarminConnectSensorEntityDescription,
)

_LOGGER = logging.getLogger(__name__)

# Limit parallel updates to prevent API rate limiting
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GarminConnectConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Garmin Connect sensors."""
    coordinators = entry.runtime_data

    entities: list[GarminConnectSensor | GarminConnectGearSensor] = []

    # Map coordinator types to coordinator instances
    coordinator_map: dict[CoordinatorType, BaseGarminCoordinator] = {
        CoordinatorType.CORE: coordinators.core,
        CoordinatorType.ACTIVITY: coordinators.activity,
        CoordinatorType.TRAINING: coordinators.training,
        CoordinatorType.BODY: coordinators.body,
        CoordinatorType.GOALS: coordinators.goals,
        CoordinatorType.GEAR: coordinators.gear,
        CoordinatorType.BLOOD_PRESSURE: coordinators.blood_pressure,
        CoordinatorType.MENSTRUAL: coordinators.menstrual,
    }

    # Add sensors from each coordinator's sensor group
    for coord_type, descriptions in COORDINATOR_SENSOR_MAP.items():
        coordinator = coordinator_map[coord_type]
        for description in descriptions:
            _LOGGER.debug(
                "Registering entity: %s (%s) -> %s",
                description.key,
                description.translation_key,
                coord_type,
            )
            entities.append(
                GarminConnectSensor(coordinator, description, entry.entry_id)
            )

    # Add dynamic gear sensors (from gear coordinator)
    gear_data = coordinators.gear.data or {}
    gear_stats = gear_data.get("gearStats", [])
    for gear_stat in gear_stats:
        gear_name = gear_stat.get("displayName") or gear_stat.get("gearName", "Unknown")
        gear_uuid = gear_stat.get("uuid") or gear_stat.get("gearUuid", "")
        if gear_uuid:
            entities.append(
                GarminConnectGearSensor(
                    coordinators.gear,
                    gear_uuid=gear_uuid,
                    gear_name=gear_name,
                    entry_id=entry.entry_id,
                )
            )

    async_add_entities(entities)


class GarminConnectSensor(
    CoordinatorEntity[BaseGarminCoordinator], RestoreSensor
):
    """Representation of a Garmin Connect sensor."""

    entity_description: GarminConnectSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BaseGarminCoordinator,
        description: GarminConnectSensorEntityDescription,
        entry_id: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Garmin Connect",
            manufacturer="Garmin",
            entry_type=DeviceEntryType.SERVICE,
        )
        self._last_known_value: str | int | float | datetime.datetime | None = None

    async def async_added_to_hass(self) -> None:
        """Restore last known value when added to hass."""
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            if last_state.state not in ("unknown", "unavailable"):
                self._last_known_value = last_state.state

    @property
    def native_value(self) -> str | int | float | datetime.datetime | None:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            # Only return last known value if preserve_value is enabled
            if self.entity_description.preserve_value:
                return self._last_known_value
            return None

        # Use custom value function if provided in description
        if self.entity_description.value_fn:
            value = self.entity_description.value_fn(self.coordinator.data)
        else:
            value = self.coordinator.data.get(self.entity_description.key)

        if value is None:
            # Return last known value if preserve_value enabled (e.g., weight at midnight)
            if self.entity_description.preserve_value:
                return self._last_known_value
            return None

        # Handle timestamp device class
        if self.entity_description.device_class == SensorDeviceClass.TIMESTAMP:
            if value:
                try:
                    # Parse ISO format timestamp and set to UTC (GMT)
                    parsed = datetime.datetime.fromisoformat(value)
                    # If naive, assume UTC since Garmin returns GMT timestamps
                    if parsed.tzinfo is None:
                        value = parsed.replace(tzinfo=datetime.UTC)
                    else:
                        value = parsed
                except (ValueError, TypeError):
                    _LOGGER.debug("Could not parse timestamp: %s", value)
                    value = None

        # Preserve int types, only round floats
        if isinstance(value, int):
            self._last_known_value = value
            return value
        if isinstance(value, float):
            # Round floats to 1 decimal place, but return int if it's a whole number
            rounded = round(value, 1)
            if rounded == int(rounded):
                self._last_known_value = int(rounded)
                return int(rounded)
            self._last_known_value = rounded
            return rounded
        # For strings and datetime objects, return as-is
        if isinstance(value, (str, datetime.datetime)):
            self._last_known_value = value
            return value
        # Fallback: return as string
        self._last_known_value = str(value)
        return str(value)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        if not self.coordinator.data:
            return {}

        # Use custom attributes function if provided in description
        if self.entity_description.attributes_fn:
            return self.entity_description.attributes_fn(self.coordinator.data)

        # Default: no extra attributes (last_synced has its own sensor)
        return {}

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        # Entity is available if coordinator has data
        # Individual sensors will show "Unknown" if their value is None
        return bool(super().available and self.coordinator.data)


class GarminConnectGearSensor(CoordinatorEntity[GearCoordinator], SensorEntity):
    """Representation of a dynamic Garmin Connect gear sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GearCoordinator,
        gear_uuid: str,
        gear_name: str,
        entry_id: str,
    ) -> None:
        """Initialize the gear sensor."""
        super().__init__(coordinator)
        self._gear_uuid = gear_uuid
        self._gear_name = gear_name
        self._attr_native_unit_of_measurement = "m"
        self._attr_device_class = SensorDeviceClass.DISTANCE
        self._attr_icon = "mdi:shoe-print"

        # Create a clean key from gear name (lowercase, underscores)
        clean_name = gear_name.lower().replace(" ", "_").replace("-", "_")
        self._attr_unique_id = f"{entry_id}_gear_{clean_name}"
        self._attr_translation_key = "gear"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Garmin Connect",
            manufacturer="Garmin",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"{self._gear_name}"

    @property
    def native_value(self) -> float | int | None:
        """Return the state of the sensor (total distance in meters)."""
        if not self.coordinator.data:
            return None

        gear_stats = self.coordinator.data.get("gearStats", [])
        for gear_stat in gear_stats:
            if (gear_stat.get("uuid") or gear_stat.get("gearUuid")) == self._gear_uuid:
                value = gear_stat.get("totalDistance")
                if isinstance(value, (int, float)):
                    if isinstance(value, float):
                        return round(value, 1)
                    return value
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        if not self.coordinator.data:
            return {}

        gear_stats = self.coordinator.data.get("gearStats", [])
        for gear_stat in gear_stats:
            if (gear_stat.get("uuid") or gear_stat.get("gearUuid")) == self._gear_uuid:
                return {
                    "gear_uuid": self._gear_uuid,
                    "total_activities": gear_stat.get("totalActivities"),
                    "date_begin": gear_stat.get("dateBegin"),
                    "date_end": gear_stat.get("dateEnd"),
                    "gear_make_name": gear_stat.get("gearMakeName"),
                    "gear_model_name": gear_stat.get("gearModelName"),
                    "gear_status_name": gear_stat.get("gearStatusName"),
                    "custom_make_model": gear_stat.get("customMakeModel"),
                    "maximum_meters": gear_stat.get("maximumMeters"),
                    "default_for_activity": gear_stat.get("defaultForActivity", []),
                }
        return {}

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return bool(super().available and self.coordinator.data)
