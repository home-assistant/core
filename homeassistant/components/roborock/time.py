"""Support for Roborock time."""

import asyncio
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import datetime
from datetime import time
import logging
from typing import Any

from roborock.command_cache import CacheableAttribute
from roborock.exceptions import RoborockException
from roborock.version_1_apis.roborock_client_v1 import AttributeCache

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from .const import DOMAIN
from .coordinator import RoborockDataUpdateCoordinator
from .device import RoborockEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class RoborockTimeDescription(TimeEntityDescription):
    """Class to describe a Roborock time entity."""

    # Gets the status of the switch
    cache_key: CacheableAttribute
    # Sets the status of the switch
    update_value: Callable[[AttributeCache, datetime.time], Coroutine[Any, Any, dict]]
    # Attribute from cache
    get_value: Callable[[AttributeCache], datetime.time]


TIME_DESCRIPTIONS: list[RoborockTimeDescription] = [
    RoborockTimeDescription(
        key="dnd_start_time",
        translation_key="dnd_start_time",
        cache_key=CacheableAttribute.dnd_timer,
        update_value=lambda cache, desired_time: cache.update_value(
            [
                desired_time.hour,
                desired_time.minute,
                cache.value.get("end_hour"),
                cache.value.get("end_minute"),
            ]
        ),
        get_value=lambda cache: datetime.time(
            hour=cache.value.get("start_hour"), minute=cache.value.get("start_minute")
        ),
        entity_category=EntityCategory.CONFIG,
    ),
    RoborockTimeDescription(
        key="dnd_end_time",
        translation_key="dnd_end_time",
        cache_key=CacheableAttribute.dnd_timer,
        update_value=lambda cache, desired_time: cache.update_value(
            [
                cache.value.get("start_hour"),
                cache.value.get("start_minute"),
                desired_time.hour,
                desired_time.minute,
            ]
        ),
        get_value=lambda cache: datetime.time(
            hour=cache.value.get("end_hour"), minute=cache.value.get("end_minute")
        ),
        entity_category=EntityCategory.CONFIG,
    ),
    RoborockTimeDescription(
        key="off_peak_start",
        translation_key="off_peak_start",
        cache_key=CacheableAttribute.valley_electricity_timer,
        update_value=lambda cache, desired_time: cache.update_value(
            [
                desired_time.hour,
                desired_time.minute,
                cache.value.get("end_hour"),
                cache.value.get("end_minute"),
            ]
        ),
        get_value=lambda cache: datetime.time(
            hour=cache.value.get("start_hour"), minute=cache.value.get("start_minute")
        ),
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    RoborockTimeDescription(
        key="off_peak_end",
        translation_key="off_peak_end",
        cache_key=CacheableAttribute.valley_electricity_timer,
        update_value=lambda cache, desired_time: cache.update_value(
            [
                cache.value.get("start_hour"),
                cache.value.get("start_minute"),
                desired_time.hour,
                desired_time.minute,
            ]
        ),
        get_value=lambda cache: datetime.time(
            hour=cache.value.get("end_hour"), minute=cache.value.get("end_minute")
        ),
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
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
    possible_entities: list[
        tuple[RoborockDataUpdateCoordinator, RoborockTimeDescription]
    ] = [
        (coordinator, description)
        for coordinator in coordinators.values()
        for description in TIME_DESCRIPTIONS
    ]
    # We need to check if this function is supported by the device.
    results = await asyncio.gather(
        *(
            coordinator.api.get_from_cache(description.cache_key)
            for coordinator, description in possible_entities
        ),
        return_exceptions=True,
    )
    valid_entities: list[RoborockTimeEntity] = []
    for (coordinator, description), result in zip(
        possible_entities, results, strict=False
    ):
        if result is None or isinstance(result, RoborockException):
            _LOGGER.debug("Not adding entity because of %s", result)
        else:
            valid_entities.append(
                RoborockTimeEntity(
                    f"{description.key}_{slugify(coordinator.roborock_device_info.device.duid)}",
                    coordinator,
                    description,
                )
            )
    async_add_entities(valid_entities)


class RoborockTimeEntity(RoborockEntity, TimeEntity):
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
        super().__init__(unique_id, coordinator.device_info, coordinator.api)

    @property
    def native_value(self) -> time | None:
        """Return the value reported by the time."""
        return self.entity_description.get_value(
            self.get_cache(self.entity_description.cache_key)
        )

    async def async_set_value(self, value: time) -> None:
        """Set the time."""
        await self.entity_description.update_value(
            self.get_cache(self.entity_description.cache_key), value
        )
