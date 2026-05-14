"""Support for Russound RIO select entities."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from aiorussound.rio.client import Controller, ZoneControlSurface
from aiorussound.rio.models import PartyMode

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import RussoundConfigEntry
from .entity import RussoundBaseEntity, command

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class RussoundZoneSelectEntityDescription(SelectEntityDescription):
    """Describes Russound RIO select entity."""

    value_fn: Callable[[ZoneControlSurface], str | None]
    set_value_fn: Callable[[ZoneControlSurface, str], Awaitable[None]]


CONTROL_ENTITIES: tuple[RussoundZoneSelectEntityDescription, ...] = (
    RussoundZoneSelectEntityDescription(
        key="party_mode",
        translation_key="party_mode",
        options=[
            PartyMode.OFF.value.lower(),
            PartyMode.ON.value.lower(),
            PartyMode.MASTER.value.lower(),
        ],
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda zone: zone.party_mode.lower() if zone.party_mode else None,
        set_value_fn=lambda zone, value: zone.set_party_mode(PartyMode(value.upper())),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RussoundConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Russound RIO select entities based on a config entry."""
    client = entry.runtime_data
    async_add_entities(
        RussoundSelectEntity(controller, zone_id, description)
        for controller in client.controllers.values()
        for zone_id in controller.zones
        for description in CONTROL_ENTITIES
    )


class RussoundSelectEntity(RussoundBaseEntity, SelectEntity):
    """Defines a Russound RIO select entity."""

    entity_description: RussoundZoneSelectEntityDescription

    def __init__(
        self,
        controller: Controller,
        zone_id: int,
        description: RussoundZoneSelectEntityDescription,
    ) -> None:
        """Initialize Russound RIO select."""
        super().__init__(controller, zone_id)
        self.entity_description = description
        self._attr_unique_id = (
            f"{self._primary_mac_address}-{self._zone.device_str}-{description.key}"
        )

    @property
    def current_option(self) -> str | None:
        """Return the state of the select."""
        return self.entity_description.value_fn(self._zone)

    @command
    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.entity_description.set_value_fn(self._zone, option)
