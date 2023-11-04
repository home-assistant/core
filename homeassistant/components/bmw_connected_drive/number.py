"""Number platform for BMW."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import logging
from typing import Any

from bimmer_connected.models import MyBMWAPIError
from bimmer_connected.vehicle import MyBMWVehicle

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BMWBaseEntity
from .const import DOMAIN
from .coordinator import BMWDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass
class BMWRequiredKeysMixin:
    """Mixin for required keys."""

    value_fn: Callable[[MyBMWVehicle], float | int | None]
    remote_service: Callable[[MyBMWVehicle, float | int], Coroutine[Any, Any, Any]]


@dataclass
class BMWNumberEntityDescription(NumberEntityDescription, BMWRequiredKeysMixin):
    """Describes BMW number entity."""

    is_available: Callable[[MyBMWVehicle], bool] = lambda _: False
    dynamic_options: Callable[[MyBMWVehicle], list[str]] | None = None


NUMBER_TYPES: list[BMWNumberEntityDescription] = [
    BMWNumberEntityDescription(
        key="target_soc",
        translation_key="target_soc",
        device_class=NumberDeviceClass.BATTERY,
        is_available=lambda v: v.is_remote_set_target_soc_enabled,
        native_max_value=100.0,
        native_min_value=20.0,
        native_step=5.0,
        mode=NumberMode.SLIDER,
        value_fn=lambda v: v.fuel_and_battery.charging_target,
        remote_service=lambda v, o: v.remote_services.trigger_charging_settings_update(
            target_soc=int(o)
        ),
        icon="mdi:battery-charging-medium",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the MyBMW number from config entry."""
    coordinator: BMWDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities: list[BMWNumber] = []

    for vehicle in coordinator.account.vehicles:
        if not coordinator.read_only:
            entities.extend(
                [
                    BMWNumber(coordinator, vehicle, description)
                    for description in NUMBER_TYPES
                    if description.is_available(vehicle)
                ]
            )
    async_add_entities(entities)


class BMWNumber(BMWBaseEntity, NumberEntity):
    """Representation of BMW Number entity."""

    entity_description: BMWNumberEntityDescription

    def __init__(
        self,
        coordinator: BMWDataUpdateCoordinator,
        vehicle: MyBMWVehicle,
        description: BMWNumberEntityDescription,
    ) -> None:
        """Initialize an BMW Number."""
        super().__init__(coordinator, vehicle)
        self.entity_description = description
        self._attr_unique_id = f"{vehicle.vin}-{description.key}"

    @property
    def native_value(self) -> float | None:
        """Return the entity value to represent the entity state."""
        return self.entity_description.value_fn(self.vehicle)

    async def async_set_native_value(self, value: float) -> None:
        """Update to the vehicle."""
        _LOGGER.debug(
            "Executing '%s' on vehicle '%s' to value '%s'",
            self.entity_description.key,
            self.vehicle.vin,
            value,
        )
        try:
            await self.entity_description.remote_service(self.vehicle, value)
        except MyBMWAPIError as ex:
            raise HomeAssistantError(ex) from ex

        self.coordinator.async_update_listeners()
