"""Select platform for the Yoto integration."""

from collections.abc import Callable
from dataclasses import dataclass

from yoto_api import PlayerConfig, YotoPlayer, caps_for

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import YotoConfigEntry, YotoDataUpdateCoordinator
from .entity import YotoEntity

PARALLEL_UPDATES = 1

# The ambient light presets offered by the Yoto app. The app has written
# different hex values for the same preset over time, so reads recognise
# every known variant while writes use the current canonical value.
OPTION_TO_HEX = {
    "sky_blue": "#40bfd9",
    "apple_green": "#9eff00",
    "lilac": "#f57399",
    "tambourine_red": "#ff0000",
    "orange_peel": "#ff3900",
    "bumblebee_yellow": "#ff8500",
    "white": "#ffffff",
    "off": "#000000",
}

HEX_TO_OPTION = {
    "#41c0f0": "sky_blue",
    "#e6ff00": "apple_green",
    "#f72a69": "lilac",
    "#ff8c00": "orange_peel",
    "#ffb800": "bumblebee_yellow",
    "#0": "off",
    "off": "off",
} | {hex_value: option for option, hex_value in OPTION_TO_HEX.items()}


@dataclass(frozen=True, kw_only=True)
class YotoSelectEntityDescription(SelectEntityDescription):
    """Describes a Yoto select entity.

    ``config_field`` is the ``set_player_config`` kwarg written on change.
    """

    value_fn: Callable[[PlayerConfig], str | None]
    config_field: str


SELECTS: tuple[YotoSelectEntityDescription, ...] = (
    YotoSelectEntityDescription(
        key="day_ambient_color",
        translation_key="day_ambient_color",
        options=list(OPTION_TO_HEX),
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda config: config.day_ambient_colour,
        config_field="day_ambient_colour",
    ),
    YotoSelectEntityDescription(
        key="night_ambient_color",
        translation_key="night_ambient_color",
        options=list(OPTION_TO_HEX),
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda config: config.night_ambient_colour,
        config_field="night_ambient_colour",
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


class YotoSelect(YotoEntity, SelectEntity):
    """Representation of a Yoto ambient light colour preset."""

    entity_description: YotoSelectEntityDescription

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
        """Return the configured preset, None for an unrecognised colour."""
        value = self.entity_description.value_fn(self.player.info.config)
        if value is None:
            return None
        return HEX_TO_OPTION.get(value.lower())

    async def async_select_option(self, option: str) -> None:
        """Write the preset's colour to the player config."""
        await self._async_set_config(
            **{self.entity_description.config_field: OPTION_TO_HEX[option]}
        )
