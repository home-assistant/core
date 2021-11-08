"""Support for Renault binary sensors."""
from __future__ import annotations

from dataclasses import dataclass

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
        return (
            self._get_data_attr(self.entity_description.on_key)
            == self.entity_description.on_value
        )


BINARY_SENSOR_TYPES: tuple[RenaultBinarySensorEntityDescription, ...] = (
    RenaultBinarySensorEntityDescription(
        key="plugged_in",
        coordinator="battery",
        device_class=DEVICE_CLASS_PLUG,
        name="Plugged In",
        on_key="plugStatus",
        on_value=PlugState.PLUGGED.value,
    ),
    RenaultBinarySensorEntityDescription(
        key="charging",
        coordinator="battery",
        device_class=DEVICE_CLASS_BATTERY_CHARGING,
        name="Charging",
        on_key="chargingStatus",
        on_value=ChargeState.CHARGE_IN_PROGRESS.value,
    ),
)
