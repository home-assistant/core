"""Support for Renault sensors."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from renault_api.kamereon.models import KamereonVehicleBatteryStatusData

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DEVICE_CLASS_CHARGE_MODE, DOMAIN
from .renault_entities import RenaultDataEntity, RenaultDataEntityDescription
from .renault_hub import RenaultHub


@dataclass
class RenaultSelectRequiredKeysMixin:
    """Mixin for required keys."""

    data_key: str
    icon_lambda: Callable[[RenaultSelectEntity], str]


@dataclass
class RenaultSelectEntityDescription(
    SelectEntityDescription,
    RenaultDataEntityDescription,
    RenaultSelectRequiredKeysMixin,
):
    """Class describing Renault select entities."""


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Renault entities from config entry."""
    proxy: RenaultHub = hass.data[DOMAIN][config_entry.entry_id]
    entities: list[RenaultSelectEntity] = [
        RenaultSelectEntity(vehicle, description)
        for vehicle in proxy.vehicles.values()
        for description in SENSOR_TYPES
        if description.coordinator in vehicle.coordinators
    ]
    async_add_entities(entities)


class RenaultSelectEntity(
    RenaultDataEntity[KamereonVehicleBatteryStatusData], SelectEntity
):
    """Mixin for sensor specific attributes."""

    entity_description: RenaultSelectEntityDescription

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        return cast(str, self.data)

    @property
    def data(self) -> StateType:
        """Return the state of this entity."""
        return self._get_data_attr(self.entity_description.data_key)

    @property
    def icon(self) -> str | None:
        """Icon handling."""
        return self.entity_description.icon_lambda(self)

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.vehicle.vehicle.set_charge_mode(option)


def _get_charge_mode_icon(entity: RenaultSelectEntity) -> str:
    """Return the icon of this entity."""
    if entity.data == "schedule_mode":
        return "mdi:calendar-clock"
    return "mdi:calendar-remove"


SENSOR_TYPES: tuple[RenaultSelectEntityDescription, ...] = (
    RenaultSelectEntityDescription(
        key="charge_mode",
        coordinator="charge_mode",
        data_key="chargeMode",
        device_class=DEVICE_CLASS_CHARGE_MODE,
        icon_lambda=_get_charge_mode_icon,
        name="Charge mode",
        options=["always", "always_charging", "schedule_mode"],
    ),
)
