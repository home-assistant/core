"""Number platform for the Yoto integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from yoto_api import PlayerConfig, YotoPlayer

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import YotoConfigEntry, YotoDataUpdateCoordinator
from .entity import YotoConfigEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class YotoNumberEntityDescription(NumberEntityDescription):
    """Describes a Yoto number entity.

    ``config_field`` is the ``set_player_config`` kwarg written on change.
    ``available_fn`` hides the entity while the value is managed automatically.
    """

    value_fn: Callable[[PlayerConfig], int | None]
    config_field: str
    available_fn: Callable[[PlayerConfig], bool] = lambda config: True


NUMBERS: tuple[YotoNumberEntityDescription, ...] = (
    YotoNumberEntityDescription(
        key="day_mode_brightness",
        translation_key="day_mode_brightness",
        entity_category=EntityCategory.CONFIG,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.SLIDER,
        value_fn=lambda config: config.day_display_brightness,
        config_field="day_display_brightness",
        available_fn=lambda config: not config.day_display_brightness_auto,
    ),
    YotoNumberEntityDescription(
        key="night_mode_brightness",
        translation_key="night_mode_brightness",
        entity_category=EntityCategory.CONFIG,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.SLIDER,
        value_fn=lambda config: config.night_display_brightness,
        config_field="night_display_brightness",
        available_fn=lambda config: not config.night_display_brightness_auto,
    ),
    YotoNumberEntityDescription(
        key="day_mode_max_volume",
        translation_key="day_mode_max_volume",
        entity_category=EntityCategory.CONFIG,
        native_min_value=0,
        native_max_value=16,
        native_step=1,
        mode=NumberMode.SLIDER,
        value_fn=lambda config: config.day_max_volume_limit,
        config_field="day_max_volume_limit",
    ),
    YotoNumberEntityDescription(
        key="night_mode_max_volume",
        translation_key="night_mode_max_volume",
        entity_category=EntityCategory.CONFIG,
        native_min_value=0,
        native_max_value=16,
        native_step=1,
        mode=NumberMode.SLIDER,
        value_fn=lambda config: config.night_max_volume_limit,
        config_field="night_max_volume_limit",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: YotoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Yoto number platform."""
    coordinator = entry.runtime_data
    known_players: set[str] = set()

    @callback
    def _add_players() -> None:
        current = set(coordinator.data)
        new_players = current - known_players
        known_players.clear()
        known_players.update(current)
        if new_players:
            async_add_entities(
                YotoNumber(coordinator, coordinator.data[player_id], description)
                for player_id in new_players
                for description in NUMBERS
            )

    entry.async_on_unload(coordinator.async_add_listener(_add_players))
    _add_players()


class YotoNumber(YotoConfigEntity, NumberEntity):
    """Representation of a Yoto player config number."""

    entity_description: YotoNumberEntityDescription

    def __init__(
        self,
        coordinator: YotoDataUpdateCoordinator,
        player: YotoPlayer,
        description: YotoNumberEntityDescription,
    ) -> None:
        """Initialize the number."""
        super().__init__(coordinator, player)
        self.entity_description = description
        self._attr_unique_id = f"{player.id}_{description.key}"

    @property
    @override
    def available(self) -> bool:
        """Return if the entity is available."""
        return super().available and self.entity_description.available_fn(
            self.player.info.config
        )

    @property
    @override
    def native_value(self) -> float | None:
        """Return the configured value."""
        return self.entity_description.value_fn(self.player.info.config)

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Update the configured value."""
        await self._async_set_config(
            **{self.entity_description.config_field: int(value)}
        )
