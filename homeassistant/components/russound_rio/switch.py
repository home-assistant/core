"""Support for Russound RIO switch entities."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from aiorussound.rio import Controller, ZoneControlSurface

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import RussoundConfigEntry
from .entity import RussoundBaseEntity, command

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class RussoundZoneSwitchEntityDescription(SwitchEntityDescription):
    """Describes Russound RIO switch entity description."""

    value_fn: Callable[[ZoneControlSurface], bool]
    set_value_fn: Callable[[ZoneControlSurface, bool], Awaitable[None]]


CONTROL_ENTITIES: tuple[RussoundZoneSwitchEntityDescription, ...] = (
    RussoundZoneSwitchEntityDescription(
        key="loudness",
        translation_key="loudness",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda zone: zone.loudness,
        set_value_fn=lambda zone, value: zone.set_loudness(value),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RussoundConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Russound RIO switch entities based on a config entry."""
    client = entry.runtime_data
    async_add_entities(
        RussoundSwitchEntity(controller, zone_id, description)
        for controller in client.controllers.values()
        for zone_id in controller.zones
        for description in CONTROL_ENTITIES
    )


class RussoundSwitchEntity(RussoundBaseEntity, SwitchEntity):
    """Defines a Russound RIO switch entity."""

    entity_description: RussoundZoneSwitchEntityDescription

    def __init__(
        self,
        controller: Controller,
        zone_id: int,
        description: RussoundZoneSwitchEntityDescription,
    ) -> None:
        """Initialize Russound RIO switch."""
        super().__init__(controller, zone_id)
        self.entity_description = description
        self._attr_unique_id = (
            f"{self._primary_mac_address}-{self._zone.device_str}-{description.key}"
        )

    @property
    def is_on(self) -> bool:
        """Return the state of the switch."""
        return self.entity_description.value_fn(self._zone)

    @command
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.entity_description.set_value_fn(self._zone, True)

    @command
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.entity_description.set_value_fn(self._zone, False)
