"""Support for switch entities."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from gardena_bluetooth.const import Battery, Sensor, Valve
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


@dataclass(frozen=True)
class GardenaBluetoothSensorEntityDescription(SensorEntityDescription):
    """Description of entity."""

    char: Characteristic = field(default_factory=lambda: Characteristic(""))
    connected_state: Characteristic | None = None

    @property
    def context(self) -> set[str]:
        """Context needed for update coordinator."""
        data = {self.char.uuid}
        if self.connected_state:
            data.add(self.connected_state.uuid)
        return data


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
    GardenaBluetoothSensorEntityDescription(
        key=Sensor.battery_level.uuid,
        translation_key="sensor_battery_level",
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
        char=Sensor.battery_level,
        connected_state=Sensor.connected_state,
    ),
    GardenaBluetoothSensorEntityDescription(
        key=Sensor.value.uuid,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.MOISTURE,
        native_unit_of_measurement=PERCENTAGE,
        char=Sensor.value,
        connected_state=Sensor.connected_state,
    ),
    GardenaBluetoothSensorEntityDescription(
        key=Sensor.type.uuid,
        translation_key="sensor_type",
        entity_category=EntityCategory.DIAGNOSTIC,
        char=Sensor.type,
        connected_state=Sensor.connected_state,
    ),
    GardenaBluetoothSensorEntityDescription(
        key=Sensor.measurement_timestamp.uuid,
        translation_key="sensor_measurement_timestamp",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        char=Sensor.measurement_timestamp,
        connected_state=Sensor.connected_state,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Gardena Bluetooth sensor based on a config entry."""
    coordinator: Coordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[GardenaBluetoothEntity] = [
        GardenaBluetoothSensor(coordinator, description, description.context)
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

        if char := self.entity_description.connected_state:
            self._attr_available = bool(self.coordinator.get_cached(char))
        else:
            self._attr_available = True

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

        time = datetime.now(UTC) + timedelta(seconds=value)
        if not self._attr_native_value:
            self._attr_native_value = time
            super()._handle_coordinator_update()
            return

        error = time - self._attr_native_value
        if abs(error.total_seconds()) > 10:
            self._attr_native_value = time
            super()._handle_coordinator_update()
            return

    @property
    def available(self) -> bool:
        """Sensor only available when open."""
        return super().available and self._attr_native_value is not None
