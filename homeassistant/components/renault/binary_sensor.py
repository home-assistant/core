"""Support for Renault binary sensors."""

from __future__ import annotations

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

    on_key: str
    on_value: StateType | list[StateType]


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
        if (data := self._get_data_attr(self.entity_description.on_key)) is None:
            return None

        if isinstance(self.entity_description.on_value, list):
            return data in self.entity_description.on_value
        return data == self.entity_description.on_value


BINARY_SENSOR_TYPES: tuple[RenaultBinarySensorEntityDescription, ...] = tuple(
    [
        RenaultBinarySensorEntityDescription(
            key="plugged_in",
            coordinator="battery",
            device_class=BinarySensorDeviceClass.PLUG,
            on_key="plugStatus",
            on_value=PlugState.PLUGGED.value,
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
