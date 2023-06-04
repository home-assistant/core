"""Support for Roborock time."""
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import time
from typing import Any

from roborock.roborock_typing import RoborockCommand

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from .const import DOMAIN
from .coordinator import RoborockDataUpdateCoordinator
from .device import RoborockCoordinatedEntity


@dataclass
class RoborockTimeDescriptionMixin:
    """Define an entity description mixin for time entities."""

    # Gets the current time of the entity.
    get_time: Callable[[RoborockCoordinatedEntity], time]
    # Sets the current time of the entity.
    set_time: Callable[[RoborockCoordinatedEntity, time], Coroutine[Any, Any, dict]]


@dataclass
class RoborockTimeDescription(TimeEntityDescription, RoborockTimeDescriptionMixin):
    """Class to describe an Roborock time entity."""


TIME_DESCRIPTIONS: list[RoborockTimeDescription] = [
    RoborockTimeDescription(
        key="dnd_start_time",
        translation_key="dnd_start_time",
        icon="mdi:bell-cancel",
        get_time=lambda data: data.coordinator.roborock_device_info.props.dnd_timer.start_time,
        set_time=lambda entity, desired_time: entity.send(
            RoborockCommand.SET_DND_TIMER,
            [
                desired_time.hour,
                desired_time.minute,
                entity.coordinator.roborock_device_info.props.dnd_timer.end_hour,
                entity.coordinator.roborock_device_info.props.dnd_timer.end_minute,
            ],
        ),
        entity_category=EntityCategory.CONFIG,
    ),
    RoborockTimeDescription(
        key="dnd_end_time",
        translation_key="dnd_end_time",
        icon="mdi:bell-ring",
        get_time=lambda data: data.coordinator.roborock_device_info.props.dnd_timer.end_time,
        set_time=lambda entity, desired_time: entity.send(
            RoborockCommand.SET_DND_TIMER,
            [
                entity.coordinator.roborock_device_info.props.dnd_timer.start_hour,
                entity.coordinator.roborock_device_info.props.dnd_timer.start_minute,
                desired_time.hour,
                desired_time.minute,
            ],
        ),
        entity_category=EntityCategory.CONFIG,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Roborock time platform."""

    coordinators: dict[str, RoborockDataUpdateCoordinator] = hass.data[DOMAIN][
        config_entry.entry_id
    ]
    async_add_entities(
        RoborockTimeEntity(
            f"{description.key}_{slugify(device_id)}",
            coordinator,
            description,
        )
        for device_id, coordinator in coordinators.items()
        for description in TIME_DESCRIPTIONS
    )


class RoborockTimeEntity(RoborockCoordinatedEntity, TimeEntity):
    """A class to let you set options on a Roborock vacuum where the potential options are fixed."""

    entity_description: RoborockTimeDescription

    def __init__(
        self,
        unique_id: str,
        coordinator: RoborockDataUpdateCoordinator,
        entity_description: RoborockTimeDescription,
    ) -> None:
        """Create a time entity."""
        self.entity_description = entity_description
        super().__init__(unique_id, coordinator)

    @property
    def native_value(self) -> time | None:
        """Return the value reported by the time."""
        return self.entity_description.get_time(self)

    async def async_set_value(self, value: time) -> None:
        """Set the time."""
        await self.entity_description.set_time(self, value)
