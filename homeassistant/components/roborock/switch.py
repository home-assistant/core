"""Support for Roborock select."""
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from roborock.roborock_typing import RoborockCommand

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from .const import DOMAIN
from .coordinator import RoborockDataUpdateCoordinator
from .device import RoborockCoordinatedEntity


@dataclass
class RoborockSwitchDescriptionMixin:
    """Define an entity description mixin for switch entities."""

    # Gets the status of the switch
    get_command: RoborockCommand
    # Sets the status of the switch
    set_command: Callable[[RoborockCoordinatedEntity, bool], None]


@dataclass
class RoborockSwitchDescription(
    SwitchEntityDescription, RoborockSwitchDescriptionMixin
):
    """Class to describe an Roborock switch entity."""


SELECT_DESCRIPTIONS: list[RoborockSwitchDescription] = [
    RoborockSwitchDescription(
        get_command=RoborockCommand.GET_CHILD_LOCK_STATUS,
        set_command=lambda data: data[0].send(
            RoborockCommand.SET_CHILD_LOCK_STATUS, {"lock_status": 1 if data[1] else 0}
        ),
        key="dnd",
        translation_key="dnd",
        icon="mdi:donotdisturb",
    )
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Roborock switch platform."""

    coordinators: dict[str, RoborockDataUpdateCoordinator] = hass.data[DOMAIN][
        config_entry.entry_id
    ]
    async_add_entities(
        RoborockSwitchEntity(
            f"{description.key}_{slugify(device_id)}",
            coordinator,
            description,
        )
        for device_id, coordinator in coordinators.items()
        for description in SELECT_DESCRIPTIONS
    )


class RoborockSwitchEntity(RoborockCoordinatedEntity, SwitchEntity):
    """A class to let you turn functionality on Roborock devices on and off."""

    entity_description: RoborockSwitchDescription

    def __init__(
        self,
        unique_id: str,
        coordinator: RoborockDataUpdateCoordinator,
        entity_description: RoborockSwitchDescription,
    ) -> None:
        """Create a switch entity."""
        self.entity_description = entity_description
        super().__init__(unique_id, coordinator)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        await self.entity_description.set_command((self, False))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        await self.entity_description.set_command((self, True))

    @property
    def is_on(self) -> bool | None:
        """Determine if the switch is on or off."""
        return self.send(self.entity_description.get_command)
