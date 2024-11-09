"""Ecovacs number module."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic

from deebot_client.capabilities import CapabilitySet
from deebot_client.events import CleanCountEvent, CutDirectionEvent, VolumeEvent

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import DEGREE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import EcovacsConfigEntry
from .entity import (
    EcovacsCapabilityEntityDescription,
    EcovacsDescriptionEntity,
    EcovacsEntity,
    EventT,
)
from .util import get_supported_entitites


@dataclass(kw_only=True, frozen=True)
class EcovacsNumberEntityDescription(
    NumberEntityDescription,
    EcovacsCapabilityEntityDescription,
    Generic[EventT],
):
    """Ecovacs number entity description."""

    native_max_value_fn: Callable[[EventT], float | int | None] = lambda _: None
    value_fn: Callable[[EventT], float | None]


ENTITY_DESCRIPTIONS: tuple[EcovacsNumberEntityDescription, ...] = (
    EcovacsNumberEntityDescription[VolumeEvent](
        capability_fn=lambda caps: caps.settings.volume,
        value_fn=lambda e: e.volume,
        native_max_value_fn=lambda e: e.maximum,
        key="volume",
        translation_key="volume",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
        native_min_value=0,
        native_max_value=10,
        native_step=1.0,
    ),
    EcovacsNumberEntityDescription[CutDirectionEvent](
        capability_fn=lambda caps: caps.settings.cut_direction,
        value_fn=lambda e: e.angle,
        key="cut_direction",
        translation_key="cut_direction",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
        native_min_value=0,
        native_max_value=180,
        native_step=1.0,
        native_unit_of_measurement=DEGREE,
    ),
    EcovacsNumberEntityDescription[CleanCountEvent](
        capability_fn=lambda caps: caps.clean.count,
        value_fn=lambda e: e.count,
        key="clean_count",
        translation_key="clean_count",
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.CONFIG,
        native_min_value=1,
        native_max_value=4,
        native_step=1.0,
        mode=NumberMode.BOX,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EcovacsConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add entities for passed config_entry in HA."""
    controller = config_entry.runtime_data
    entities: list[EcovacsEntity] = get_supported_entitites(
        controller, EcovacsNumberEntity, ENTITY_DESCRIPTIONS
    )
    if entities:
        async_add_entities(entities)


class EcovacsNumberEntity(
    EcovacsDescriptionEntity[CapabilitySet[EventT, int]],
    NumberEntity,
):
    """Ecovacs number entity."""

    entity_description: EcovacsNumberEntityDescription

    async def async_added_to_hass(self) -> None:
        """Set up the event listeners now that hass is ready."""
        await super().async_added_to_hass()

        async def on_event(event: EventT) -> None:
            self._attr_native_value = self.entity_description.value_fn(event)
            if maximum := self.entity_description.native_max_value_fn(event):
                self._attr_native_max_value = maximum
            self.async_write_ha_state()

        self._subscribe(self._capability.event, on_event)

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        await self._device.execute_command(self._capability.set(int(value)))
