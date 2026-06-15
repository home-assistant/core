"""Select platform for the Yoto integration."""

from collections.abc import Callable
from dataclasses import dataclass

from yoto_api import AMBIENT_PRESET_KEYS, PlayerConfig, YotoPlayer, caps_for

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import YotoConfigEntry, YotoDataUpdateCoordinator
from .entity import YotoConfigEntity

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class YotoSelectEntityDescription(SelectEntityDescription):
    """Describes a Yoto select entity.

    ``config_field`` is the ``set_player_config`` kwarg written on change.
    """

    value_fn: Callable[[PlayerConfig], str | None]
    config_field: str


SELECTS: tuple[YotoSelectEntityDescription, ...] = (
    YotoSelectEntityDescription(
        key="day_mode_color",
        translation_key="day_mode_color",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda config: config.day_ambient_preset,
        config_field="day_ambient_preset",
    ),
    YotoSelectEntityDescription(
        key="night_mode_color",
        translation_key="night_mode_color",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda config: config.night_ambient_preset,
        config_field="night_ambient_preset",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: YotoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Yoto select platform."""
    coordinator = entry.runtime_data
    async_add_entities(
        YotoSelect(coordinator, player, description)
        for player in coordinator.client.players.values()
        if caps_for(player.device).has_ambient_light
        for description in SELECTS
    )


class YotoSelect(YotoConfigEntity, SelectEntity):
    """Representation of a Yoto player config select."""

    entity_description: YotoSelectEntityDescription
    _attr_options = list(AMBIENT_PRESET_KEYS)

    def __init__(
        self,
        coordinator: YotoDataUpdateCoordinator,
        player: YotoPlayer,
        description: YotoSelectEntityDescription,
    ) -> None:
        """Initialize the select."""
        super().__init__(coordinator, player)
        self.entity_description = description
        self._attr_unique_id = f"{player.id}_{description.key}"

    @property
    def current_option(self) -> str | None:
        """Return the selected colour preset, or None for a custom value."""
        return self.entity_description.value_fn(self.player.info.config)

    async def async_select_option(self, option: str) -> None:
        """Update the configured colour preset."""
        await self._async_set_config(**{self.entity_description.config_field: option})
