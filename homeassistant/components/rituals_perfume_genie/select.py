"""Support for Rituals Perfume Genie numbers."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import override

from ritualsgenie import Attribute, RitualsGenie, RoomSize

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory, UnitOfArea
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import RitualsConfigEntry, RitualsData, RitualsDataUpdateCoordinator
from .entity import DiffuserEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class RitualsSelectEntityDescription(SelectEntityDescription):
    """Class describing Rituals select entities."""

    current_fn: Callable[[RitualsData], str | None]
    select_fn: Callable[[RitualsGenie, str, str], Awaitable[None]]


def _room_size(square_meters: str) -> RoomSize:
    """Return the room size category of one of the options."""
    return next(size for size in RoomSize if size.square_meters == int(square_meters))


ENTITY_DESCRIPTIONS = (
    RitualsSelectEntityDescription(
        key="room_size_square_meter",
        translation_key="room_size_square_meter",
        unit_of_measurement=UnitOfArea.SQUARE_METERS,
        entity_category=EntityCategory.CONFIG,
        options=["15", "30", "60", "100"],
        current_fn=lambda data: (
            str(data.hub.room_size.square_meters) if data.hub.room_size else None
        ),
        select_fn=lambda client, hub_hash, value: client.set_room_size_category(
            hub_hash, _room_size(value)
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RitualsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the diffuser select entities."""
    coordinators = config_entry.runtime_data

    async_add_entities(
        RitualsSelectEntity(coordinator, description)
        for coordinator in coordinators.values()
        for description in ENTITY_DESCRIPTIONS
    )


class RitualsSelectEntity(DiffuserEntity, SelectEntity):
    """Representation of a diffuser select entity."""

    entity_description: RitualsSelectEntityDescription

    def __init__(
        self,
        coordinator: RitualsDataUpdateCoordinator,
        description: RitualsSelectEntityDescription,
    ) -> None:
        """Initialize the diffuser room size select entity."""
        super().__init__(coordinator, description)
        self._attr_entity_registry_enabled_default = (
            self.coordinator.data.hub.has_battery
        )

    @property
    @override
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        return self.entity_description.current_fn(self.coordinator.data)

    @override
    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.entity_description.select_fn(
            self.coordinator.client, self.coordinator.hub_hash, option
        )

        # Keep the new value until the next update, like the device has it now.
        attribute_values = self.coordinator.data.hub.attribute_values
        attribute_values[Attribute.ROOM_SIZE] = str(int(_room_size(option)))
        self.async_write_ha_state()
