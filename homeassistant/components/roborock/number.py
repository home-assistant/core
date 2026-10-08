"""Support for Roborock number."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import logging
from typing import Any, override

from roborock.devices.traits.b01 import Q10PropertiesApi
from roborock.devices.traits.b01.q10 import SoundVolumeTrait
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
    RoborockB01Q10UpdateCoordinator,
    RoborockConfigEntry,
    RoborockCoordinatorType,
    RoborockDataUpdateCoordinator,
)
from .entity import RoborockCoordinatedEntityB01Q10, RoborockEntityV1

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


@dataclass(frozen=True, kw_only=True)
class RoborockNumberDescriptionQ10(NumberEntityDescription):
    """Class to describe a Roborock Q10 number entity."""

    trait: Callable[[Q10PropertiesApi], SoundVolumeTrait | None]
    """Function to get the trait backing the entity, if supported."""

    get_value: Callable[[SoundVolumeTrait], float | None]
    """Function to get the value from the trait."""

    set_value: Callable[[SoundVolumeTrait, float], Coroutine[Any, Any, None]]
    """Function to set the value on the trait."""


Q10_NUMBER_DESCRIPTIONS: list[RoborockNumberDescriptionQ10] = [
    RoborockNumberDescriptionQ10(
        key="volume",
        translation_key="volume",
        native_min_value=0,
        native_max_value=100,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.CONFIG,
        trait=lambda api: api.volume,
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
        entities: list[NumberEntity] = []
        if isinstance(coordinator, RoborockDataUpdateCoordinator):
            entities.extend(
                RoborockNumberEntity(
                    f"{description.key}_{coordinator.duid_slug}",
                    coordinator=coordinator,
                    entity_description=description,
                    trait=trait,
                )
                for description in NUMBER_DESCRIPTIONS
                if (trait := description.trait(coordinator.properties_api)) is not None
            )
        elif isinstance(coordinator, RoborockB01Q10UpdateCoordinator):
            entities.extend(
                RoborockNumberEntityQ10(
                    f"{description.key}_{coordinator.duid_slug}",
                    coordinator=coordinator,
                    entity_description=description,
                    trait=q10_trait,
                )
                for description in Q10_NUMBER_DESCRIPTIONS
                if (q10_trait := description.trait(coordinator.api)) is not None
            )
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


class RoborockNumberEntityQ10(RoborockCoordinatedEntityB01Q10, NumberEntity):
    """A class to set a numeric setting on a Roborock Q10 device."""

    entity_description: RoborockNumberDescriptionQ10
    coordinator: RoborockB01Q10UpdateCoordinator

    def __init__(
        self,
        unique_id: str,
        coordinator: RoborockB01Q10UpdateCoordinator,
        entity_description: RoborockNumberDescriptionQ10,
        trait: SoundVolumeTrait,
    ) -> None:
        """Create a number entity."""
        self.entity_description = entity_description
        self._trait = trait
        super().__init__(unique_id, coordinator)

    @override
    async def async_added_to_hass(self) -> None:
        """Register a trait listener for push-based state updates."""
        await super().async_added_to_hass()
        self.async_on_remove(self._trait.add_update_listener(self.async_write_ha_state))

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
