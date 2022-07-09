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
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN
from .renault_entities import RenaultDataEntity, RenaultDataEntityDescription
from .renault_hub import RenaultHub


@dataclass
class RenaultBinarySensorRequiredKeysMixin:
    """Mixin for required keys."""

    on_key: str
    on_value: StateType


@dataclass
class RenaultBinarySensorEntityDescription(
    BinarySensorEntityDescription,
    RenaultDataEntityDescription,
    RenaultBinarySensorRequiredKeysMixin,
):
    """Class describing Renault binary sensor entities."""

    icon_fn: Callable[[RenaultBinarySensor], str] | None = None


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Renault entities from config entry."""
    proxy: RenaultHub = hass.data[DOMAIN][config_entry.entry_id]
    entities: list[RenaultBinarySensor] = [
        RenaultBinarySensor(vehicle, description)
        for vehicle in proxy.vehicles.values()
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
        return data == self.entity_description.on_value

    @property
    def icon(self) -> str | None:
        """Icon handling."""
        if self.entity_description.icon_fn:
            return self.entity_description.icon_fn(self)
        return None


BINARY_SENSOR_TYPES: tuple[RenaultBinarySensorEntityDescription, ...] = tuple(
    [
        RenaultBinarySensorEntityDescription(
            key="plugged_in",
            coordinator="battery",
            device_class=BinarySensorDeviceClass.PLUG,
            name="Plugged in",
            on_key="plugStatus",
            on_value=PlugState.PLUGGED.value,
        ),
        RenaultBinarySensorEntityDescription(
            key="charging",
            coordinator="battery",
            device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
            name="Charging",
            on_key="chargingStatus",
            on_value=ChargeState.CHARGE_IN_PROGRESS.value,
        ),
        RenaultBinarySensorEntityDescription(
            key="hvac_status",
            coordinator="hvac_status",
            icon_fn=lambda e: "mdi:fan" if e.is_on else "mdi:fan-off",
            name="HVAC",
            on_key="hvacStatus",
            on_value="on",
        ),
        RenaultBinarySensorEntityDescription(
            key="lock_status",
            coordinator="lock_status",
            # lock: on means open (unlocked), off means closed (locked)
            device_class=BinarySensorDeviceClass.LOCK,
            name="Lock",
            on_key="lockStatus",
            on_value="unlocked",
        ),
        RenaultBinarySensorEntityDescription(
            key="hatch_status",
            coordinator="lock_status",
            # On means open, Off means closed
            device_class=BinarySensorDeviceClass.DOOR,
            name="Hatch",
            on_key="hatchStatus",
            on_value="open",
        ),
    ]
    + [
        RenaultBinarySensorEntityDescription(
            key=f"{door.replace(' ','_').lower()}_door_status",
            coordinator="lock_status",
            # On means open, Off means closed
            device_class=BinarySensorDeviceClass.DOOR,
            name=f"{door.capitalize()} door",
            on_key=f"doorStatus{door.replace(' ','')}",
            on_value="open",
        )
        for door in ("Rear Left", "Rear Right", "Driver", "Passenger")
    ],
)
