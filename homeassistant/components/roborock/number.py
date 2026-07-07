"""Support for Roborock number."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import logging
from typing import Any, override

from roborock.devices.traits.v1 import PropertiesApi
from roborock.exceptions import RoborockException

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import (
    RoborockConfigEntry,
    RoborockCoordinatorType,
    RoborockDataUpdateCoordinator,
)
from .entity import RoborockEntityV1

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class RoborockNumberDescription(NumberEntityDescription):
    """Class to describe a Roborock number entity."""

    trait: Callable[[PropertiesApi], Any | None]
    """Function to determine if number entity is supported by the device."""

    get_value: Callable[[Any], float | None]
    """Function to get the value from the trait."""

    set_value: Callable[[Any, float], Coroutine[Any, Any, None]]
    """Function to set the value on the trait."""


NUMBER_DESCRIPTIONS: list[RoborockNumberDescription] = [
    RoborockNumberDescription(
        key="volume",
        translation_key="volume",
        native_min_value=0,
        native_max_value=100,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.CONFIG,
        trait=lambda api: api.sound_volume,
        get_value=lambda trait: (
            float(trait.volume) if trait.volume is not None else None
        ),
        set_value=lambda trait, value: trait.set_volume(int(value)),
    )
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RoborockConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Roborock number platform."""
    coordinators = config_entry.runtime_data

    @callback
    def async_add_coordinator_entities(
        coordinator: RoborockCoordinatorType,
    ) -> None:
        """Add entities for a specific coordinator."""
        if not isinstance(coordinator, RoborockDataUpdateCoordinator):
            return
        entities = [
            RoborockNumberEntity(
                f"{description.key}_{coordinator.duid_slug}",
                coordinator=coordinator,
                entity_description=description,
                trait=trait,
            )
            for description in NUMBER_DESCRIPTIONS
            if (trait := description.trait(coordinator.properties_api)) is not None
        ]
        async_add_entities(entities)

    for coordinator in coordinators.values():
        async_add_coordinator_entities(coordinator)

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            f"roborock_coordinator_added_{config_entry.entry_id}",
            async_add_coordinator_entities,
        )
    )


class RoborockNumberEntity(RoborockEntityV1, NumberEntity):
    """A class to set options on a Roborock vacuum with fixed options."""

    entity_description: RoborockNumberDescription

    def __init__(
        self,
        unique_id: str,
        coordinator: RoborockDataUpdateCoordinator,
        entity_description: RoborockNumberDescription,
        trait: Any,
    ) -> None:
        """Create a number entity."""
        self.entity_description = entity_description
        super().__init__(
            unique_id, coordinator.device_info, api=coordinator.properties_api.command
        )
        self._trait = trait

    @property
    @override
    def native_value(self) -> float | None:
        """Get native value."""
        return self.entity_description.get_value(self._trait)

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set number value."""
        try:
            await self.entity_description.set_value(self._trait, value)
        except RoborockException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="update_options_failed",
            ) from err
