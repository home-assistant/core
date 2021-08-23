"""Support for Renault binary sensors."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, Optional, TypeVar

from renault_api.kamereon.enums import ChargeState, PlugState
from renault_api.kamereon.models import KamereonVehicleBatteryStatusData

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_BATTERY_CHARGING,
    DEVICE_CLASS_PLUG,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN
from .renault_entities import RenaultDataEntity, RenaultEntityDescription
from .renault_hub import RenaultHub


@dataclass
class RenaultBinarySensorEntityDescription(
    BinarySensorEntityDescription, RenaultEntityDescription
):
    """Class describing Renault binary sensor entities."""

    on_value: StateType = None


BINARY_SENSOR_TYPES: tuple[RenaultBinarySensorEntityDescription, ...] = (
    RenaultBinarySensorEntityDescription(
        key="plugged_in",
        coordinator="battery",
        data_key="plugStatus",
        device_class=DEVICE_CLASS_PLUG,
        entity_class="RenaultBatteryBinarySensor",
        name="Plugged In",
        on_value=PlugState.PLUGGED.value,
    ),
    RenaultBinarySensorEntityDescription(
        key="charging",
        coordinator="battery",
        data_key="chargingStatus",
        device_class=DEVICE_CLASS_BATTERY_CHARGING,
        entity_class="RenaultBatteryBinarySensor",
        name="Charging",
        on_value=ChargeState.CHARGE_IN_PROGRESS.value,
    ),
)

T = TypeVar("T")


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Renault entities from config entry."""
    proxy: RenaultHub = hass.data[DOMAIN][config_entry.entry_id]
    entities: list[BinarySensorEntity] = []
    for vehicle in proxy.vehicles.values():
        for description in BINARY_SENSOR_TYPES:
            if description.coordinator in vehicle.coordinators:
                entity_class = globals()[description.entity_class]
                entities.append(entity_class(vehicle, description))
    async_add_entities(entities)


class RenaultBinarySensor(
    Generic[T], RenaultDataEntity[Optional[T]], BinarySensorEntity
):
    """Mixin for binary sensor specific attributes."""

    entity_description: RenaultBinarySensorEntityDescription


class RenaultBatteryBinarySensor(RenaultBinarySensor[KamereonVehicleBatteryStatusData]):
    """Renault battery binary sensor."""

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.entity_description.on_value == self.data
