"""Support for reading vehicle status from BMW connected drive portal."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import cast

from bimmer_connected.vehicle import ConnectedDriveVehicle

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_UNIT_SYSTEM_IMPERIAL,
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

from . import BMWConnectedDriveBaseEntity
from .const import DOMAIN, UNIT_MAP
from .coordinator import BMWDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass
class BMWSensorEntityDescription(SensorEntityDescription):
    """Describes BMW sensor entity."""

    unit_metric: str | None = None
    unit_imperial: str | None = None
    value: Callable = lambda x, y: x


def convert_and_round(
    state: tuple,
    converter: Callable[[float | None, str], float],
    precision: int,
) -> float | None:
    """Safely convert and round a value from a Tuple[value, unit]."""
    if state[0] is None:
        return None
    return round(converter(state[0], UNIT_MAP.get(state[1], state[1])), precision)


SENSOR_TYPES: dict[str, BMWSensorEntityDescription] = {
    # --- Generic ---
    "charging_start_time": BMWSensorEntityDescription(
        key="charging_start_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=False,
    ),
    "charging_end_time": BMWSensorEntityDescription(
        key="charging_end_time",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    "charging_time_label": BMWSensorEntityDescription(
        key="charging_time_label",
        entity_registry_enabled_default=False,
    ),
    "charging_status": BMWSensorEntityDescription(
        key="charging_status",
        icon="mdi:ev-station",
        value=lambda x, y: x.value,
    ),
    "charging_level_hv": BMWSensorEntityDescription(
        key="charging_level_hv",
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
        icon="mdi:map-marker-distance",
        unit_metric=LENGTH_KILOMETERS,
        unit_imperial=LENGTH_MILES,
        value=lambda x, hass: convert_and_round(x, hass.config.units.length, 2),
    ),
    "remaining_range_electric": BMWSensorEntityDescription(
        key="remaining_range_electric",
        icon="mdi:map-marker-distance",
        unit_metric=LENGTH_KILOMETERS,
        unit_imperial=LENGTH_MILES,
        value=lambda x, hass: convert_and_round(x, hass.config.units.length, 2),
    ),
    "remaining_range_fuel": BMWSensorEntityDescription(
        key="remaining_range_fuel",
        icon="mdi:map-marker-distance",
        unit_metric=LENGTH_KILOMETERS,
        unit_imperial=LENGTH_MILES,
        value=lambda x, hass: convert_and_round(x, hass.config.units.length, 2),
    ),
    "remaining_fuel": BMWSensorEntityDescription(
        key="remaining_fuel",
        icon="mdi:gas-station",
        unit_metric=VOLUME_LITERS,
        unit_imperial=VOLUME_GALLONS,
        value=lambda x, hass: convert_and_round(x, hass.config.units.volume, 2),
    ),
    "fuel_percent": BMWSensorEntityDescription(
        key="fuel_percent",
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
    """Set up the BMW ConnectedDrive sensors from config entry."""
    unit_system = hass.config.units
    coordinator: BMWDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities: list[BMWConnectedDriveSensor] = []

    for vehicle in coordinator.account.vehicles:
        entities.extend(
            [
                BMWConnectedDriveSensor(coordinator, vehicle, description, unit_system)
                for attribute_name in vehicle.available_attributes
                if (description := SENSOR_TYPES.get(attribute_name))
            ]
        )

    async_add_entities(entities)


class BMWConnectedDriveSensor(BMWConnectedDriveBaseEntity, SensorEntity):
    """Representation of a BMW vehicle sensor."""

    entity_description: BMWSensorEntityDescription

    def __init__(
        self,
        coordinator: BMWDataUpdateCoordinator,
        vehicle: ConnectedDriveVehicle,
        description: BMWSensorEntityDescription,
        unit_system: UnitSystem,
    ) -> None:
        """Initialize BMW vehicle sensor."""
        super().__init__(coordinator, vehicle)
        self.entity_description = description

        self._attr_name = f"{vehicle.name} {description.key}"
        self._attr_unique_id = f"{vehicle.vin}-{description.key}"

        if unit_system.name == CONF_UNIT_SYSTEM_IMPERIAL:
            self._attr_native_unit_of_measurement = description.unit_imperial
        else:
            self._attr_native_unit_of_measurement = description.unit_metric

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        _LOGGER.debug(
            "Updating sensor '%s' of %s", self.entity_description.key, self.vehicle.name
        )
        state = getattr(self.vehicle.status, self.entity_description.key)
        self._attr_native_value = cast(
            StateType, self.entity_description.value(state, self.hass)
        )
        super()._handle_coordinator_update()
