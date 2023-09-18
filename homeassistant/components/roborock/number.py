"""Support for Roborock number."""
import asyncio
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import logging
from typing import Any

from roborock.api import AttributeCache
from roborock.command_cache import CacheableAttribute
from roborock.exceptions import RoborockException

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from .const import DOMAIN
from .coordinator import RoborockDataUpdateCoordinator
from .device import RoborockEntity

_LOGGER = logging.getLogger(__name__)


@dataclass
class RoborockNumberDescriptionMixin:
    """Define an entity description mixin for button entities."""

    # Gets the status of the switch
    cache_key: CacheableAttribute
    # Sets the status of the switch
    update_value: Callable[[AttributeCache, float], Coroutine[Any, Any, dict]]


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
        cache_key=CacheableAttribute.sound_volume,
        entity_category=EntityCategory.CONFIG,
        update_value=lambda cache, value: cache.update_value([int(value)]),
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
    possible_entities: list[
        tuple[RoborockDataUpdateCoordinator, RoborockNumberDescription]
    ] = [
        (coordinator, description)
        for coordinator in coordinators.values()
        for description in NUMBER_DESCRIPTIONS
    ]
    # We need to check if this function is supported by the device.
    results = await asyncio.gather(
        *(
            coordinator.api.cache.get(description.cache_key).async_value()
            for coordinator, description in possible_entities
        ),
        return_exceptions=True,
    )
    valid_entities: list[RoborockNumberEntity] = []
    for (coordinator, description), result in zip(possible_entities, results):
        if result is None or isinstance(result, RoborockException):
            _LOGGER.debug("Not adding entity because of %s", result)
        else:
            valid_entities.append(
                RoborockNumberEntity(
                    f"{description.key}_{slugify(coordinator.roborock_device_info.device.duid)}",
                    coordinator,
                    description,
                )
            )
    async_add_entities(valid_entities)


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

    @property
    def native_value(self) -> float | None:
        """Get native value."""
        return self.get_cache(self.entity_description.cache_key).value

    async def async_set_native_value(self, value: float) -> None:
        """Set number value."""
        await self.entity_description.update_value(
            self.get_cache(self.entity_description.cache_key), value
        )
