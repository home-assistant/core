"""Support for BMW connected drive button entities."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from bimmer_connected.remote_services import RemoteServiceStatus
from bimmer_connected.vehicle import ConnectedDriveVehicle

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import (
    DOMAIN as BMW_DOMAIN,
    BMWConnectedDriveAccount,
    BMWConnectedDriveBaseEntity,
)
from .const import CONF_ACCOUNT, DATA_ENTRIES


@dataclass
class BMWButtonEntityDescription(ButtonEntityDescription):
    """Class describing BMW button entities."""

    enabled_when_read_only: bool = False
    remote_function: Callable[
        [ConnectedDriveVehicle], RemoteServiceStatus
    ] | None = None
    account_function: Callable[[BMWConnectedDriveAccount], None] | None = None


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
        account_function=lambda account: account.update(),
        enabled_when_read_only=True,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the BMW ConnectedDrive buttons from config entry."""
    account: BMWConnectedDriveAccount = hass.data[BMW_DOMAIN][DATA_ENTRIES][
        config_entry.entry_id
    ][CONF_ACCOUNT]
    entities: list[BMWButton] = []

    for vehicle in account.account.vehicles:
        entities.extend(
            [
                BMWButton(account, vehicle, description)
                for description in BUTTON_TYPES
                if not account.read_only
                or (account.read_only and description.enabled_when_read_only)
            ]
        )

    async_add_entities(entities)


class BMWButton(BMWConnectedDriveBaseEntity, ButtonEntity):
    """Representation of a BMW Connected Drive button."""

    entity_description: BMWButtonEntityDescription

    def __init__(
        self,
        account: BMWConnectedDriveAccount,
        vehicle: ConnectedDriveVehicle,
        description: BMWButtonEntityDescription,
    ) -> None:
        """Initialize BMW vehicle sensor."""
        super().__init__(account, vehicle)
        self.entity_description = description

        self._attr_name = f"{vehicle.name} {description.name}"
        self._attr_unique_id = f"{vehicle.vin}-{description.key}"

    def press(self) -> None:
        """Process the button press."""
        if self.entity_description.remote_function:
            self.entity_description.remote_function(self._vehicle)
        elif self.entity_description.account_function:
            self.entity_description.account_function(self._account)
