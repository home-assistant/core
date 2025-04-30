"""Support for Renault binary sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from renault_api.kamereon.enums import ChargeState, PlugState
from renault_api.kamereon.models import KamereonVehicleBatteryStatusData

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import RenaultConfigEntry
from .entity import RenaultDataEntity, RenaultDataEntityDescription

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class RenaultBinarySensorEntityDescription(
    BinarySensorEntityDescription,
    RenaultDataEntityDescription,
):
    """Class describing Renault binary sensor entities."""

    on_key: str | None = None
    on_value: StateType | None = None
    value_lambda: Callable[[RenaultBinarySensor], bool | None] | None = None


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


class RenaultBinarySensor(
    RenaultDataEntity[KamereonVehicleBatteryStatusData], BinarySensorEntity
):
    """Mixin for binary sensor specific attributes."""

    entity_description: RenaultBinarySensorEntityDescription

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""

        if self.entity_description.value_lambda is not None:
            return self.entity_description.value_lambda(self)
        if self.entity_description.on_key is None:
            raise NotImplementedError("Either value_lambda or on_key must be set")
        if (data := self._get_data_attr(self.entity_description.on_key)) is None:
            return None

        return data == self.entity_description.on_value


def _plugged_in_value_lambda(self: RenaultBinarySensor) -> bool | None:
    """Return true if the vehicle is plugged in."""

    data = self.coordinator.data
    plug_status = data.get_plug_status() if data else None

    if plug_status is None:
        charging_status = data.get_charging_status() if data else None
        if charging_status is not None and charging_status in [
            ChargeState.CHARGE_IN_PROGRESS,
            ChargeState.WAITING_FOR_CURRENT_CHARGE,
            ChargeState.CHARGE_ENDED,
            ChargeState.V2G_CHARGING_NORMAL,
            ChargeState.V2G_CHARGING_WAITING,
            ChargeState.V2G_DISCHARGING,
            ChargeState.WAITING_FOR_A_PLANNED_CHARGE,
        ]:
            return True
    else:
        return plug_status == PlugState.PLUGGED

    return None


BINARY_SENSOR_TYPES: tuple[RenaultBinarySensorEntityDescription, ...] = tuple(
    [
        RenaultBinarySensorEntityDescription(
            key="plugged_in",
            coordinator="battery",
            device_class=BinarySensorDeviceClass.PLUG,
            value_lambda=_plugged_in_value_lambda,
        ),
        RenaultBinarySensorEntityDescription(
            key="charging",
            coordinator="battery",
            device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
            on_key="chargingStatus",
            on_value=ChargeState.CHARGE_IN_PROGRESS.value,
        ),
        RenaultBinarySensorEntityDescription(
            key="hvac_status",
            coordinator="hvac_status",
            on_key="hvacStatus",
            on_value="on",
            translation_key="hvac_status",
        ),
        RenaultBinarySensorEntityDescription(
            key="lock_status",
            coordinator="lock_status",
            # lock: on means open (unlocked), off means closed (locked)
            device_class=BinarySensorDeviceClass.LOCK,
            on_key="lockStatus",
            on_value="unlocked",
        ),
        RenaultBinarySensorEntityDescription(
            key="hatch_status",
            coordinator="lock_status",
            # On means open, Off means closed
            device_class=BinarySensorDeviceClass.DOOR,
            on_key="hatchStatus",
            on_value="open",
            translation_key="hatch_status",
        ),
    ]
    + [
        RenaultBinarySensorEntityDescription(
            key=f"{door.replace(' ', '_').lower()}_door_status",
            coordinator="lock_status",
            # On means open, Off means closed
            device_class=BinarySensorDeviceClass.DOOR,
            on_key=f"doorStatus{door.replace(' ', '')}",
            on_value="open",
            translation_key=f"{door.lower().replace(' ', '_')}_door_status",
        )
        for door in ("Rear Left", "Rear Right", "Driver", "Passenger")
    ],
)
