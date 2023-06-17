"""Support for Roborock number."""
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from roborock.roborock_typing import RoborockCommand

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from .const import DOMAIN
from .coordinator import RoborockDataUpdateCoordinator
from .device import RoborockEntity


@dataclass
class RoborockNumberDescriptionMixin:
    """Define an entity description mixin for number entities."""

    # Gets the current value of the number entity.
    get_value: Callable[[RoborockEntity], Coroutine[Any, Any, int]]
    # Sets the current value of the number entity.
    set_value: Callable[[RoborockEntity, int], Coroutine[Any, Any, dict]]


@dataclass
class RoborockNumberDescription(
    NumberEntityDescription, RoborockNumberDescriptionMixin
):
    """Class to describe an Roborock number entity."""


NUMBER_DESCRIPTIONS: list[RoborockNumberDescription] = [
    RoborockNumberDescription(
        key="volume",
        translation_key="volume",
        icon="mdi:volume-source",
        native_min_value=0,
        native_max_value=100,
        native_unit_of_measurement=PERCENTAGE,
        get_value=lambda entity: entity.api.get_sound_volume(),
        set_value=lambda entity, value: entity.send(
            RoborockCommand.CHANGE_SOUND_VOLUME, value
        ),
        entity_category=EntityCategory.CONFIG,
    )
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Roborock number platform."""

    coordinators: dict[str, RoborockDataUpdateCoordinator] = hass.data[DOMAIN][
        config_entry.entry_id
    ]
    async_add_entities(
        (
            RoborockNumberEntity(
                f"{description.key}_{slugify(device_id)}",
                coordinator,
                description,
            )
            for device_id, coordinator in coordinators.items()
            for description in NUMBER_DESCRIPTIONS
        ),
        True,
    )


class RoborockNumberEntity(RoborockEntity, NumberEntity):
    """A class to let you set options on a Roborock vacuum where the potential options are fixed."""

    entity_description: RoborockNumberDescription

    def __init__(
        self,
        unique_id: str,
        coordinator: RoborockDataUpdateCoordinator,
        entity_description: RoborockNumberDescription,
    ) -> None:
        """Create a number entity."""
        self.entity_description = entity_description
        super().__init__(unique_id, coordinator.device_info, coordinator.api)

    async def async_set_native_value(self, value: float) -> None:
        """Set number value."""
        await self.entity_description.set_value(self, int(value))

    async def async_update(self) -> None:
        """Update number."""
        number = await self.entity_description.get_value(self)
        self._attr_native_value = float(number)
