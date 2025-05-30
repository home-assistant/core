"""Support for the Switchbot Light."""

from typing import Any

from switchbot_api import (
    CeilingLightCommands,
    CommonCommands,
    Device,
    Remote,
    SwitchBotAPI,
)

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SwitchbotCloudData, SwitchBotCoordinator
from .const import DOMAIN
from .entity import SwitchBotCloudEntity


def value_map_brightness(value: int) -> int:
    """Return value for brightness map."""
    return int(value / 255 * 100)


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SwitchBot Cloud entry."""
    data: SwitchbotCloudData = hass.data[DOMAIN][config.entry_id]
    async_add_entities(
        SwitchBotCloudLight(data.api, device, coordinator)
        for device, coordinator in data.devices.lights
    )


class SwitchBotCloudLight(SwitchBotCloudEntity, LightEntity):
    """Representation of a SwitchBot Battery Circulator Fan."""

    # _attr_supported_features = (
    #     LightEntityFeature.FLASH
    #     | LightEntityFeature.EFFECT
    #     | LightEntityFeature.TRANSITION
    # )

    _attr_max_color_temp_kelvin = 6500
    _attr_min_color_temp_kelvin = 2700

    _attr_is_on: bool | None = None

    def __init__(
        self,
        api: SwitchBotAPI,
        device: Device | Remote,
        coordinator: SwitchBotCoordinator,
    ) -> None:
        """Entity init."""
        super().__init__(api, device, coordinator)
        if device.device_type not in "Strip Light":
            self._attr_supported_color_modes = {ColorMode.RGB, ColorMode.COLOR_TEMP}
        else:
            self._attr_supported_color_modes = {ColorMode.RGB}

    @property
    def is_on(self) -> bool | None:
        """Return True if entity is on."""
        response: dict | None = self.coordinator.data
        assert response is not None

        if self._attr_is_on is None:
            self._attr_color_mode = ColorMode.RGB
            power: str | None = response.get("power") if response else None
            self._attr_is_on = "on" in power if power else False
            self._attr_brightness: int | None = response.get("brightness")
            attr_rgb_color: str | None = response.get("color")

            self._attr_rgb_color: tuple | None = (
                tuple(int(i) for i in attr_rgb_color.split(":"))
                if attr_rgb_color
                else None
            )
            self._attr_color_temp_kelvin: int | None = response.get("colorTemperature")
        return self._attr_is_on

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self.send_api_command(CommonCommands.OFF)
        self._attr_is_on = False
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        brightness: int | None = kwargs.get("brightness")
        rgb_color: tuple[int, int, int] | None = kwargs.get("rgb_color")
        color_temp_kelvin: int | None = kwargs.get("color_temp_kelvin")
        if brightness:
            self._attr_color_mode = ColorMode.RGB
            await self.send_api_command(
                CeilingLightCommands.SET_BRIGHTNESS,
                parameters=str(value_map_brightness(brightness)),
            )
            self._attr_brightness = brightness
        if rgb_color:
            self._attr_color_mode = ColorMode.RGB
            # need fixed while switch-api update
            await self.send_api_command(
                CeilingLightCommands.SET_COLOR_TEMPERATURE,
                parameters=":".join([str(i) for i in rgb_color]),
            )
            self._attr_rgb_color = rgb_color
        if color_temp_kelvin:
            self._attr_color_mode = ColorMode.COLOR_TEMP
            await self.send_api_command(
                CeilingLightCommands.SET_COLOR_TEMPERATURE,
                parameters=str(color_temp_kelvin),
            )
            self._attr_color_temp_kelvin = color_temp_kelvin
            self._attr_rgb_color = (0, 0, 0)
        else:
            self._attr_color_mode = ColorMode.RGB
            await self.send_api_command(CommonCommands.ON)
        self._attr_is_on = True
        self.async_write_ha_state()

    @property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 0..255."""
        return self._attr_brightness

    @property
    def color_mode(self) -> ColorMode | str | None:
        """Return the color mode of the light."""
        return self._attr_color_mode

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return the CT color value in Kelvin."""
        return self._attr_color_temp_kelvin

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the rgb color value [int, int, int]."""
        return self._attr_rgb_color

    @property
    def supported_color_modes(self) -> set[ColorMode] | set[str] | None:
        """Flag supported color modes."""
        return self._attr_supported_color_modes
