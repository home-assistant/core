"""Support for Roborock number."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import logging
from typing import Any

from roborock.devices.traits.v1 import PropertiesApi
from roborock.exceptions import RoborockException

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import (
    RoborockB01Q10UpdateCoordinator,
    RoborockConfigEntry,
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

    get_value: Callable[[Any], float]
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
        get_value=lambda trait: float(trait.volume),
        set_value=lambda trait, value: trait.set_volume(int(value)),
    )
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RoborockConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Roborock number platform."""
    async_add_entities(
        [
            RoborockNumberEntity(
                f"{description.key}_{coordinator.duid_slug}",
                coordinator=coordinator,
                entity_description=description,
                trait=trait,
            )
            for coordinator in config_entry.runtime_data.v1
            for description in NUMBER_DESCRIPTIONS
            if (trait := description.trait(coordinator.properties_api)) is not None
        ]
    )
    async_add_entities(
        RoborockQ10VolumeNumberEntity(coordinator)
        for coordinator in config_entry.runtime_data.b01_q10
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
    def native_value(self) -> float | None:
        """Get native value."""
        return self.entity_description.get_value(self._trait)

    async def async_set_native_value(self, value: float) -> None:
        """Set number value."""
        try:
            await self.entity_description.set_value(self._trait, value)
        except RoborockException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="update_options_failed",
            ) from err


class RoborockQ10VolumeNumberEntity(RoborockCoordinatedEntityB01Q10, NumberEntity):
    """Speaker volume control for a Roborock Q10 (B01/ss07) device."""

    _attr_translation_key = "volume"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_entity_category = EntityCategory.CONFIG
    coordinator: RoborockB01Q10UpdateCoordinator

    def __init__(self, coordinator: RoborockB01Q10UpdateCoordinator) -> None:
        """Create a number entity."""
        super().__init__(f"volume_{coordinator.duid_slug}", coordinator)

    async def async_added_to_hass(self) -> None:
        """Register a trait listener for push-based state updates."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.api.volume.add_update_listener(self.async_write_ha_state)
        )

    @property
    def native_value(self) -> float | None:
        """Get native value."""
        volume = self.coordinator.api.volume.volume
        return float(volume) if volume is not None else None

    async def async_set_native_value(self, value: float) -> None:
        """Set the speaker volume."""
        try:
            await self.coordinator.api.volume.set_volume(int(value))
        except RoborockException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"command": "volume"},
            ) from err
