"""Light platform for the Yoto integration."""

from typing import Any

from yoto_api import YotoError, YotoPlayer, caps_for

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
    LightEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import YotoConfigEntry, YotoDataUpdateCoordinator
from .entity import YotoEntity

PARALLEL_UPDATES = 1

AMBIENT_LIGHT = LightEntityDescription(
    key="ambient_light",
    translation_key="ambient_light",
)


def _parse_colour(value: str | None) -> tuple[int, int, int] | None:
    """Parse a ``#rrggbb``/``0xrrggbb`` colour into an RGB tuple."""
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
        YotoAmbientLight(coordinator, player)
        for player in coordinator.client.players.values()
        if caps_for(player.device).has_ambient_light
    )


class YotoAmbientLight(YotoEntity, LightEntity):
    """The player's ambient light (nightlight).

    The lamp has a single colour channel and no separate brightness, so
    brightness is folded into the RGB value: the current colour is
    reported as full-brightness RGB scaled down by a brightness equal to
    its brightest channel.
    """

    entity_description = AMBIENT_LIGHT
    _attr_color_mode = ColorMode.RGB
    _attr_supported_color_modes = {ColorMode.RGB}

    def __init__(
        self,
        coordinator: YotoDataUpdateCoordinator,
        player: YotoPlayer,
    ) -> None:
        """Initialize the light."""
        super().__init__(coordinator, player)
        self._attr_unique_id = f"{player.id}_ambient_light"

    @property
    def _rgb(self) -> tuple[int, int, int] | None:
        """Return the current lamp colour, None when off."""
        rgb = _parse_colour(self.player.status.nightlight_mode)
        if rgb is None or max(rgb) == 0:
            return None
        return rgb

    @property
    def is_on(self) -> bool:
        """Return True if the ambient light is lit."""
        return self._rgb is not None

    @property
    def brightness(self) -> int | None:
        """Return the brightness derived from the brightest channel."""
        if (rgb := self._rgb) is None:
            return None
        return max(rgb)

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the current colour scaled to full brightness."""
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
        await self._async_set_ambients(red, green, blue)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the ambient light off."""
        await self._async_set_ambients(0, 0, 0)

    async def _async_set_ambients(self, red: int, green: int, blue: int) -> None:
        """Send the lamp colour and ask for a status push to confirm it."""
        client = self.coordinator.client
        try:
            await client.set_ambients(self._player_id, red, green, blue)
            # The firmware does not push data/status spontaneously; request a
            # snapshot so the new lamp state lands via the MQTT callback.
            await client.request_player_status(self._player_id)
        except YotoError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"error": str(err)},
            ) from err
