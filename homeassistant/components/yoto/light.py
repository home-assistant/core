"""Light platform for the Yoto integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from yoto_api import PlayerConfig, YotoPlayer, caps_for

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
    LightEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import YotoConfigEntry, YotoDataUpdateCoordinator
from .entity import YotoEntity

PARALLEL_UPDATES = 1

OFF_COLOUR = "#000000"


@dataclass(frozen=True, kw_only=True)
class YotoLightEntityDescription(LightEntityDescription):
    """Describes a Yoto ambient light entity.

    ``config_field`` is the ``set_player_config`` kwarg written on change.
    """

    value_fn: Callable[[PlayerConfig], str | None]
    config_field: str


LIGHTS: tuple[YotoLightEntityDescription, ...] = (
    YotoLightEntityDescription(
        key="day_ambient_light",
        translation_key="day_ambient_light",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda config: config.day_ambient_colour,
        config_field="day_ambient_colour",
    ),
    YotoLightEntityDescription(
        key="night_ambient_light",
        translation_key="night_ambient_light",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda config: config.night_ambient_colour,
        config_field="night_ambient_colour",
    ),
)


def _parse_colour(value: str | None) -> tuple[int, int, int] | None:
    """Parse a ``#rrggbb`` config colour into an RGB tuple."""
    if value is None or value == "off":
        return None
    try:
        raw = int(value.removeprefix("#"), 16)
    except ValueError:
        return None
    return ((raw >> 16) & 0xFF, (raw >> 8) & 0xFF, raw & 0xFF)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: YotoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Yoto light platform."""
    coordinator = entry.runtime_data
    async_add_entities(
        YotoAmbientLight(coordinator, player, description)
        for player in coordinator.client.players.values()
        if caps_for(player.device).has_ambient_light
        for description in LIGHTS
    )


class YotoAmbientLight(YotoEntity, LightEntity):
    """Day/night ambient light colour stored in the player config.

    The player exposes a single colour per mode with no separate
    brightness channel, so brightness is folded into the RGB value:
    the stored colour is reported as full-brightness RGB scaled down
    by a brightness equal to its brightest channel.
    """

    entity_description: YotoLightEntityDescription
    _attr_color_mode = ColorMode.RGB
    _attr_supported_color_modes = {ColorMode.RGB}

    def __init__(
        self,
        coordinator: YotoDataUpdateCoordinator,
        player: YotoPlayer,
        description: YotoLightEntityDescription,
    ) -> None:
        """Initialize the light."""
        super().__init__(coordinator, player)
        self.entity_description = description
        self._attr_unique_id = f"{player.id}_{description.key}"

    @property
    def _rgb(self) -> tuple[int, int, int] | None:
        """Return the raw configured colour, None when unset or black."""
        rgb = _parse_colour(self.entity_description.value_fn(self.player.info.config))
        if rgb is None or max(rgb) == 0:
            return None
        return rgb

    @property
    def is_on(self) -> bool:
        """Return True if the ambient light colour is set."""
        return self._rgb is not None

    @property
    def brightness(self) -> int | None:
        """Return the brightness derived from the brightest channel."""
        if (rgb := self._rgb) is None:
            return None
        return max(rgb)

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the configured colour scaled to full brightness."""
        if (rgb := self._rgb) is None:
            return None
        scale = max(rgb)
        return (
            round(rgb[0] * 255 / scale),
            round(rgb[1] * 255 / scale),
            round(rgb[2] * 255 / scale),
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Set the ambient light colour."""
        rgb = kwargs.get(ATTR_RGB_COLOR) or self.rgb_color or (255, 255, 255)
        brightness = kwargs.get(ATTR_BRIGHTNESS, self.brightness or 255)
        red, green, blue = (round(channel * brightness / 255) for channel in rgb)
        await self._async_set_config(
            **{self.entity_description.config_field: f"#{red:02x}{green:02x}{blue:02x}"}
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the ambient light off."""
        await self._async_set_config(
            **{self.entity_description.config_field: OFF_COLOUR}
        )
