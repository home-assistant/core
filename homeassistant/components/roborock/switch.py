"""Support for Roborock switch."""
from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import logging
from typing import Any

from roborock.api import AttributeCache
from roborock.command_cache import CacheableAttribute

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from .const import DOMAIN
from .coordinator import RoborockDataUpdateCoordinator
from .device import RoborockEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class RoborockSwitchDescriptionMixin:
    """Define an entity description mixin for switch entities."""

    # Gets the status of the switch
    cache_key: CacheableAttribute
    # Sets the status of the switch
    update_value: Callable[[AttributeCache, bool], Coroutine[Any, Any, dict]]
    # Attribute from cache
    attribute: str


@dataclass(frozen=True)
class RoborockSwitchDescription(
    SwitchEntityDescription, RoborockSwitchDescriptionMixin
):
    """Class to describe an Roborock switch entity."""


SWITCH_DESCRIPTIONS: list[RoborockSwitchDescription] = [
    RoborockSwitchDescription(
        cache_key=CacheableAttribute.child_lock_status,
        update_value=lambda cache, value: cache.update_value(
            {"lock_status": 1 if value else 0}
        ),
        attribute="lock_status",
        key="child_lock",
        translation_key="child_lock",
        entity_category=EntityCategory.CONFIG,
    ),
    RoborockSwitchDescription(
        cache_key=CacheableAttribute.flow_led_status,
        update_value=lambda cache, value: cache.update_value(
            {"status": 1 if value else 0}
        ),
        attribute="status",
        key="status_indicator",
        translation_key="status_indicator",
        entity_category=EntityCategory.CONFIG,
    ),
    RoborockSwitchDescription(
        cache_key=CacheableAttribute.dnd_timer,
        update_value=lambda cache, value: cache.update_value(
            [
                cache.value.get("start_hour"),
                cache.value.get("start_minute"),
                cache.value.get("end_hour"),
                cache.value.get("end_minute"),
            ]
        )
        if value
        else cache.close_value(),
        attribute="enabled",
        key="dnd_switch",
        translation_key="dnd_switch",
        entity_category=EntityCategory.CONFIG,
    ),
    RoborockSwitchDescription(
        cache_key=CacheableAttribute.valley_electricity_timer,
        update_value=lambda cache, value: cache.update_value(
            [
                cache.value.get("start_hour"),
                cache.value.get("start_minute"),
                cache.value.get("end_hour"),
                cache.value.get("end_minute"),
            ]
        )
        if value
        else cache.close_value(),
        attribute="enabled",
        key="off_peak_switch",
        translation_key="off_peak_switch",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
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
    possible_entities: list[
        tuple[RoborockDataUpdateCoordinator, RoborockSwitchDescription]
    ] = [
        (coordinator, description)
        for coordinator in coordinators.values()
        for description in SWITCH_DESCRIPTIONS
    ]
    # We need to check if this function is supported by the device.
    results = await asyncio.gather(
        *(
            coordinator.api.get_from_cache(description.cache_key)
            for coordinator, description in possible_entities
        ),
        return_exceptions=True,
    )
    valid_entities: list[RoborockSwitch] = []
    for (coordinator, description), result in zip(possible_entities, results):
        if result is None or isinstance(result, Exception):
            _LOGGER.debug("Not adding entity because of %s", result)
        else:
            valid_entities.append(
                RoborockSwitch(
                    f"{description.key}_{slugify(coordinator.roborock_device_info.device.duid)}",
                    coordinator,
                    description,
                )
            )
    async_add_entities(valid_entities)


class RoborockSwitch(RoborockEntity, SwitchEntity):
    """A class to let you turn functionality on Roborock devices on and off that does need a coordinator."""

    entity_description: RoborockSwitchDescription

    def __init__(
        self,
        unique_id: str,
        coordinator: RoborockDataUpdateCoordinator,
        entity_description: RoborockSwitchDescription,
    ) -> None:
        """Initialize the entity."""
        self.entity_description = entity_description
        super().__init__(unique_id, coordinator.device_info, coordinator.api)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        await self.entity_description.update_value(
            self.get_cache(self.entity_description.cache_key), False
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        await self.entity_description.update_value(
            self.get_cache(self.entity_description.cache_key), True
        )

    @property
    def is_on(self) -> bool | None:
        """Return True if entity is on."""
        return (
            self.get_cache(self.entity_description.cache_key).value.get(
                self.entity_description.attribute
            )
            == 1
        )
