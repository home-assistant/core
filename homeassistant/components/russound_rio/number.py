"""Support for Russound number entities."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from aiorussound.rio import Controller, ZoneControlSurface

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import RussoundConfigEntry
from .entity import RussoundBaseEntity, command

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class RussoundZoneNumberEntityDescription(NumberEntityDescription):
    """Describes Russound number entities."""

    value_fn: Callable[[ZoneControlSurface], float]
    set_value_fn: Callable[[ZoneControlSurface, float], Awaitable[None]]


CONTROL_ENTITIES: tuple[RussoundZoneNumberEntityDescription, ...] = (
    RussoundZoneNumberEntityDescription(
        key="balance",
        translation_key="balance",
        native_min_value=-10,
        native_max_value=10,
        native_step=1,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda zone: zone.balance,
        set_value_fn=lambda zone, value: zone.set_balance(int(value)),
    ),
    RussoundZoneNumberEntityDescription(
        key="bass",
        translation_key="bass",
        native_min_value=-10,
        native_max_value=10,
        native_step=1,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda zone: zone.bass,
        set_value_fn=lambda zone, value: zone.set_bass(int(value)),
    ),
    RussoundZoneNumberEntityDescription(
        key="treble",
        translation_key="treble",
        native_min_value=-10,
        native_max_value=10,
        native_step=1,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda zone: zone.treble,
        set_value_fn=lambda zone, value: zone.set_treble(int(value)),
    ),
    RussoundZoneNumberEntityDescription(
        key="turn_on_volume",
        translation_key="turn_on_volume",
        native_min_value=0,
        native_max_value=100,
        native_step=2,
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda zone: zone.turn_on_volume * 2,
        set_value_fn=lambda zone, value: zone.set_turn_on_volume(int(value / 2)),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RussoundConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Russound number entities based on a config entry."""
    client = entry.runtime_data
    async_add_entities(
        RussoundNumberEntity(controller, zone_id, description)
        for controller in client.controllers.values()
        for zone_id in controller.zones
        for description in CONTROL_ENTITIES
    )


class RussoundNumberEntity(RussoundBaseEntity, NumberEntity):
    """Defines a Russound number entity."""

    entity_description: RussoundZoneNumberEntityDescription

    def __init__(
        self,
        controller: Controller,
        zone_id: int,
        description: RussoundZoneNumberEntityDescription,
    ) -> None:
        """Initialize a Russound number entity."""
        super().__init__(controller, zone_id)
        self.entity_description = description
        self._attr_unique_id = (
            f"{self._primary_mac_address}-{self._zone.device_str}-{description.key}"
        )

    @property
    def native_value(self) -> float:
        """Return the native value of the entity."""
        return float(self.entity_description.value_fn(self._zone))

    @command
    async def async_set_native_value(self, value: float) -> None:
        """Set the value."""
        await self.entity_description.set_value_fn(self._zone, value)
