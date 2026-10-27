"""The Twinkly light component."""

import logging
from typing import Any, override

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
    EFFECT_OFF,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DEV_LED_PROFILE, DEV_PROFILE_RGB, DEV_PROFILE_RGBW
from .coordinator import TwinklyConfigEntry, TwinklyCoordinator
from .entity import TwinklyEntity

_LOGGER = logging.getLogger(__name__)

# "off" is the standard no-effect value. "None" is the old name some scenes still use.
NO_EFFECT_OPTIONS = {EFFECT_OFF, "None", "none"}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: TwinklyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Setups an entity from a config entry (UI config flow)."""
    entity = TwinklyLight(config_entry.runtime_data)

    async_add_entities([entity], update_before_add=True)


class TwinklyLight(TwinklyEntity, LightEntity):
    """Implementation of the light for the Twinkly service."""

    _attr_name = None
    _attr_translation_key = "light"

    def __init__(self, coordinator: TwinklyCoordinator) -> None:
        """Initialize a TwinklyLight entity."""
        super().__init__(coordinator)
        device_info = coordinator.data.device_info
        self._attr_unique_id = device_info["mac"]

        if device_info.get(DEV_LED_PROFILE) == DEV_PROFILE_RGBW:
            self._attr_supported_color_modes = {ColorMode.RGBW}
            self._attr_color_mode = ColorMode.RGBW
            self._attr_rgbw_color = (255, 255, 255, 0)
        elif device_info.get(DEV_LED_PROFILE) == DEV_PROFILE_RGB:
            self._attr_supported_color_modes = {ColorMode.RGB}
            self._attr_color_mode = ColorMode.RGB
            self._attr_rgb_color = (255, 255, 255)
        else:
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
            self._attr_color_mode = ColorMode.BRIGHTNESS
        self.client = coordinator.client
        if coordinator.supports_effects:
            self._attr_supported_features = LightEntityFeature.EFFECT
        self._update_attr()

    @property
    @override
    def effect(self) -> str | None:
        """Return the current effect."""
        # The device keeps reporting the last movie id while showing a solid color.
        if self.coordinator.data.current_mode != "movie":
            return EFFECT_OFF
        if (current_movie_id := self.coordinator.data.current_movie) is not None:
            movie_name = self.coordinator.data.movies.get(current_movie_id)
            if movie_name is not None:
                return f"{current_movie_id} {movie_name}"
        return None

    @property
    @override
    def effect_list(self) -> list[str]:
        """Return the list of saved effects."""
        return [EFFECT_OFF] + [
            f"{identifier} {name}"
            for identifier, name in self.coordinator.data.movies.items()
        ]

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn device on."""
        current_mode = self.coordinator.data.current_mode
        supports_effects = bool(LightEntityFeature.EFFECT & self.supported_features)
        effect = kwargs.get(ATTR_EFFECT) if supports_effects else None
        # A scene stores the light's color next to the movie it plays, so a
        # movie wins over a color sent in the same call.
        movie = None if effect in NO_EFFECT_OPTIONS else effect

        if ATTR_BRIGHTNESS in kwargs:
            brightness = round(kwargs[ATTR_BRIGHTNESS] / 2.55)

            # If brightness is 0, the twinkly will only "disable" the brightness,
            # which means that it will be 100%.
            if brightness == 0:
                await self.client.turn_off()
                return

            await self.client.set_brightness(brightness)

        color: tuple[int, ...] | None
        if ATTR_RGBW_COLOR in kwargs:
            red, green, blue, white = kwargs[ATTR_RGBW_COLOR]
            color = (white, red, green, blue)
            same_color = kwargs[ATTR_RGBW_COLOR] == self._attr_rgbw_color
        else:
            color = kwargs.get(ATTR_RGB_COLOR)
            same_color = color == self._attr_rgb_color

        if color is not None and movie is None:
            if supports_effects:
                # A movie can play over the stored color, so the mode is checked too.
                if not same_color or current_mode != "color":
                    await self.client.interview()
                    await self.client.set_static_colour(color)
                    await self.client.set_mode("color")
                    self.client.default_mode = "color"
                    current_mode = "color"
            elif not same_color:
                await self.client.interview()
                await self.client.set_cycle_colours(color)
                await self.client.set_mode("movie")
                self.client.default_mode = "movie"
            if ATTR_RGBW_COLOR in kwargs:
                self._attr_rgbw_color = kwargs[ATTR_RGBW_COLOR]
            else:
                self._attr_rgb_color = kwargs[ATTR_RGB_COLOR]

        if movie is not None:
            # Skip only when this movie is already playing. A solid color
            # keeps the last movie id, so the same effect is sent again.
            movie_id = int(movie.split(" ")[0])
            if (
                current_mode != "movie"
                or self.coordinator.data.current_movie is None
                or movie_id != self.coordinator.data.current_movie
            ):
                await self.client.interview()
                await self.client.set_current_movie(movie_id)
                await self.client.set_mode("movie")
                self.client.default_mode = "movie"
        elif effect is not None and current_mode != "color":
            await self.client.interview()
            await self.client.set_mode("color")
            self.client.default_mode = "color"
        if not self._attr_is_on:
            await self.client.turn_on()
        await self.coordinator.async_refresh()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn device off."""
        await self.client.turn_off()
        await self.coordinator.async_refresh()

    def _update_attr(self) -> None:
        """Update the entity attributes."""
        self._attr_is_on = self.coordinator.data.is_on
        self._attr_brightness = self.coordinator.data.brightness
        if (color := self.coordinator.data.color) is None:
            return
        if self._attr_color_mode == ColorMode.RGB:
            self._attr_rgb_color = (color.red, color.green, color.blue)
        elif self._attr_color_mode == ColorMode.RGBW and color.white is not None:
            self._attr_rgbw_color = (color.red, color.green, color.blue, color.white)

    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attr()
        super()._handle_coordinator_update()
