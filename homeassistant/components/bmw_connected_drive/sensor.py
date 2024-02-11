"""Support for reading vehicle status from MyBMW portal."""
from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import cast

from bimmer_connected.models import ValueWithUnit
from bimmer_connected.vehicle import MyBMWVehicle

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfLength,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import BMWBaseEntity
from .const import DOMAIN
from .coordinator import BMWDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class BMWSensorEntityDescription(SensorEntityDescription):
    """Describes BMW sensor entity."""

    key_class: str | None = None


SENSOR_TYPES: dict[str, BMWSensorEntityDescription] = {
    "ac_current_limit": BMWSensorEntityDescription(
        key="ac_current_limit",
        translation_key="ac_current_limit",
        key_class="charging_profile",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        icon="mdi:current-ac",
        entity_registry_enabled_default=False,
    ),
    "charging_start_time": BMWSensorEntityDescription(
        key="charging_start_time",
        translation_key="charging_start_time",
        key_class="fuel_and_battery",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=False,
    ),
    "charging_end_time": BMWSensorEntityDescription(
        key="charging_end_time",
        translation_key="charging_end_time",
        key_class="fuel_and_battery",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    "charging_status": BMWSensorEntityDescription(
        key="charging_status",
        translation_key="charging_status",
        key_class="fuel_and_battery",
        icon="mdi:ev-station",
    ),
    "charging_target": BMWSensorEntityDescription(
        key="charging_target",
        translation_key="charging_target",
        key_class="fuel_and_battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:battery-charging-high",
    ),
    "remaining_battery_percent": BMWSensorEntityDescription(
        key="remaining_battery_percent",
        translation_key="remaining_battery_percent",
        key_class="fuel_and_battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "mileage": BMWSensorEntityDescription(
        key="mileage",
        translation_key="mileage",
        icon="mdi:speedometer",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    "remaining_range_total": BMWSensorEntityDescription(
        key="remaining_range_total",
        translation_key="remaining_range_total",
        key_class="fuel_and_battery",
        icon="mdi:map-marker-distance",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "remaining_range_electric": BMWSensorEntityDescription(
        key="remaining_range_electric",
        translation_key="remaining_range_electric",
        key_class="fuel_and_battery",
        icon="mdi:map-marker-distance",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "remaining_range_fuel": BMWSensorEntityDescription(
        key="remaining_range_fuel",
        translation_key="remaining_range_fuel",
        key_class="fuel_and_battery",
        icon="mdi:map-marker-distance",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "remaining_fuel": BMWSensorEntityDescription(
        key="remaining_fuel",
        translation_key="remaining_fuel",
        key_class="fuel_and_battery",
        icon="mdi:gas-station",
        device_class=SensorDeviceClass.VOLUME_STORAGE,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "remaining_fuel_percent": BMWSensorEntityDescription(
        key="remaining_fuel_percent",
        translation_key="remaining_fuel_percent",
        key_class="fuel_and_battery",
        icon="mdi:gas-station",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the MyBMW sensors from config entry."""
    coordinator: BMWDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities: list[BMWSensor] = []

    for vehicle in coordinator.account.vehicles:
        entities.extend(
            [
                BMWSensor(coordinator, vehicle, description)
                for attribute_name in vehicle.available_attributes
                if (description := SENSOR_TYPES.get(attribute_name))
            ]
        )

    async_add_entities(entities)


class BMWSensor(BMWBaseEntity, SensorEntity):
    """Representation of a BMW vehicle sensor."""

    entity_description: BMWSensorEntityDescription

    def __init__(
        self,
        coordinator: BMWDataUpdateCoordinator,
        vehicle: MyBMWVehicle,
        description: BMWSensorEntityDescription,
    ) -> None:
        """Initialize BMW vehicle sensor."""
        super().__init__(coordinator, vehicle)
        self.entity_description = description
        self._attr_unique_id = f"{vehicle.vin}-{description.key}"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        _LOGGER.debug(
            "Updating sensor '%s' of %s", self.entity_description.key, self.vehicle.name
        )
        if self.entity_description.key_class is None:
            state = getattr(self.vehicle, self.entity_description.key)
        else:
            state = getattr(
                getattr(self.vehicle, self.entity_description.key_class),
                self.entity_description.key,
            )
        if isinstance(state, ValueWithUnit):
            state = state.value
        self._attr_native_value = cast(StateType, state)
        super()._handle_coordinator_update()
