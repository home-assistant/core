"""Time platform for the Yoto integration."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import time

from yoto_api import PlayerConfig, YotoPlayer

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import YotoConfigEntry, YotoDataUpdateCoordinator
from .entity import YotoEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class YotoTimeEntityDescription(TimeEntityDescription):
    """Describes a Yoto time entity.

    ``config_field`` is the ``set_player_config`` kwarg written on change.
    """

    value_fn: Callable[[PlayerConfig], time | None]
    config_field: str


TIME_ENTITIES: tuple[YotoTimeEntityDescription, ...] = (
    YotoTimeEntityDescription(
        key="day_mode_start",
        translation_key="day_mode_start",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda config: config.day_time,
        config_field="day_time",
    ),
    YotoTimeEntityDescription(
        key="night_mode_start",
        translation_key="night_mode_start",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda config: config.night_time,
        config_field="night_time",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: YotoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Yoto time platform."""
    coordinator = entry.runtime_data
    async_add_entities(
        YotoTime(coordinator, player, description)
        for player in coordinator.client.players.values()
        for description in TIME_ENTITIES
    )


class YotoTime(YotoEntity, TimeEntity):
    """Representation of a Yoto player config time."""

    entity_description: YotoTimeEntityDescription

    def __init__(
        self,
        coordinator: YotoDataUpdateCoordinator,
        player: YotoPlayer,
        description: YotoTimeEntityDescription,
    ) -> None:
        """Initialize the time entity."""
        super().__init__(coordinator, player)
        self.entity_description = description
        self._attr_unique_id = f"{player.id}_{description.key}"

    @property
    def native_value(self) -> time | None:
        """Return the configured time."""
        return self.entity_description.value_fn(self.player.info.config)

    async def async_set_value(self, value: time) -> None:
        """Update the configured time."""
        await self._async_set_config(**{self.entity_description.config_field: value})
