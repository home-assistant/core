"""Platform for light integration."""

import asyncio
from typing import Any

from libaxion_dmx import AxionDmxApi

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
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import homeassistant.util.color as color_util

from . import AxionConfigEntry
from .const import (
    _LOGGER,
    AXION_MANUFACTURER_NAME,
    AXION_MODEL_NAME,
    CONF_CHANNEL,
    CONF_LIGHT_TYPE,
    DOMAIN,
)
from .coordinator import AxionDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AxionConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Axion Lighting platform."""
    api = config_entry.runtime_data.api
    coordinator = config_entry.runtime_data.coordinator
    channel = config_entry.data[CONF_CHANNEL]
    light_type = config_entry.data[CONF_LIGHT_TYPE]

    # Fetch the device name before creating the entity
    try:
        device_name = (await api.get_name()).strip()
    except Exception as e:  # noqa: BLE001
        _LOGGER.error(f"Failed to get device name: {e}")
        device_name = "Unknown"

    light = AxionDMXLight(coordinator, api, channel, light_type, device_name)

    async_add_entities([light], True)


class AxionDMXLight(CoordinatorEntity[AxionDataUpdateCoordinator], LightEntity):
    """Representation of an Axion Light."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self,
        coordinator: AxionDataUpdateCoordinator,
        api: AxionDmxApi,
        channel: int,
        light_type: str,
        device_name: str,
    ) -> None:
        """Initialize an Axion Light."""
        super().__init__(coordinator)
        self.api = api
        self._channel = channel - 1
        self._light_type = light_type
        self._name = f"Axion Light {channel}"
        self._attr_unique_id = f"axion_dmx_light_{device_name}_{channel}"
        self._attr_is_on = False
        self._attr_brightness = 255
        self._attr_hs_color = (0, 0)  # Default to white
        self._last_hs_color: tuple[float, float] | None = (0, 0)
        self._attr_rgbw_color = (0, 0, 0, 0)  # Default values for RGBW
        self._last_rgbw: tuple[int, int, int, int] | None = (0, 0, 0, 0)
        self._attr_rgbww_color = (0, 0, 0, 0, 0)  # Default values for RGBWW
        self._last_rgbww: tuple[int, int, int, int, int] | None = (0, 0, 0, 0, 0)
        self._color_temp = 1
        self._last_color_temp = 1
        self._attr_color_mode = ColorMode.BRIGHTNESS
        self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
        self._attr_supported_features = LightEntityFeature.TRANSITION
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            name=self._name,
            manufacturer=AXION_MANUFACTURER_NAME,
            model=AXION_MODEL_NAME,
        )

        if light_type == "rgb":
            self._attr_color_mode = ColorMode.HS
            self._attr_supported_color_modes.add(ColorMode.HS)

        if light_type == "rgbw":
            self._attr_color_mode = ColorMode.RGBW
            self._attr_supported_color_modes.add(ColorMode.RGBW)

        if light_type == "rgbww":
            self._attr_color_mode = ColorMode.RGBWW
            self._attr_supported_color_modes.add(ColorMode.RGBWW)

        if light_type == "tunable_white":
            self._attr_color_mode = ColorMode.COLOR_TEMP
            self._attr_supported_color_modes.add(ColorMode.COLOR_TEMP)

    @property
    def color_temp(self) -> int:
        """Return the color temperature of the light."""
        return color_util.color_temperature_kelvin_to_mired(self._color_temp)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Instruct the light to turn on."""
        _LOGGER.debug(f"Instructing the {self._name} to turn on!")
        self._attr_is_on = True

        # Handling brightness
        self._attr_brightness = kwargs.get(ATTR_BRIGHTNESS, 255)

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

        if self._light_type in ["rgb", "rgbw", "rgbww"]:
            if ATTR_HS_COLOR in kwargs:
                self._attr_color_mode = ColorMode.HS
                self._attr_hs_color = kwargs[ATTR_HS_COLOR]
                _LOGGER.debug(f"RGB before scaling - {self._attr_hs_color}")
                if self._attr_hs_color is not None:
                    rgb = color_util.color_hs_to_RGB(*self._attr_hs_color)
            elif ATTR_RGBW_COLOR in kwargs:
                self._attr_color_mode = ColorMode.RGBW
                self._attr_rgbw_color = rgbw = kwargs[ATTR_RGBW_COLOR]
                _LOGGER.debug(f"RGBW before scaling - {self._attr_rgbw_color}")
            elif ATTR_RGBWW_COLOR in kwargs:
                self._attr_color_mode = ColorMode.RGBWW
                self._attr_rgbww_color = rgbww = kwargs[ATTR_RGBWW_COLOR]
                _LOGGER.debug(f"RGBWW before scaling - {self._attr_rgbww_color}")

            if rgb is not None:
                # Scale the previously known RGB values
                scaled_rgb = [
                    scale_brightness(c, self._attr_brightness, 255) for c in rgb
                ]
                _LOGGER.debug(f"RGB after scaling - {scaled_rgb}")
                await self.api.set_color(self._channel, scaled_rgb)
                self._last_hs_color = self._attr_hs_color
            elif rgbw is not None:
                # Scale the previously known RGBW values
                scaled_rgbw = [
                    scale_brightness(c, self._attr_brightness, 255) for c in rgbw
                ]
                _LOGGER.debug(f"RGBW after scaling - {scaled_rgbw}")
                await self.api.set_rgbw(self._channel, scaled_rgbw)
                self._last_rgbw = self._attr_rgbw_color
            elif rgbww is not None:
                # Scale the previously known RGBWW values
                scaled_rgbww = [
                    scale_brightness(c, self._attr_brightness, 255) for c in rgbww
                ]
                _LOGGER.debug(f"RGBWW after scaling - {scaled_rgbww}")
                await self.api.set_rgbww(self._channel, scaled_rgbww)
                self._last_rgbww = self._attr_rgbww_color
            else:
                _LOGGER.debug("No color is specified, use the last known color")
                # If no color is specified, use the last known color
                if self._light_type == "rgb":
                    _LOGGER.debug(f"Using the last RGB - {self._last_hs_color}")
                    if self._last_hs_color is not None:
                        rgb = color_util.color_hs_to_RGB(*self._last_hs_color)
                    if rgb is not None:
                        scaled_rgb = [
                            scale_brightness(c, self._attr_brightness, 255) for c in rgb
                        ]
                    await self.api.set_color(self._channel, scaled_rgb)
                elif self._light_type == "rgbw":
                    _LOGGER.debug(f"Using the last RGBW - {self._last_rgbw}")
                    rgbw = self._last_rgbw
                    if rgbw is not None:
                        scaled_rgbw = [
                            scale_brightness(c, self._attr_brightness, 255)
                            for c in rgbw
                        ]
                    await self.api.set_rgbw(self._channel, scaled_rgbw)
                elif self._light_type == "rgbww":
                    _LOGGER.debug(f"Using the last RGBWW - {self._last_rgbww}")
                    rgbww = self._last_rgbww
                    if rgbww is not None:
                        scaled_rgbww = [
                            scale_brightness(c, self._attr_brightness, 255)
                            for c in rgbww
                        ]
                    await self.api.set_rgbww(self._channel, scaled_rgbww)
        elif self._light_type == "tunable_white":
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
                brightness=self._attr_brightness
                if self._attr_brightness is not None
                else 255,
            )
            self._last_color_temp = self._color_temp
            _LOGGER.debug(f"Setting Warm Light level - {warm_white_level}")
            await self.api.set_level(self._channel, warm_white_level)
            _LOGGER.debug(f"Setting Cold White level - {cold_white_level}")
            await self.api.set_level(self._channel + 1, cold_white_level)
        else:
            await self.api.set_level(self._channel, self._attr_brightness)

        # Add a small delay to allow the controller to process the command
        await asyncio.sleep(0.5)

        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        _LOGGER.debug(f"Instructing the {self._name} to turn off!")
        self._attr_is_on = False

        # Only set the first channel to 0 for White or Tunable White
        if self._light_type in ["white", "tunable_white"]:
            await self.api.set_level(self._channel, 0)

        if self._light_type == "rgb":
            self._last_hs_color = self._attr_hs_color
            await self.api.set_color(self._channel, (0, 0, 0))

        elif self._light_type == "rgbw":
            self._last_rgbw = self._attr_rgbw_color
            await self.api.set_rgbw(self._channel, (0, 0, 0, 0))

        elif self._light_type == "rgbww":
            self._last_rgbww = self._attr_rgbww_color
            await self.api.set_rgbww(self._channel, (0, 0, 0, 0, 0))

        elif self._light_type == "tunable_white":
            # Turn off the second channel
            await self.api.set_level(self._channel + 1, 0)

        # Add a small delay to allow the controller to process the command
        await asyncio.sleep(0.5)

        # Manually refresh the coordinator to get the latest state
        await self.coordinator.async_request_refresh()
