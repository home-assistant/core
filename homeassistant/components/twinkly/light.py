"""The Twinkly light component."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    ATTR_RGBW_COLOR,
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
    def effect(self) -> str | None:
        """Return the current effect."""
        if (current_movie_id := self.coordinator.data.current_movie) is not None:
            return (
                f"{current_movie_id} {self.coordinator.data.movies[current_movie_id]}"
            )
        return None

    @property
    def effect_list(self) -> list[str]:
        """Return the list of saved effects."""
        return [
            f"{identifier} {name}"
            for identifier, name in self.coordinator.data.movies.items()
        ]

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn device on."""
        if ATTR_BRIGHTNESS in kwargs:
            brightness = int(int(kwargs[ATTR_BRIGHTNESS]) / 2.55)

            # If brightness is 0, the twinkly will only "disable" the brightness,
            # which means that it will be 100%.
            if brightness == 0:
                await self.client.turn_off()
                return

            await self.client.set_brightness(brightness)

        if (
            ATTR_RGBW_COLOR in kwargs
            and kwargs[ATTR_RGBW_COLOR] != self._attr_rgbw_color
        ):
            await self.client.interview()
            if LightEntityFeature.EFFECT & self.supported_features:
                await self.client.set_static_colour(
                    (
                        kwargs[ATTR_RGBW_COLOR][3],
                        kwargs[ATTR_RGBW_COLOR][0],
                        kwargs[ATTR_RGBW_COLOR][1],
                        kwargs[ATTR_RGBW_COLOR][2],
                    )
                )
                await self.client.set_mode("color")
                self.client.default_mode = "color"
            else:
                await self.client.set_cycle_colours(
                    (
                        kwargs[ATTR_RGBW_COLOR][3],
                        kwargs[ATTR_RGBW_COLOR][0],
                        kwargs[ATTR_RGBW_COLOR][1],
                        kwargs[ATTR_RGBW_COLOR][2],
                    )
                )
                await self.client.set_mode("movie")
                self.client.default_mode = "movie"
            self._attr_rgbw_color = kwargs[ATTR_RGBW_COLOR]

        if ATTR_RGB_COLOR in kwargs and kwargs[ATTR_RGB_COLOR] != self._attr_rgb_color:
            await self.client.interview()
            if LightEntityFeature.EFFECT & self.supported_features:
                await self.client.set_static_colour(kwargs[ATTR_RGB_COLOR])
                await self.client.set_mode("color")
                self.client.default_mode = "color"
            else:
                await self.client.set_cycle_colours(kwargs[ATTR_RGB_COLOR])
                await self.client.set_mode("movie")
                self.client.default_mode = "movie"

            self._attr_rgb_color = kwargs[ATTR_RGB_COLOR]

        if (
            ATTR_EFFECT in kwargs
            and LightEntityFeature.EFFECT & self.supported_features
        ):
            movie_id = kwargs[ATTR_EFFECT].split(" ")[0]
            if (
                self.coordinator.data.current_movie is None
                or int(movie_id) != self.coordinator.data.current_movie
            ):
                await self.client.interview()
                await self.client.set_current_movie(int(movie_id))
                await self.client.set_mode("movie")
                self.client.default_mode = "movie"
        if not self._attr_is_on:
            await self.client.turn_on()
        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn device off."""
        await self.client.turn_off()
        await self.coordinator.async_refresh()

    def _update_attr(self) -> None:
        """Update the entity attributes."""
        self._attr_is_on = self.coordinator.data.is_on
        self._attr_brightness = self.coordinator.data.brightness

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attr()
        super()._handle_coordinator_update()
