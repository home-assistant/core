"""Support for Rituals Perfume Genie numbers."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import override

from ritualsgenie import Attribute, RitualsGenie, RitualsGenieHub, RoomSize

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory, UnitOfArea
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import RitualsConfigEntry, RitualsHubsCoordinator
from .entity import DiffuserEntity, async_add_diffusers, rituals_action

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class RitualsSelectEntityDescription(SelectEntityDescription):
    """Class describing Rituals select entities."""

    current_fn: Callable[[RitualsGenieHub], str | None]
    select_fn: Callable[[RitualsGenie, RitualsGenieHub, str], Awaitable[None]]


def _room_size(square_meters: str) -> RoomSize:
    """Return the room size category of one of the options."""
    return next(size for size in RoomSize if size.square_meters == int(square_meters))


async def _set_room_size(
    client: RitualsGenie, hub: RitualsGenieHub, value: str
) -> None:
    """Set the room size, in square meters as well when the diffuser has those.

    Rituals doesn't derive one from the other, and the app shows the square
    meters. Without both, the app tells a different room size.
    """
    if hub.attributes.get(Attribute.ROOM_SQUARE_METERS):
        await client.set_room_square_meters(hub.hash, int(value))
    else:
        await client.set_room_size_category(hub.hash, _room_size(value))


ENTITY_DESCRIPTIONS = (
    RitualsSelectEntityDescription(
        key="room_size_square_meter",
        translation_key="room_size_square_meter",
        unit_of_measurement=UnitOfArea.SQUARE_METERS,
        entity_category=EntityCategory.CONFIG,
        options=["15", "30", "60", "100"],
        current_fn=lambda hub: (
            str(hub.room_size.square_meters) if hub.room_size else None
        ),
        select_fn=_set_room_size,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RitualsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the diffuser select entities."""
    hubs = config_entry.runtime_data.hubs

    @callback
    def add_diffusers(hublots: list[str]) -> None:
        async_add_entities(
            RitualsSelectEntity(hubs, hublot, description)
            for hublot in hublots
            for description in ENTITY_DESCRIPTIONS
        )

    async_add_diffusers(config_entry, add_diffusers)


class RitualsSelectEntity(DiffuserEntity, SelectEntity):
    """Representation of a diffuser select entity."""

    entity_description: RitualsSelectEntityDescription

    def __init__(
        self,
        coordinator: RitualsHubsCoordinator,
        hublot: str,
        description: RitualsSelectEntityDescription,
    ) -> None:
        """Initialize the diffuser room size select entity."""
        super().__init__(coordinator, hublot, description)
        self._attr_entity_registry_enabled_default = self.hub.has_battery

    @property
    @override
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        return self.entity_description.current_fn(self.hub)

    @override
    @rituals_action
    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.entity_description.select_fn(
            self.coordinator.client, self.hub, option
        )

        # Keep the new value until the next update, like the device has it now.
        attribute_values = self.hub.attribute_values
        attribute_values[Attribute.ROOM_SIZE] = str(int(_room_size(option)))
        if self.hub.attributes.get(Attribute.ROOM_SQUARE_METERS):
            attribute_values[Attribute.ROOM_SQUARE_METERS] = option
        self.async_write_ha_state()
