"""Platform for light integration."""

import asyncio
from datetime import timedelta
from typing import Any

from requests.exceptions import RequestException

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    ATTR_RGBW_COLOR,
    ATTR_RGBWW_COLOR,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import homeassistant.util.color as color_util

from .const import _LOGGER, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Axion Lighting platform."""
    api = hass.data[DOMAIN][config_entry.entry_id]["api"]
    channel = hass.data[DOMAIN][config_entry.entry_id]["channel"]
    light_type = hass.data[DOMAIN][config_entry.entry_id]["light_type"]

    async def async_update_data():
        """Fetch data from API endpoint."""
        try:
            return await api.get_level(channel)
        except RequestException as err:
            raise UpdateFailed("Error communicating with API") from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="light",
        update_method=async_update_data,
        update_interval=timedelta(seconds=5),
    )
    await coordinator.async_config_entry_first_refresh()

    async_add_entities([AxionDMXLight(coordinator, api, channel, light_type)], True)


class AxionDMXLight(LightEntity):
    """Representation of an Axion Light."""

    def __init__(self, coordinator, api, channel, light_type) -> None:
        """Initialize an Axion Light."""
        self.coordinator = coordinator
        self.api = api
        self._channel = channel - 1
        self._light_type = light_type
        self._name = f"Axion Light {channel}"
        self._unique_id = f"axion_dmx_light_{channel}"
        self._is_on = False
        self._brightness = 255
        self._hs_color = (0, 0)  # Default to white
        self._last_hs_color = (0, 0)
        self._rgbw_color = (0, 0, 0, 0)  # Default values for RGBW
        self._last_rgbw = (0, 0, 0, 0)
        self._rgbww_color = (0, 0, 0, 0, 0)  # Default values for RGBWW
        self._last_rgbww = (0, 0, 0, 0, 0)
        self._color_temp = 1
        self._last_color_temp = 1
        self._attr_color_mode = ColorMode.BRIGHTNESS
        self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}

        if light_type == "RGB":
            self._attr_color_mode = ColorMode.HS
            self._attr_supported_color_modes.add(ColorMode.HS)

        if light_type == "RGBW":
            self._attr_color_mode = ColorMode.RGBW
            self._attr_supported_color_modes.add(ColorMode.RGBW)

        if light_type == "RGBWW":
            self._attr_color_mode = ColorMode.RGBWW
            self._attr_supported_color_modes.add(ColorMode.RGBWW)

        if light_type == "Tunable White":
            self._attr_color_mode = ColorMode.COLOR_TEMP
            self._attr_supported_color_modes.add(ColorMode.COLOR_TEMP)

    @property
    def name(self) -> str:
        """Return the display name of this light."""
        return self._name

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self._is_on

    @property
    def brightness(self) -> int:
        """Return the brightness of the light."""
        return self._brightness

    @property
    def color_mode(self) -> str:
        """Return the current color mode of this light."""
        return self._attr_color_mode if self._attr_color_mode is not None else ""

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the color of the light."""
        return self._hs_color

    @property
    def rgbw_color(self) -> tuple[int, int, int, int] | None:
        """Return the rgbw color value."""
        return self._rgbw_color

    @property
    def rgbww_color(self) -> tuple[int, int, int, int, int] | None:
        """Return the rgbww color value."""
        return self._rgbww_color

    @property
    def color_temp(self) -> int:
        """Return the color temperature of the light."""
        return color_util.color_temperature_kelvin_to_mired(self._color_temp)

    @property
    def unique_id(self) -> str:
        """Return the unique ID of this light."""
        return self._unique_id

    @property
    def supported_color_modes(self) -> set[ColorMode] | set[str] | None:
        """Flag supported color modes."""
        return self._attr_supported_color_modes

    @property
    def supported_features(self) -> LightEntityFeature:
        """Return the supported features of this light."""
        return LightEntityFeature.TRANSITION

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""
        _LOGGER.debug(f"Instructing the {self._name} to turn on!")
        self._is_on = True

        # Handling brightness
        self._brightness = kwargs.get(ATTR_BRIGHTNESS, 255)

        # Function to scale color values by brightness
        def scale_brightness(color_value, brightness, max_brightness):
            return int(color_value * brightness / max_brightness)

        def get_tunable_white_levels(
            cct: int,
            warm_white_k: int = 1800,
            cool_white_k: int = 6000,
            max_level: int = 255,
            brightness: int = 255,
        ) -> tuple[int, int]:
            """Convert color temperature to DMX levels for Cold White and Warm White channels."""
            range_k = cool_white_k - warm_white_k
            if cct < warm_white_k:
                cct = warm_white_k
            elif cct > cool_white_k:
                cct = cool_white_k

            percent = ((cct - warm_white_k) / range_k) * 100
            _LOGGER.debug(f"Percentage - {percent}")

            ww_percent = 100 - percent
            cw_percent = percent

            ww_level = int((max_level / 100) * ww_percent)
            _LOGGER.debug(f"Warm white level - {ww_level}")
            cw_level = int((max_level / 100) * cw_percent)
            _LOGGER.debug(f"Cold white level - {cw_level}")

            if brightness > 0:
                ww_level = int(ww_level * (brightness / 255))
                cw_level = int(cw_level * (brightness / 255))

            return ww_level, cw_level

        # Initialize color variables
        rgb = None
        rgbw = None
        rgbww = None
        cold_white_level = 0
        warm_white_level = 0

        if self._light_type in ["RGB", "RGBW", "RGBWW"]:
            if ATTR_HS_COLOR in kwargs:
                self._attr_color_mode = ColorMode.HS
                self._hs_color = kwargs[ATTR_HS_COLOR]
                _LOGGER.debug(f"RGB before scaling - {self._hs_color}")
                rgb = color_util.color_hs_to_RGB(*self._hs_color)
            elif ATTR_RGBW_COLOR in kwargs:
                self._attr_color_mode = ColorMode.RGBW
                self._rgbw_color = rgbw = kwargs[ATTR_RGBW_COLOR]
                _LOGGER.debug(f"RGBW before scaling - {self._rgbw_color}")
            elif ATTR_RGBWW_COLOR in kwargs:
                self._attr_color_mode = ColorMode.RGBWW
                self._rgbww_color = rgbww = kwargs[ATTR_RGBWW_COLOR]
                _LOGGER.debug(f"RGBWW before scaling - {self._rgbww_color}")

            if rgb is not None:
                # Scale the previously known RGB values
                scaled_rgb = [scale_brightness(c, self._brightness, 255) for c in rgb]
                _LOGGER.debug(f"RGB after scaling - {scaled_rgb}")
                await self.api.set_color(self._channel, scaled_rgb)
                self._last_hs_color = self._hs_color
            elif rgbw is not None:
                # Scale the previously known RGBW values
                scaled_rgbw = [scale_brightness(c, self._brightness, 255) for c in rgbw]
                _LOGGER.debug(f"RGBW after scaling - {scaled_rgbw}")
                await self.api.set_rgbw(self._channel, scaled_rgbw)
                self._last_rgbw = self._rgbw_color
            elif rgbww is not None:
                # Scale the previously known RGBWW values
                scaled_rgbww = [
                    scale_brightness(c, self._brightness, 255) for c in rgbww
                ]
                _LOGGER.debug(f"RGBWW after scaling - {scaled_rgbww}")
                await self.api.set_rgbww(self._channel, scaled_rgbww)
                self._last_rgbww = self._rgbww_color
            else:
                _LOGGER.debug("No color is specified, use the last known color")
                # If no color is specified, use the last known color
                if self._light_type == "RGB":
                    _LOGGER.debug(f"Using the last RGB - {self._last_hs_color}")
                    rgb = color_util.color_hs_to_RGB(*self._last_hs_color)
                    scaled_rgb = [
                        scale_brightness(c, self._brightness, 255) for c in rgb
                    ]
                    await self.api.set_color(self._channel, scaled_rgb)
                elif self._light_type == "RGBW":
                    _LOGGER.debug(f"Using the last RGBW - {self._last_rgbw}")
                    rgbw = self._last_rgbw
                    scaled_rgbw = [
                        scale_brightness(c, self._brightness, 255) for c in rgbw
                    ]
                    await self.api.set_rgbw(self._channel, scaled_rgbw)
                elif self._light_type == "RGBWW":
                    _LOGGER.debug(f"Using the last RGBWW - {self._last_rgbww}")
                    rgbww = self._last_rgbww
                    scaled_rgbww = [
                        scale_brightness(c, self._brightness, 255) for c in rgbww
                    ]
                    await self.api.set_rgbww(self._channel, scaled_rgbww)
        elif self._light_type == "Tunable White":
            if ATTR_COLOR_TEMP in kwargs:
                self._attr_color_mode = ColorMode.COLOR_TEMP
                self._color_temp = color_util.color_temperature_mired_to_kelvin(
                    kwargs[ATTR_COLOR_TEMP]
                )
            else:
                self._color_temp = self._last_color_temp

            warm_white_level, cold_white_level = get_tunable_white_levels(
                self._color_temp,
                warm_white_k=1800,  # Fixed value for warm white LED
                cool_white_k=6000,  # Fixed value for cold white LED
                max_level=255,
                brightness=self._brightness,
            )
            self._last_color_temp = self._color_temp
            _LOGGER.debug(f"Setting Warm Light level - {warm_white_level}")
            await self.api.set_level(self._channel, warm_white_level)
            _LOGGER.debug(f"Setting Cold White level - {cold_white_level}")
            await self.api.set_level(self._channel + 1, cold_white_level)
        else:
            await self.api.set_level(self._channel, self._brightness)

        # Add a small delay to allow the controller to process the command
        await asyncio.sleep(0.5)

        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        _LOGGER.debug(f"Instructing the {self._name} to turn off!")
        self._is_on = False
        await self.api.set_level(self._channel, 0)

        if self._light_type in ["RGB", "RGBW", "RGBWW"]:
            self._last_hs_color = self._hs_color
            await self.api.set_level((self._channel + 1), 0)
            await self.api.set_level((self._channel + 2), 0)
            if self._light_type in ["RGBW", "RGBWW"]:
                self._last_rgbw = self._rgbw_color
                await self.api.set_level((self._channel + 3), 0)
                if self._light_type == "RGBWW":
                    self._last_rgbww = self._rgbww_color
                    await self.api.set_level((self._channel + 4), 0)
        elif self._light_type == "Tunable White":
            await self.api.set_level(self._channel + 1, 0)

        # Add a small delay to allow the controller to process the command
        await asyncio.sleep(0.5)

        # Manually refresh the coordinator to get the latest state
        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Fetch new state data for this light."""
        level = await self.api.get_level(self._channel)
        self._is_on = level > 0
        self._brightness = level

        if self._light_type in ["RGB", "RGBW", "RGBWW"]:
            # Assuming the RGB values are stored in a way to fetch them
            r = await self.api.get_level(self._channel)
            g = await self.api.get_level(self._channel + 1)
            b = await self.api.get_level(self._channel + 2)
            hs_color = color_util.color_RGB_to_hs(r, g, b)
            self._hs_color = (int(hs_color[0]), int(hs_color[1]))

            # Determine if the light is on based on any of the RGB channels being non-zero
            self._is_on = any([r, g, b])
            self._brightness = max(r, g, b)

            if self._light_type in ["RGBW", "RGBWW"]:
                w1 = await self.api.get_level(self._channel + 3)
                self._rgbw_color = (r, g, b, w1)
                self._is_on = any([r, g, b, w1])
                self._brightness = max(r, g, b, w1)

                if self._light_type == "RGBWW":
                    w2 = await self.api.get_level(self._channel + 4)
                    self._rgbww_color = (r, g, b, w1, w2)
                    self._is_on = any([r, g, b, w1, w2])
                    self._brightness = max(r, g, b, w1, w2)

        elif self._light_type == "Tunable White":
            cold_white_level = await self.api.get_level(self._channel)
            warm_white_level = await self.api.get_level(self._channel + 1)
            self._is_on = any([cold_white_level, warm_white_level])
            self._brightness = max(cold_white_level, warm_white_level)

        # # Make sure to update the state in Home Assistant
        # self.async_write_ha_state()
