"""Support for Renault binary sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from renault_api.kamereon.enums import ChargeState, PlugState
from renault_api.kamereon.models import (
    KamereonVehicleBatteryStatusData,
    KamereonVehicleDataAttributes,
    KamereonVehicleHvacStatusData,
    KamereonVehicleLockStatusData,
)

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import RenaultConfigEntry
from .entity import RenaultDataEntity, RenaultDataEntityDescription

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0

_PLUG_FROM_CHARGE_STATUS: set[ChargeState] = {
    ChargeState.CHARGE_IN_PROGRESS,
    ChargeState.WAITING_FOR_CURRENT_CHARGE,
    ChargeState.CHARGE_ENDED,
    ChargeState.V2G_CHARGING_NORMAL,
    ChargeState.V2G_CHARGING_WAITING,
    ChargeState.V2G_DISCHARGING,
    ChargeState.WAITING_FOR_A_PLANNED_CHARGE,
}


@dataclass(frozen=True, kw_only=True)
class RenaultBinarySensorEntityDescription[T: KamereonVehicleDataAttributes](
    BinarySensorEntityDescription,
    RenaultDataEntityDescription,
):
    """Class describing Renault binary sensor entities."""

    value_lambda: Callable[[RenaultBinarySensor[T]], bool | None]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RenaultConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Renault entities from config entry."""
    entities: list[RenaultBinarySensor] = [
        RenaultBinarySensor(vehicle, description)
        for vehicle in config_entry.runtime_data.vehicles.values()
        for description in BINARY_SENSOR_TYPES
        if description.coordinator in vehicle.coordinators
    ]
    async_add_entities(entities)


class RenaultBinarySensor[T: KamereonVehicleDataAttributes](
    RenaultDataEntity[T], BinarySensorEntity
):
    """Mixin for binary sensor specific attributes."""

    entity_description: RenaultBinarySensorEntityDescription[T]

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        return self.entity_description.value_lambda(self)


def _plugged_in_value_lambda(
    self: RenaultBinarySensor[KamereonVehicleBatteryStatusData],
) -> bool | None:
    """Return true if the vehicle is plugged in."""
    if (plug_status := self.coordinator.data.get_plug_status()) is not None:
        return plug_status == PlugState.PLUGGED

    if (
        charging_status := self.coordinator.data.get_charging_status()
    ) is not None and charging_status in _PLUG_FROM_CHARGE_STATUS:
        return True

    return None


BINARY_SENSOR_TYPES: tuple[RenaultBinarySensorEntityDescription, ...] = (
    RenaultBinarySensorEntityDescription[KamereonVehicleBatteryStatusData](
        key="plugged_in",
        coordinator="battery",
        device_class=BinarySensorDeviceClass.PLUG,
        value_lambda=_plugged_in_value_lambda,
    ),
    RenaultBinarySensorEntityDescription[KamereonVehicleBatteryStatusData](
        key="charging",
        coordinator="battery",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        value_lambda=lambda e: (
            e.coordinator.data.chargingStatus == ChargeState.CHARGE_IN_PROGRESS.value
            if e.coordinator.data.chargingStatus is not None
            else None
        ),
    ),
    RenaultBinarySensorEntityDescription[KamereonVehicleHvacStatusData](
        key="hvac_status",
        coordinator="hvac_status",
        translation_key="hvac_status",
        value_lambda=lambda e: (
            e.coordinator.data.hvacStatus == "on"
            if e.coordinator.data.hvacStatus is not None
            else None
        ),
    ),
    RenaultBinarySensorEntityDescription[KamereonVehicleLockStatusData](
        key="lock_status",
        coordinator="lock_status",
        # lock: on means open (unlocked), off means closed (locked)
        device_class=BinarySensorDeviceClass.LOCK,
        value_lambda=lambda e: (
            e.coordinator.data.lockStatus == "unlocked"
            if e.coordinator.data.lockStatus is not None
            else None
        ),
    ),
    RenaultBinarySensorEntityDescription[KamereonVehicleLockStatusData](
        key="hatch_status",
        coordinator="lock_status",
        # On means open, Off means closed
        device_class=BinarySensorDeviceClass.DOOR,
        translation_key="hatch_status",
        value_lambda=lambda e: (
            e.coordinator.data.hatchStatus == "open"
            if e.coordinator.data.hatchStatus is not None
            else None
        ),
    ),
    RenaultBinarySensorEntityDescription[KamereonVehicleLockStatusData](
        key="rear_left_door_status",
        coordinator="lock_status",
        # On means open, Off means closed
        device_class=BinarySensorDeviceClass.DOOR,
        translation_key="rear_left_door_status",
        value_lambda=lambda e: (
            e.coordinator.data.doorStatusRearLeft == "open"
            if e.coordinator.data.doorStatusRearLeft is not None
            else None
        ),
    ),
    RenaultBinarySensorEntityDescription[KamereonVehicleLockStatusData](
        key="rear_right_door_status",
        coordinator="lock_status",
        # On means open, Off means closed
        device_class=BinarySensorDeviceClass.DOOR,
        translation_key="rear_right_door_status",
        value_lambda=lambda e: (
            e.coordinator.data.doorStatusRearRight == "open"
            if e.coordinator.data.doorStatusRearRight is not None
            else None
        ),
    ),
    RenaultBinarySensorEntityDescription[KamereonVehicleLockStatusData](
        key="driver_door_status",
        coordinator="lock_status",
        # On means open, Off means closed
        device_class=BinarySensorDeviceClass.DOOR,
        translation_key="driver_door_status",
        value_lambda=lambda e: (
            e.coordinator.data.doorStatusDriver == "open"
            if e.coordinator.data.doorStatusDriver is not None
            else None
        ),
    ),
    RenaultBinarySensorEntityDescription[KamereonVehicleLockStatusData](
        key="passenger_door_status",
        coordinator="lock_status",
        # On means open, Off means closed
        device_class=BinarySensorDeviceClass.DOOR,
        translation_key="passenger_door_status",
        value_lambda=lambda e: (
            e.coordinator.data.doorStatusPassenger == "open"
            if e.coordinator.data.doorStatusPassenger is not None
            else None
        ),
    ),
)
