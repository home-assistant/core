"""Ecovacs number module."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from deebot_client.capabilities import CapabilityNumber, CapabilitySet
from deebot_client.device import Device
from deebot_client.events import CleanCountEvent, CutDirectionEvent, VolumeEvent
from deebot_client.events.base import Event
from deebot_client.events.water_info import WaterCustomAmountEvent

from homeassistant.components.number import (
    EntityDescription,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import DEGREE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import EcovacsConfigEntry
from .entity import (
    EcovacsCapabilityEntityDescription,
    EcovacsDescriptionEntity,
    EcovacsEntity,
)
from .util import get_supported_entities


@dataclass(kw_only=True, frozen=True)
class EcovacsNumberEntityDescription[EventT: Event](
    NumberEntityDescription,
    EcovacsCapabilityEntityDescription,
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
    EcovacsNumberEntityDescription[WaterCustomAmountEvent](
        capability_fn=lambda caps: (
            caps.water.amount
            if caps.water and isinstance(caps.water.amount, CapabilityNumber)
            else None
        ),
        value_fn=lambda e: e.value,
        key="water_amount",
        translation_key="water_amount",
        entity_category=EntityCategory.CONFIG,
        native_step=1.0,
        mode=NumberMode.BOX,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EcovacsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add entities for passed config_entry in HA."""
    controller = config_entry.runtime_data
    entities: list[EcovacsEntity] = get_supported_entities(
        controller, EcovacsNumberEntity, ENTITY_DESCRIPTIONS
    )
    if entities:
        async_add_entities(entities)


class EcovacsNumberEntity[EventT: Event](
    EcovacsDescriptionEntity[CapabilitySet[EventT, [int]]],
    NumberEntity,
):
    """Ecovacs number entity."""

    entity_description: EcovacsNumberEntityDescription

    def __init__(
        self,
        device: Device,
        capability: CapabilitySet[EventT, [int]],
        entity_description: EntityDescription,
    ) -> None:
        """Initialize entity."""
        super().__init__(device, capability, entity_description)
        if isinstance(capability, CapabilityNumber):
            self._attr_native_min_value = capability.min
            self._attr_native_max_value = capability.max

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
