"""Support for Roborock switch."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import logging
from typing import Any

from roborock.command_cache import CacheableAttribute
from roborock.exceptions import RoborockException
from roborock.version_1_apis.roborock_client_v1 import AttributeCache

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN, RoborockConfigEntry
from .coordinator import RoborockDataUpdateCoordinator
from .entity import RoborockEntityV1

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class RoborockSwitchDescription(SwitchEntityDescription):
    """Class to describe a Roborock switch entity."""

    # Gets the status of the switch
    cache_key: CacheableAttribute
    # Sets the status of the switch
    update_value: Callable[[AttributeCache, bool], Coroutine[Any, Any, None]]
    # Attribute from cache
    attribute: str


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
    config_entry: RoborockConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Roborock switch platform."""
    possible_entities: list[
        tuple[RoborockDataUpdateCoordinator, RoborockSwitchDescription]
    ] = [
        (coordinator, description)
        for coordinator in config_entry.runtime_data.v1
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
    for (coordinator, description), result in zip(
        possible_entities, results, strict=False
    ):
        if result is None or isinstance(result, Exception):
            _LOGGER.debug("Not adding entity because of %s", result)
        else:
            valid_entities.append(
                RoborockSwitch(
                    f"{description.key}_{coordinator.duid_slug}",
                    coordinator,
                    description,
                )
            )
    async_add_entities(valid_entities)


class RoborockSwitch(RoborockEntityV1, SwitchEntity):
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
        try:
            await self.entity_description.update_value(
                self.get_cache(self.entity_description.cache_key), False
            )
        except RoborockException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="update_options_failed",
            ) from err

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        try:
            await self.entity_description.update_value(
                self.get_cache(self.entity_description.cache_key), True
            )
        except RoborockException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="update_options_failed",
            ) from err

    @property
    def is_on(self) -> bool | None:
        """Return True if entity is on."""
        status = self.get_cache(self.entity_description.cache_key).value.get(
            self.entity_description.attribute
        )
        if status is None:
            return status
        return bool(status)
