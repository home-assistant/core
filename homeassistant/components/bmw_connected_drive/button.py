"""Support for BMW connected drive button entities."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import TYPE_CHECKING

from bimmer_connected.remote_services import RemoteServiceStatus
from bimmer_connected.vehicle import ConnectedDriveVehicle

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BMWConnectedDriveBaseEntity
from .const import DOMAIN

if TYPE_CHECKING:
    from .coordinator import BMWDataUpdateCoordinator


@dataclass
class BMWButtonEntityDescription(ButtonEntityDescription):
    """Class describing BMW button entities."""

    enabled_when_read_only: bool = False
    remote_function: Callable[
        [ConnectedDriveVehicle], RemoteServiceStatus
    ] | None = None
    account_function: Callable[[BMWDataUpdateCoordinator], Coroutine] | None = None


BUTTON_TYPES: tuple[BMWButtonEntityDescription, ...] = (
    BMWButtonEntityDescription(
        key="light_flash",
        icon="mdi:car-light-alert",
        name="Flash Lights",
        remote_function=lambda vehicle: vehicle.remote_services.trigger_remote_light_flash(),
    ),
    BMWButtonEntityDescription(
        key="sound_horn",
        icon="mdi:bullhorn",
        name="Sound Horn",
        remote_function=lambda vehicle: vehicle.remote_services.trigger_remote_horn(),
    ),
    BMWButtonEntityDescription(
        key="activate_air_conditioning",
        icon="mdi:hvac",
        name="Activate Air Conditioning",
        remote_function=lambda vehicle: vehicle.remote_services.trigger_remote_air_conditioning(),
    ),
    BMWButtonEntityDescription(
        key="deactivate_air_conditioning",
        icon="mdi:hvac-off",
        name="Deactivate Air Conditioning",
        remote_function=lambda vehicle: vehicle.remote_services.trigger_remote_air_conditioning_stop(),
    ),
    BMWButtonEntityDescription(
        key="find_vehicle",
        icon="mdi:crosshairs-question",
        name="Find Vehicle",
        remote_function=lambda vehicle: vehicle.remote_services.trigger_remote_vehicle_finder(),
    ),
    BMWButtonEntityDescription(
        key="refresh",
        icon="mdi:refresh",
        name="Refresh from cloud",
        account_function=lambda coordinator: coordinator.async_request_refresh(),
        enabled_when_read_only=True,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the BMW ConnectedDrive buttons from config entry."""
    coordinator: BMWDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities: list[BMWButton] = []

    for vehicle in coordinator.account.vehicles:
        entities.extend(
            [
                BMWButton(coordinator, vehicle, description)
                for description in BUTTON_TYPES
                if not coordinator.read_only
                or (coordinator.read_only and description.enabled_when_read_only)
            ]
        )

    async_add_entities(entities)


class BMWButton(BMWConnectedDriveBaseEntity, ButtonEntity):
    """Representation of a BMW Connected Drive button."""

    entity_description: BMWButtonEntityDescription

    def __init__(
        self,
        coordinator: BMWDataUpdateCoordinator,
        vehicle: ConnectedDriveVehicle,
        description: BMWButtonEntityDescription,
    ) -> None:
        """Initialize BMW vehicle sensor."""
        super().__init__(coordinator, vehicle)
        self.entity_description = description

        self._attr_name = f"{vehicle.name} {description.name}"
        self._attr_unique_id = f"{vehicle.vin}-{description.key}"

    async def async_press(self) -> None:
        """Press the button."""
        if self.entity_description.remote_function:
            await self.hass.async_add_executor_job(
                self.entity_description.remote_function(self.vehicle)
            )
        elif self.entity_description.account_function:
            await self.entity_description.account_function(self.coordinator)
