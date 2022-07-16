"""Support for reading vehicle status from MyBMW portal."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import cast

from bimmer_connected.models import ValueWithUnit
from bimmer_connected.vehicle import MyBMWVehicle

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    LENGTH_KILOMETERS,
    LENGTH_MILES,
    PERCENTAGE,
    VOLUME_GALLONS,
    VOLUME_LITERS,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util.unit_system import UnitSystem

from . import BMWBaseEntity
from .const import DOMAIN, UNIT_MAP
from .coordinator import BMWDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass
class BMWSensorEntityDescription(SensorEntityDescription):
    """Describes BMW sensor entity."""

    key_class: str | None = None
    unit_metric: str | None = None
    unit_imperial: str | None = None
    value: Callable = lambda x, y: x


def convert_and_round(
    state: ValueWithUnit,
    converter: Callable[[float | None, str], float],
    precision: int,
) -> float | None:
    """Safely convert and round a value from ValueWithUnit."""
    if state.value and state.unit:
        return round(
            converter(state.value, UNIT_MAP.get(state.unit, state.unit)), precision
        )
    if state.value:
        return state.value
    return None


SENSOR_TYPES: dict[str, BMWSensorEntityDescription] = {
    # --- Generic ---
    "charging_start_time": BMWSensorEntityDescription(
        key="charging_start_time",
        key_class="fuel_and_battery",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=False,
    ),
    "charging_end_time": BMWSensorEntityDescription(
        key="charging_end_time",
        key_class="fuel_and_battery",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    "charging_time_label": BMWSensorEntityDescription(
        key="charging_time_label",
        key_class="fuel_and_battery",
        entity_registry_enabled_default=False,
    ),
    "charging_status": BMWSensorEntityDescription(
        key="charging_status",
        key_class="fuel_and_battery",
        icon="mdi:ev-station",
        value=lambda x, y: x.value,
    ),
    "remaining_battery_percent": BMWSensorEntityDescription(
        key="remaining_battery_percent",
        key_class="fuel_and_battery",
        unit_metric=PERCENTAGE,
        unit_imperial=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
    ),
    # --- Specific ---
    "mileage": BMWSensorEntityDescription(
        key="mileage",
        icon="mdi:speedometer",
        unit_metric=LENGTH_KILOMETERS,
        unit_imperial=LENGTH_MILES,
        value=lambda x, hass: convert_and_round(x, hass.config.units.length, 2),
    ),
    "remaining_range_total": BMWSensorEntityDescription(
        key="remaining_range_total",
        key_class="fuel_and_battery",
        icon="mdi:map-marker-distance",
        unit_metric=LENGTH_KILOMETERS,
        unit_imperial=LENGTH_MILES,
        value=lambda x, hass: convert_and_round(x, hass.config.units.length, 2),
    ),
    "remaining_range_electric": BMWSensorEntityDescription(
        key="remaining_range_electric",
        key_class="fuel_and_battery",
        icon="mdi:map-marker-distance",
        unit_metric=LENGTH_KILOMETERS,
        unit_imperial=LENGTH_MILES,
        value=lambda x, hass: convert_and_round(x, hass.config.units.length, 2),
    ),
    "remaining_range_fuel": BMWSensorEntityDescription(
        key="remaining_range_fuel",
        key_class="fuel_and_battery",
        icon="mdi:map-marker-distance",
        unit_metric=LENGTH_KILOMETERS,
        unit_imperial=LENGTH_MILES,
        value=lambda x, hass: convert_and_round(x, hass.config.units.length, 2),
    ),
    "remaining_fuel": BMWSensorEntityDescription(
        key="remaining_fuel",
        key_class="fuel_and_battery",
        icon="mdi:gas-station",
        unit_metric=VOLUME_LITERS,
        unit_imperial=VOLUME_GALLONS,
        value=lambda x, hass: convert_and_round(x, hass.config.units.volume, 2),
    ),
    "remaining_fuel_percent": BMWSensorEntityDescription(
        key="remaining_fuel_percent",
        key_class="fuel_and_battery",
        icon="mdi:gas-station",
        unit_metric=PERCENTAGE,
        unit_imperial=PERCENTAGE,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the MyBMW sensors from config entry."""
    unit_system = hass.config.units
    coordinator: BMWDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities: list[BMWSensor] = []

    for vehicle in coordinator.account.vehicles:
        entities.extend(
            [
                BMWSensor(coordinator, vehicle, description, unit_system)
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
        unit_system: UnitSystem,
    ) -> None:
        """Initialize BMW vehicle sensor."""
        super().__init__(coordinator, vehicle)
        self.entity_description = description

        self._attr_name = f"{vehicle.name} {description.key}"
        self._attr_unique_id = f"{vehicle.vin}-{description.key}"

        # Force metric system as BMW API apparently only returns metric values now
        self._attr_native_unit_of_measurement = description.unit_metric

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
        self._attr_native_value = cast(
            StateType, self.entity_description.value(state, self.hass)
        )
        super()._handle_coordinator_update()
