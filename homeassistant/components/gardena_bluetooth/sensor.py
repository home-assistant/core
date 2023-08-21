"""Support for switch entities."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from gardena_bluetooth.const import Battery, Valve
from gardena_bluetooth.parse import Characteristic

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.util.dt as dt_util

from .const import DOMAIN
from .coordinator import (
    Coordinator,
    GardenaBluetoothDescriptorEntity,
    GardenaBluetoothEntity,
)


@dataclass
class GardenaBluetoothSensorEntityDescription(SensorEntityDescription):
    """Description of entity."""

    char: Characteristic = field(default_factory=lambda: Characteristic(""))


DESCRIPTIONS = (
    GardenaBluetoothSensorEntityDescription(
        key=Valve.activation_reason.uuid,
        translation_key="activation_reason",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        char=Valve.activation_reason,
    ),
    GardenaBluetoothSensorEntityDescription(
        key=Battery.battery_level.uuid,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
        char=Battery.battery_level,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Gardena Bluetooth sensor based on a config entry."""
    coordinator: Coordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[GardenaBluetoothEntity] = [
        GardenaBluetoothSensor(coordinator, description)
        for description in DESCRIPTIONS
        if description.key in coordinator.characteristics
    ]
    if Valve.remaining_open_time.uuid in coordinator.characteristics:
        entities.append(GardenaBluetoothRemainSensor(coordinator))
    async_add_entities(entities)


class GardenaBluetoothSensor(GardenaBluetoothDescriptorEntity, SensorEntity):
    """Representation of a sensor."""

    entity_description: GardenaBluetoothSensorEntityDescription

    def _handle_coordinator_update(self) -> None:
        value = self.coordinator.get_cached(self.entity_description.char)
        if isinstance(value, datetime):
            value = value.replace(
                tzinfo=dt_util.get_time_zone(self.hass.config.time_zone)
            )
        self._attr_native_value = value
        super()._handle_coordinator_update()


class GardenaBluetoothRemainSensor(GardenaBluetoothEntity, SensorEntity):
    """Representation of a sensor."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_native_value: datetime | None = None
    _attr_translation_key = "remaining_open_timestamp"

    def __init__(
        self,
        coordinator: Coordinator,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, {Valve.remaining_open_time.uuid})
        self._attr_unique_id = f"{coordinator.address}-remaining_open_timestamp"

    def _handle_coordinator_update(self) -> None:
        value = self.coordinator.get_cached(Valve.remaining_open_time)
        if not value:
            self._attr_native_value = None
            super()._handle_coordinator_update()
            return

        time = datetime.now(timezone.utc) + timedelta(seconds=value)
        if not self._attr_native_value:
            self._attr_native_value = time
            super()._handle_coordinator_update()
            return

        error = time - self._attr_native_value
        if abs(error.total_seconds()) > 10:
            self._attr_native_value = time
            super()._handle_coordinator_update()
            return
