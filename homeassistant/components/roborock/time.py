"""Support for Roborock time."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import datetime
from datetime import time
import logging
from typing import Any

from roborock.data import DnDTimer, ValleyElectricityTimer
from roborock.exceptions import RoborockException

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import RoborockConfigEntry, RoborockDataUpdateCoordinator
from .entity import RoborockEntityV1

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class RoborockTimeDescription(TimeEntityDescription):
    """Class to describe a Roborock time entity."""

    trait: Callable[[Any], Any | None]
    """Function to determine if time entity is supported by the device."""

    get_value: Callable[[Any], datetime.time]
    """Function to get the value from the trait."""

    update_value: Callable[[Any, datetime.time], Coroutine[Any, Any, None]]
    """Function to set the value on the trait."""


TIME_DESCRIPTIONS: list[RoborockTimeDescription] = [
    RoborockTimeDescription(
        key="dnd_start_time",
        translation_key="dnd_start_time",
        trait=lambda api: api.dnd,
        update_value=lambda trait, desired_time: trait.set_dnd_timer(
            DnDTimer(
                enabled=trait.enabled,
                start_hour=desired_time.hour,
                start_minute=desired_time.minute,
                end_hour=trait.end_hour,
                end_minute=trait.end_minute,
            )
        ),
        get_value=lambda trait: datetime.time(
            hour=trait.start_hour, minute=trait.start_minute
        ),
        entity_category=EntityCategory.CONFIG,
    ),
    RoborockTimeDescription(
        key="dnd_end_time",
        translation_key="dnd_end_time",
        trait=lambda api: api.dnd,
        update_value=lambda trait, desired_time: trait.set_dnd_timer(
            DnDTimer(
                enabled=trait.enabled,
                start_hour=trait.start_hour,
                start_minute=trait.start_minute,
                end_hour=desired_time.hour,
                end_minute=desired_time.minute,
            )
        ),
        get_value=lambda trait: datetime.time(
            hour=trait.end_hour, minute=trait.end_minute
        ),
        entity_category=EntityCategory.CONFIG,
    ),
    RoborockTimeDescription(
        key="off_peak_start",
        translation_key="off_peak_start",
        trait=lambda api: api.valley_electricity_timer,
        update_value=lambda trait, desired_time: trait.set_timer(
            ValleyElectricityTimer(
                enabled=trait.enabled,
                start_hour=desired_time.hour,
                start_minute=desired_time.minute,
                end_hour=trait.end_hour,
                end_minute=trait.end_minute,
            )
        ),
        get_value=lambda trait: datetime.time(
            hour=trait.start_hour, minute=trait.start_minute
        ),
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
    RoborockTimeDescription(
        key="off_peak_end",
        translation_key="off_peak_end",
        trait=lambda api: api.valley_electricity_timer,
        update_value=lambda trait, desired_time: trait.set_timer(
            ValleyElectricityTimer(
                enabled=trait.enabled,
                start_hour=trait.start_hour,
                start_minute=trait.start_minute,
                end_hour=desired_time.hour,
                end_minute=desired_time.minute,
            )
        ),
        get_value=lambda trait: datetime.time(
            hour=trait.end_hour, minute=trait.end_minute
        ),
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RoborockConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Roborock time platform."""
    async_add_entities(
        [
            RoborockTimeEntity(
                f"{description.key}_{coordinator.duid_slug}",
                coordinator,
                description,
                trait,
            )
            for coordinator in config_entry.runtime_data.v1
            for description in TIME_DESCRIPTIONS
            if (trait := description.trait(coordinator.properties_api)) is not None
        ]
    )


class RoborockTimeEntity(RoborockEntityV1, TimeEntity):
    """A class to let you set options on a Roborock vacuum where the potential options are fixed."""

    entity_description: RoborockTimeDescription

    def __init__(
        self,
        unique_id: str,
        coordinator: RoborockDataUpdateCoordinator,
        entity_description: RoborockTimeDescription,
        trait: Any,
    ) -> None:
        """Create a time entity."""
        self.entity_description = entity_description
        super().__init__(
            unique_id, coordinator.device_info, api=coordinator.properties_api.command
        )
        self._trait = trait

    @property
    def native_value(self) -> time | None:
        """Return the value reported by the time."""
        return self.entity_description.get_value(self._trait)

    async def async_set_value(self, value: time) -> None:
        """Set the time."""
        try:
            await self.entity_description.update_value(self._trait, value)
        except RoborockException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="update_options_failed",
            ) from err
