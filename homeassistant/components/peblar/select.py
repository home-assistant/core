"""Support for Peblar selects."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from peblar import LedBrightness, Peblar, PeblarUserConfiguration, SmartChargingMode, SoundVolume

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import (
    PeblarConfigEntry,
    PeblarRuntimeData,
    PeblarUserConfigurationDataUpdateCoordinator,
)
from .entity import PeblarEntity
from .helpers import peblar_exception_handler

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class PeblarSelectEntityDescription(SelectEntityDescription):
    """Class describing Peblar select entities."""

    has_fn: Callable[[PeblarRuntimeData], bool] = lambda x: True
    current_fn: Callable[[PeblarUserConfiguration], str | None]
    select_fn: Callable[[Peblar, str], Awaitable[Any]]


DESCRIPTIONS = [
    PeblarSelectEntityDescription(
        key="smart_charging",
        translation_key="smart_charging",
        entity_category=EntityCategory.CONFIG,
        options=[
            "default",
            "fast_solar",
            "pure_solar",
            "scheduled",
            "smart_solar",
        ],
        current_fn=lambda x: x.smart_charging.value if x.smart_charging else None,
        select_fn=lambda x, mode: x.smart_charging(SmartChargingMode(mode)),
    ),
    PeblarSelectEntityDescription(
        key="buzzer_volume",
        translation_key="buzzer_volume",
        entity_category=EntityCategory.CONFIG,
        has_fn=lambda x: x.system_information.hardware_has_buzzer,
        options=[v.name.lower() for v in SoundVolume],
        current_fn=lambda x: x.buzzer_volume.name.lower() if x.buzzer_volume else None,
        select_fn=lambda x, option: x.set_buzzer_volume(
            volume=SoundVolume[option.upper()]
        ),
    ),
    PeblarSelectEntityDescription(
        key="led_brightness",
        translation_key="led_brightness",
        entity_category=EntityCategory.CONFIG,
        has_fn=lambda x: x.system_information.hardware_has_led,
        options=[v.name.lower() for v in LedBrightness],
        current_fn=lambda x: (
            x.led_brightness.name.lower() if x.led_brightness is not None else None
        ),
        select_fn=lambda x, option: x.set_led_brightness(
            brightness=LedBrightness[option.upper()]
        ),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PeblarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Peblar select based on a config entry."""
    async_add_entities(
        PeblarSelectEntity(
            entry=entry,
            coordinator=entry.runtime_data.user_configuration_coordinator,
            description=description,
        )
        for description in DESCRIPTIONS
        if description.has_fn(entry.runtime_data)
    )


class PeblarSelectEntity(
    PeblarEntity[PeblarUserConfigurationDataUpdateCoordinator],
    SelectEntity,
):
    """Defines a Peblar select entity."""

    entity_description: PeblarSelectEntityDescription

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        return self.entity_description.current_fn(self.coordinator.data)

    @peblar_exception_handler
    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.entity_description.select_fn(self.coordinator.peblar, option)
        await self.coordinator.async_request_refresh()
