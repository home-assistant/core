"""Provides a light for Home Connect."""

import logging
from math import ceil
from typing import Any

from homeconnect.api import HomeConnectError

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
    LightEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.util.color as color_util

from .api import HomeConnectDevice
from .const import ATTR_VALUE, DOMAIN
from .entity import HomeConnectEntityDescription, HomeConnectInteractiveEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Home Connect light."""

    def get_entities():
        """Get a list of entities."""
        hc_api = hass.data[DOMAIN][config_entry.entry_id]
        return [
            HomeConnectLight(device, setting)
            for setting in BSH_LIGHT_SETTINGS
            for device in hc_api.devices
            if setting.key in device.appliance.status
        ]

    async_add_entities(await hass.async_add_executor_job(get_entities), True)


class HomeConnectLightEntityDescription(
    HomeConnectEntityDescription,
    LightEntityDescription,
    frozen_or_thawed=True,
):
    """Description of a Home Connect binary sensor entity."""

    brightness_key: str | None = None
    color_key: str | None = None
    enable_custom_color_value_key: str | None = None
    custom_color_key: str | None = None


class HomeConnectLight(HomeConnectInteractiveEntity, LightEntity):
    """Light for Home Connect."""

    entity_description: HomeConnectLightEntityDescription
    _brightness_key: str | None
    _color_key: str | None
    _enable_custom_color_value_key: str | None
    _custom_color_key: str | None

    def __init__(
        self, device: HomeConnectDevice, desc: HomeConnectLightEntityDescription
    ) -> None:
        """Initialize the entity."""
        super().__init__(device, desc)

        def get_setting_key_if_setting_exists(setting_key) -> str | None:
            if setting_key and setting_key in device.appliance.status:
                return setting_key
            return None

        self._brightness_key = get_setting_key_if_setting_exists(desc.brightness_key)
        self._custom_color_key = get_setting_key_if_setting_exists(
            desc.custom_color_key
        )
        self._color_key = get_setting_key_if_setting_exists(desc.color_key)
        self._enable_custom_color_value_key = desc.enable_custom_color_value_key
        self._custom_color_key = get_setting_key_if_setting_exists(
            desc.custom_color_key
        )
        self._attr_color_mode = (
            ColorMode.HS
            if self._custom_color_key is not None
            else ColorMode.BRIGHTNESS
            if self._brightness_key is not None
            else ColorMode.ONOFF
        )

        match (self._brightness_key, self._custom_color_key):
            case (None, None):
                self._attr_supported_color_modes = {ColorMode.ONOFF}
            case (_, None):
                self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
            case (_, _):
                self._attr_supported_color_modes = {ColorMode.HS, ColorMode.RGB}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Switch the light on, change brightness, change color."""
        _LOGGER.debug("Switching light on for: %s", self.name)
        if not await self.async_set_value_to_appliance(True):
            return
        if self._custom_color_key:
            if ATTR_RGB_COLOR in kwargs:
                if (
                    self._enable_custom_color_value_key
                    and self._enable_custom_color_value_key
                    != self.device.appliance.status.get(self._color_key, {}).get(
                        ATTR_VALUE, None
                    )
                ):
                    try:
                        await self.async_set_value_to_appliance(
                            self._enable_custom_color_value_key,
                            self._color_key,
                        )
                    except HomeConnectError as err:
                        _LOGGER.error(
                            "Error while trying selecting customcolor: %s", err
                        )
                        return
                rgb = kwargs[ATTR_RGB_COLOR]
                hex_val = color_util.color_rgb_to_hex(rgb[0], rgb[1], rgb[2])
                try:
                    await self.async_set_value_to_appliance(
                        f"#{hex_val}",
                        self._custom_color_key,
                    )
                except HomeConnectError as err:
                    _LOGGER.error("Error while trying setting the color: %s", err)
            elif ATTR_BRIGHTNESS in kwargs and ATTR_HS_COLOR in kwargs:
                if (
                    self._enable_custom_color_value_key
                    and self._enable_custom_color_value_key
                    != self.device.appliance.status.get(self._color_key, {}).get(
                        ATTR_VALUE, None
                    )
                ):
                    try:
                        await self.async_set_value_to_appliance(
                            self._enable_custom_color_value_key,
                            self._color_key,
                        )
                    except HomeConnectError as err:
                        _LOGGER.error(
                            "Error while trying selecting customcolor: %s", err
                        )
                        return
                if self._attr_brightness is not None:
                    brightness = 10 + ceil(self._attr_brightness / 255 * 90)
                    if ATTR_BRIGHTNESS in kwargs:
                        brightness = 10 + ceil(kwargs[ATTR_BRIGHTNESS] / 255 * 90)

                    hs_color = kwargs.get(ATTR_HS_COLOR, self._attr_hs_color)

                    if hs_color is not None:
                        rgb = color_util.color_hsv_to_RGB(
                            hs_color[0], hs_color[1], brightness
                        )
                        hex_val = color_util.color_rgb_to_hex(rgb[0], rgb[1], rgb[2])
                        try:
                            await self.async_set_value_to_appliance(
                                f"#{hex_val}",
                                self._custom_color_key,
                            )
                        except HomeConnectError as err:
                            _LOGGER.error(
                                "Error while trying setting the color: %s", err
                            )

        if ATTR_BRIGHTNESS in kwargs:
            _LOGGER.debug("Changing brightness for: %s", self.name)
            brightness = 10 + ceil(kwargs[ATTR_BRIGHTNESS] / 255 * 90)
            try:
                await self.async_set_value_to_appliance(
                    brightness, self._brightness_key
                )
            except HomeConnectError as err:
                _LOGGER.error("Error while trying set the brightness: %s", err)

        self.async_entity_update()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Switch the light off."""
        _LOGGER.debug("Switching light off for: %s", self.name)
        await self.async_set_value_to_appliance(False)
        self.async_entity_update()

    async def async_update(self) -> None:
        """Update the light's status."""
        if self.status.get(ATTR_VALUE) is True:
            self._attr_is_on = True
        elif self.status.get(ATTR_VALUE) is False:
            self._attr_is_on = False
        else:
            self._attr_is_on = None

        _LOGGER.debug("Updated, new light state: %s", self._attr_is_on)

        if self._custom_color_key:
            color = self.device.appliance.status.get(self._custom_color_key, {})

            if not color:
                self._attr_hs_color = None
                self._attr_brightness = None
            else:
                colorvalue = color.get(ATTR_VALUE)[1:]
                rgb = color_util.rgb_hex_to_rgb_list(colorvalue)
                self._attr_rgb_color = (rgb[0], rgb[1], rgb[2])
                hsv = color_util.color_RGB_to_hsv(
                    self._attr_rgb_color[0],
                    self._attr_rgb_color[1],
                    self._attr_rgb_color[2],
                )
                self._attr_hs_color = (hsv[0], hsv[1])
                self._attr_brightness = ceil((hsv[2] - 10) * 255 / 90)
                _LOGGER.debug(
                    "Updated, new color (%s) and new brightness (%s) ",
                    colorvalue,
                    self._attr_brightness,
                )

        elif self._brightness_key:
            brightness = self.device.appliance.status.get(self._brightness_key, {})
            if brightness is None:
                self._attr_brightness = None
            else:
                self._attr_brightness = ceil(
                    (brightness.get(ATTR_VALUE) - 10) * 255 / 90
                )
            _LOGGER.debug("Updated, new brightness: %s", self._attr_brightness)


BSH_LIGHT_SETTINGS = {
    HomeConnectLightEntityDescription(
        key="Refrigeration.Common.Setting.Light.External.Power",
        brightness_key="Refrigeration.Common.Setting.Light.External.Brightness",
    ),
    HomeConnectLightEntityDescription(
        key="Refrigeration.Common.Setting.Light.Internal.Power",
        brightness_key="Refrigeration.Common.Setting.Light.Internal.Brightness",
    ),
    HomeConnectLightEntityDescription(
        key="Cooking.Common.Setting.Lighting",
        brightness_key="Cooking.Common.Setting.LightingBrightness",
    ),
    HomeConnectLightEntityDescription(
        key="BSH.Common.Setting.AmbientLightEnabled",
        brightness_key="BSH.Common.Setting.AmbientLightBrightness",
        color_key="BSH.Common.Setting.AmbientLightColor",
        enable_custom_color_value_key="BSH.Common.EnumType.AmbientLightColor.CustomColor",
        custom_color_key="BSH.Common.Setting.AmbientLightCustomColor",
    ),
}
