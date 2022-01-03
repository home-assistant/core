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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util.unit_system import UnitSystem

from . import (
    DOMAIN as BMW_DOMAIN,
    BMWConnectedDriveAccount,
    BMWConnectedDriveBaseEntity,
)
from .const import CONF_ACCOUNT, DATA_ENTRIES, UNIT_MAP

_LOGGER = logging.getLogger(__name__)


@dataclass
class BMWSensorEntityDescription(SensorEntityDescription):
    """Describes BMW sensor entity."""

    unit_metric: str | None = None
    unit_imperial: str | None = None
    value: Callable = lambda x, y: x


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
        value=lambda x, hass: round(
            hass.config.units.length(x[0], UNIT_MAP.get(x[1], x[1])), 2
        ),
    ),
    "remaining_range_total": BMWSensorEntityDescription(
        key="remaining_range_total",
        icon="mdi:map-marker-distance",
        unit_metric=LENGTH_KILOMETERS,
        unit_imperial=LENGTH_MILES,
        value=lambda x, hass: round(
            hass.config.units.length(x[0], UNIT_MAP.get(x[1], x[1])), 2
        ),
    ),
    "remaining_range_electric": BMWSensorEntityDescription(
        key="remaining_range_electric",
        icon="mdi:map-marker-distance",
        unit_metric=LENGTH_KILOMETERS,
        unit_imperial=LENGTH_MILES,
        value=lambda x, hass: round(
            hass.config.units.length(x[0], UNIT_MAP.get(x[1], x[1])), 2
        ),
    ),
    "remaining_range_fuel": BMWSensorEntityDescription(
        key="remaining_range_fuel",
        icon="mdi:map-marker-distance",
        unit_metric=LENGTH_KILOMETERS,
        unit_imperial=LENGTH_MILES,
        value=lambda x, hass: round(
            hass.config.units.length(x[0], UNIT_MAP.get(x[1], x[1])), 2
        ),
    ),
    "remaining_fuel": BMWSensorEntityDescription(
        key="remaining_fuel",
        icon="mdi:gas-station",
        unit_metric=VOLUME_LITERS,
        unit_imperial=VOLUME_GALLONS,
        value=lambda x, hass: round(
            hass.config.units.volume(x[0], UNIT_MAP.get(x[1], x[1])), 2
        ),
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
    account: BMWConnectedDriveAccount = hass.data[BMW_DOMAIN][DATA_ENTRIES][
        config_entry.entry_id
    ][CONF_ACCOUNT]
    entities: list[BMWConnectedDriveSensor] = []

    for vehicle in account.account.vehicles:
        entities.extend(
            [
                BMWConnectedDriveSensor(account, vehicle, description, unit_system)
                for attribute_name in vehicle.available_attributes
                if (description := SENSOR_TYPES.get(attribute_name))
            ]
        )

    async_add_entities(entities, True)


class BMWConnectedDriveSensor(BMWConnectedDriveBaseEntity, SensorEntity):
    """Representation of a BMW vehicle sensor."""

    entity_description: BMWSensorEntityDescription

    def __init__(
        self,
        account: BMWConnectedDriveAccount,
        vehicle: ConnectedDriveVehicle,
        description: BMWSensorEntityDescription,
        unit_system: UnitSystem,
    ) -> None:
        """Initialize BMW vehicle sensor."""
        super().__init__(account, vehicle)
        self.entity_description = description

        self._attr_name = f"{vehicle.name} {description.key}"
        self._attr_unique_id = f"{vehicle.vin}-{description.key}"

        if unit_system.name == CONF_UNIT_SYSTEM_IMPERIAL:
            self._attr_native_unit_of_measurement = description.unit_imperial
        else:
            self._attr_native_unit_of_measurement = description.unit_metric

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        state = getattr(self._vehicle.status, self.entity_description.key)
        return cast(StateType, self.entity_description.value(state, self.hass))
