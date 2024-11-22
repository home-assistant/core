"""Support for Roborock number."""

import asyncio
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import logging
from typing import Any

from roborock.command_cache import CacheableAttribute
from roborock.exceptions import RoborockException
from roborock.version_1_apis.roborock_client_v1 import AttributeCache

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN, RoborockConfigEntry
from .coordinator import RoborockDataUpdateCoordinator
from .entity import RoborockEntityV1

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class RoborockNumberDescription(NumberEntityDescription):
    """Class to describe a Roborock number entity."""

    # Gets the status of the switch
    cache_key: CacheableAttribute
    # Sets the status of the switch
    update_value: Callable[[AttributeCache, float], Coroutine[Any, Any, None]]


NUMBER_DESCRIPTIONS: list[RoborockNumberDescription] = [
    RoborockNumberDescription(
        key="volume",
        translation_key="volume",
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
    config_entry: RoborockConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Roborock number platform."""
    possible_entities: list[
        tuple[RoborockDataUpdateCoordinator, RoborockNumberDescription]
    ] = [
        (coordinator, description)
        for coordinator in config_entry.runtime_data.v1
        for description in NUMBER_DESCRIPTIONS
    ]
    # We need to check if this function is supported by the device.
    results = await asyncio.gather(
        *(
            coordinator.api.get_from_cache(description.cache_key)
            for coordinator, description in possible_entities
        ),
        return_exceptions=True,
    )
    valid_entities: list[RoborockNumberEntity] = []
    for (coordinator, description), result in zip(
        possible_entities, results, strict=False
    ):
        if result is None or isinstance(result, RoborockException):
            _LOGGER.debug("Not adding entity because of %s", result)
        else:
            valid_entities.append(
                RoborockNumberEntity(
                    f"{description.key}_{coordinator.duid_slug}",
                    coordinator,
                    description,
                )
            )
    async_add_entities(valid_entities)


class RoborockNumberEntity(RoborockEntityV1, NumberEntity):
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
        val: float = self.get_cache(self.entity_description.cache_key).value
        return val

    async def async_set_native_value(self, value: float) -> None:
        """Set number value."""
        try:
            await self.entity_description.update_value(
                self.get_cache(self.entity_description.cache_key), value
            )
        except RoborockException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="update_options_failed",
            ) from err
