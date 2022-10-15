"""Support for MyBMW button entities."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any

from bimmer_connected.vehicle import MyBMWVehicle
from bimmer_connected.vehicle.remote_services import RemoteServiceStatus

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BMWBaseEntity
from .const import DOMAIN

if TYPE_CHECKING:
    from .coordinator import BMWDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass
class BMWButtonEntityDescription(ButtonEntityDescription):
    """Class describing BMW button entities."""

    enabled_when_read_only: bool = False
    remote_function: Callable[
        [MyBMWVehicle], Coroutine[Any, Any, RemoteServiceStatus]
    ] | None = None
    account_function: Callable[[BMWDataUpdateCoordinator], Coroutine] | None = None


BUTTON_TYPES: tuple[BMWButtonEntityDescription, ...] = (
    BMWButtonEntityDescription(
        key="light_flash",
        icon="mdi:car-light-alert",
        name="Flash lights",
        remote_function=lambda vehicle: vehicle.remote_services.trigger_remote_light_flash(),
    ),
    BMWButtonEntityDescription(
        key="sound_horn",
        icon="mdi:bullhorn",
        name="Sound horn",
        remote_function=lambda vehicle: vehicle.remote_services.trigger_remote_horn(),
    ),
    BMWButtonEntityDescription(
        key="activate_air_conditioning",
        icon="mdi:hvac",
        name="Activate air conditioning",
        remote_function=lambda vehicle: vehicle.remote_services.trigger_remote_air_conditioning(),
    ),
    BMWButtonEntityDescription(
        key="deactivate_air_conditioning",
        icon="mdi:hvac-off",
        name="Deactivate air conditioning",
        remote_function=lambda vehicle: vehicle.remote_services.trigger_remote_air_conditioning_stop(),
    ),
    BMWButtonEntityDescription(
        key="find_vehicle",
        icon="mdi:crosshairs-question",
        name="Find vehicle",
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
    """Set up the BMW buttons from config entry."""
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
        if self.entity_description.remote_function:
            await self.entity_description.remote_function(self.vehicle)
        elif self.entity_description.account_function:
            _LOGGER.warning(
                "The 'Refresh from cloud' button is deprecated. Use the 'homeassistant.update_entity' "
                "service with any BMW entity for a full reload. See https://www.home-assistant.io/"
                "integrations/bmw_connected_drive/#update-the-state--refresh-from-api for details"
            )
            await self.entity_description.account_function(self.coordinator)

        # Always update HA states after a button was executed.
        # BMW remote services that change the vehicle's state update the local object
        # when executing the service, so only the HA state machine needs further updates.
        self.coordinator.async_update_listeners()
