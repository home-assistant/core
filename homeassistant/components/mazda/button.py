"""Platform for Mazda button integration."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pymazda import (
    Client as MazdaAPIClient,
    MazdaAccountLockedException,
    MazdaAPIEncryptionException,
    MazdaAuthenticationException,
    MazdaException,
    MazdaLoginFailedException,
    MazdaTokenExpiredException,
)

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import MazdaEntity
from .const import DATA_CLIENT, DATA_COORDINATOR, DOMAIN


async def handle_button_press(
    client: MazdaAPIClient,
    key: str,
    vehicle_id: int,
    coordinator: DataUpdateCoordinator,
) -> None:
    """Handle a press for a Mazda button entity."""
    api_method = getattr(client, key)

    try:
        await api_method(vehicle_id)
    except (
        MazdaException,
        MazdaAuthenticationException,
        MazdaAccountLockedException,
        MazdaTokenExpiredException,
        MazdaAPIEncryptionException,
        MazdaLoginFailedException,
    ) as ex:
        raise HomeAssistantError(ex) from ex


async def handle_refresh_vehicle_status(
    client: MazdaAPIClient,
    key: str,
    vehicle_id: int,
    coordinator: DataUpdateCoordinator,
) -> None:
    """Handle a request to refresh the vehicle status."""
    await handle_button_press(client, key, vehicle_id, coordinator)

    await coordinator.async_request_refresh()


@dataclass
class MazdaButtonEntityDescription(ButtonEntityDescription):
    """Describes a Mazda button entity."""

    # Function to determine whether the vehicle supports this button,
    # given the coordinator data
    is_supported: Callable[[dict[str, Any]], bool] = lambda data: True

    async_press: Callable[
        [MazdaAPIClient, str, int, DataUpdateCoordinator], Awaitable
    ] = handle_button_press


BUTTON_ENTITIES = [
    MazdaButtonEntityDescription(
        key="start_engine",
        name="Start engine",
        icon="mdi:engine",
    ),
    MazdaButtonEntityDescription(
        key="stop_engine",
        name="Stop engine",
        icon="mdi:engine-off",
    ),
    MazdaButtonEntityDescription(
        key="turn_on_hazard_lights",
        name="Turn on hazard lights",
        icon="mdi:hazard-lights",
    ),
    MazdaButtonEntityDescription(
        key="turn_off_hazard_lights",
        name="Turn off hazard lights",
        icon="mdi:hazard-lights",
    ),
    MazdaButtonEntityDescription(
        key="refresh_vehicle_status",
        name="Refresh status",
        icon="mdi:refresh",
        async_press=handle_refresh_vehicle_status,
        is_supported=lambda data: data["isElectric"],
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the button platform."""
    client = hass.data[DOMAIN][config_entry.entry_id][DATA_CLIENT]
    coordinator = hass.data[DOMAIN][config_entry.entry_id][DATA_COORDINATOR]

    async_add_entities(
        MazdaButtonEntity(client, coordinator, index, description)
        for index, data in enumerate(coordinator.data)
        for description in BUTTON_ENTITIES
        if description.is_supported(data)
    )


class MazdaButtonEntity(MazdaEntity, ButtonEntity):
    """Representation of a Mazda button."""

    entity_description: MazdaButtonEntityDescription

    def __init__(
        self,
        client: MazdaAPIClient,
        coordinator: DataUpdateCoordinator,
        index: int,
        description: MazdaButtonEntityDescription,
    ) -> None:
        """Initialize Mazda button."""
        super().__init__(client, coordinator, index)
        self.entity_description = description

        self._attr_unique_id = f"{self.vin}_{description.key}"

    async def async_press(self) -> None:
        """Press the button."""
        await self.entity_description.async_press(
            self.client, self.entity_description.key, self.vehicle_id, self.coordinator
        )
