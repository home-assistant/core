"""Binary sensor module."""

from collections.abc import Callable
from dataclasses import dataclass

from deebot_client.capabilities import CapabilityEvent
from deebot_client.events.base import Event
from deebot_client.events.water_info import MopAttachedEvent

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import EcovacsConfigEntry
from .entity import EcovacsCapabilityEntityDescription, EcovacsDescriptionEntity
from .util import get_supported_entities


@dataclass(kw_only=True, frozen=True)
class EcovacsBinarySensorEntityDescription[EventT: Event](
    BinarySensorEntityDescription,
    EcovacsCapabilityEntityDescription,
):
    """Class describing Deebot binary sensor entity."""

    value_fn: Callable[[EventT], bool | None]


ENTITY_DESCRIPTIONS: tuple[EcovacsBinarySensorEntityDescription, ...] = (
    EcovacsBinarySensorEntityDescription[MopAttachedEvent](
        capability_fn=lambda caps: caps.water.mop_attached if caps.water else None,
        value_fn=lambda e: e.value,
        key="water_mop_attached",
        translation_key="water_mop_attached",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EcovacsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add entities for passed config_entry in HA."""
    async_add_entities(
        get_supported_entities(
            config_entry.runtime_data, EcovacsBinarySensor, ENTITY_DESCRIPTIONS
        )
    )


class EcovacsBinarySensor[EventT: Event](
    EcovacsDescriptionEntity[CapabilityEvent[EventT]],
    BinarySensorEntity,
):
    """Ecovacs binary sensor."""

    entity_description: EcovacsBinarySensorEntityDescription

    async def async_added_to_hass(self) -> None:
        """Set up the event listeners now that hass is ready."""
        await super().async_added_to_hass()

        async def on_event(event: EventT) -> None:
            self._attr_is_on = self.entity_description.value_fn(event)
            self.async_write_ha_state()

        self._subscribe(self._capability.event, on_event)
