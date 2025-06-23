"""Support for MyBMW button entities."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any

from bimmer_connected.models import MyBMWAPIError
from bimmer_connected.vehicle import MyBMWVehicle
from bimmer_connected.vehicle.remote_services import RemoteServiceStatus

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DOMAIN, BMWConfigEntry
from .entity import BMWBaseEntity

if TYPE_CHECKING:
    from .coordinator import BMWDataUpdateCoordinator

PARALLEL_UPDATES = 1

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class BMWButtonEntityDescription(ButtonEntityDescription):
    """Class describing BMW button entities."""

    remote_function: Callable[[MyBMWVehicle], Coroutine[Any, Any, RemoteServiceStatus]]
    enabled_when_read_only: bool = False
    is_available: Callable[[MyBMWVehicle], bool] = lambda _: True


BUTTON_TYPES: tuple[BMWButtonEntityDescription, ...] = (
    BMWButtonEntityDescription(
        key="light_flash",
        translation_key="light_flash",
        remote_function=lambda vehicle: vehicle.remote_services.trigger_remote_light_flash(),
    ),
    BMWButtonEntityDescription(
        key="sound_horn",
        translation_key="sound_horn",
        remote_function=lambda vehicle: vehicle.remote_services.trigger_remote_horn(),
    ),
    BMWButtonEntityDescription(
        key="activate_air_conditioning",
        translation_key="activate_air_conditioning",
        remote_function=lambda vehicle: vehicle.remote_services.trigger_remote_air_conditioning(),
    ),
    BMWButtonEntityDescription(
        key="deactivate_air_conditioning",
        translation_key="deactivate_air_conditioning",
        remote_function=lambda vehicle: vehicle.remote_services.trigger_remote_air_conditioning_stop(),
        is_available=lambda vehicle: vehicle.is_remote_climate_stop_enabled,
    ),
    BMWButtonEntityDescription(
        key="find_vehicle",
        translation_key="find_vehicle",
        remote_function=lambda vehicle: vehicle.remote_services.trigger_remote_vehicle_finder(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BMWConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the BMW buttons from config entry."""
    coordinator = config_entry.runtime_data

    entities: list[BMWButton] = []

    for vehicle in coordinator.account.vehicles:
        entities.extend(
            [
                BMWButton(coordinator, vehicle, description)
                for description in BUTTON_TYPES
                if (not coordinator.read_only and description.is_available(vehicle))
                or (coordinator.read_only and description.enabled_when_read_only)
            ]
        )

    async_add_entities(entities)


class BMWButton(BMWBaseEntity, ButtonEntity):
    """Representation of a MyBMW button."""

    entity_description: BMWButtonEntityDescription

    def __init__(
        self,
        coordinator: BMWDataUpdateCoordinator,
        vehicle: MyBMWVehicle,
        description: BMWButtonEntityDescription,
    ) -> None:
        """Initialize BMW vehicle sensor."""
        super().__init__(coordinator, vehicle)
        self.entity_description = description
        self._attr_unique_id = f"{vehicle.vin}-{description.key}"

    async def async_press(self) -> None:
        """Press the button."""
        try:
            await self.entity_description.remote_function(self.vehicle)
        except MyBMWAPIError as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="remote_service_error",
                translation_placeholders={"exception": str(ex)},
            ) from ex

        self.coordinator.async_update_listeners()
