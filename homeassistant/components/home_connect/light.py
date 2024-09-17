"""Provides a light for Home Connect."""

from dataclasses import dataclass
import logging
from math import ceil
from typing import Any

from homeconnect.api import HomeConnectError

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    ColorMode,
    LightEntity,
    LightEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.util.color as color_util

from .api import ConfigEntryAuth, HomeConnectDevice
from .const import (
    ATTR_VALUE,
    BSH_AMBIENT_LIGHT_BRIGHTNESS,
    BSH_AMBIENT_LIGHT_COLOR,
    BSH_AMBIENT_LIGHT_COLOR_CUSTOM_COLOR,
    BSH_AMBIENT_LIGHT_CUSTOM_COLOR,
    BSH_AMBIENT_LIGHT_ENABLED,
    COOKING_LIGHTING,
    COOKING_LIGHTING_BRIGHTNESS,
    DOMAIN,
    REFRIGERATION_EXTERNAL_LIGHT_BRIGHTNESS,
    REFRIGERATION_EXTERNAL_LIGHT_POWER,
    REFRIGERATION_INTERNAL_LIGHT_BRIGHTNESS,
    REFRIGERATION_INTERNAL_LIGHT_POWER,
)
from .entity import HomeConnectEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class HomeConnectLightEntityDescription(LightEntityDescription):
    """Light entity description."""

    brightness_key: str | None = None
    color_key: str | None = None
    enable_custom_color_value_key: str | None = None
    custom_color_key: str | None = None
    brightness_scale: tuple[float, float] = (0.0, 100.0)


LIGHTS: tuple[HomeConnectLightEntityDescription, ...] = (
    HomeConnectLightEntityDescription(
        key=REFRIGERATION_INTERNAL_LIGHT_POWER,
        brightness_key=REFRIGERATION_INTERNAL_LIGHT_BRIGHTNESS,
        brightness_scale=(1.0, 100.0),
        translation_key="internal_light",
    ),
    HomeConnectLightEntityDescription(
        key=REFRIGERATION_EXTERNAL_LIGHT_POWER,
        brightness_key=REFRIGERATION_EXTERNAL_LIGHT_BRIGHTNESS,
        brightness_scale=(1.0, 100.0),
        translation_key="external_light",
    ),
    HomeConnectLightEntityDescription(
        key=COOKING_LIGHTING,
        brightness_key=COOKING_LIGHTING_BRIGHTNESS,
        brightness_scale=(10.0, 100.0),
        translation_key="cooking_lighting",
    ),
    HomeConnectLightEntityDescription(
        key=BSH_AMBIENT_LIGHT_ENABLED,
        brightness_key=BSH_AMBIENT_LIGHT_BRIGHTNESS,
        color_key=BSH_AMBIENT_LIGHT_COLOR,
        enable_custom_color_value_key=BSH_AMBIENT_LIGHT_COLOR_CUSTOM_COLOR,
        custom_color_key=BSH_AMBIENT_LIGHT_CUSTOM_COLOR,
        brightness_scale=(10.0, 100.0),
        translation_key="ambient_light",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Home Connect light."""

    def get_entities() -> list[LightEntity]:
        """Get a list of entities."""
        hc_api: ConfigEntryAuth = hass.data[DOMAIN][config_entry.entry_id]
        return [
            HomeConnectLight(device, description)
            for description in LIGHTS
            for device in hc_api.devices
            if description.key in device.appliance.status
        ]

    async_add_entities(await hass.async_add_executor_job(get_entities), True)


class HomeConnectLight(HomeConnectEntity, LightEntity):
    """Light for Home Connect."""

    entity_description: LightEntityDescription

    def __init__(
        self, device: HomeConnectDevice, desc: HomeConnectLightEntityDescription
    ) -> None:
        """Initialize the entity."""
        super().__init__(device, desc)

        def get_setting_key_if_setting_exists(setting_key: str | None) -> str | None:
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
        self._brightness_scale = desc.brightness_scale

        match (self._brightness_key, self._custom_color_key):
            case (None, None):
                self._attr_color_mode = ColorMode.ONOFF
                self._attr_supported_color_modes = {ColorMode.ONOFF}
            case (_, None):
                self._attr_color_mode = ColorMode.BRIGHTNESS
                self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
            case (_, _):
                self._attr_color_mode = ColorMode.HS
                self._attr_supported_color_modes = {ColorMode.HS}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Switch the light on, change brightness, change color."""
        if self._custom_color_key:
            _LOGGER.debug("Switching ambient light on for: %s", self.name)
            try:
                await self.hass.async_add_executor_job(
                    self.device.appliance.set_setting, self.bsh_key, True
                )
            except HomeConnectError as err:
                _LOGGER.error("Error while trying to turn on ambient light: %s", err)
                return
            if ATTR_BRIGHTNESS in kwargs or ATTR_HS_COLOR in kwargs:
                try:
                    await self.hass.async_add_executor_job(
                        self.device.appliance.set_setting,
                        self._color_key,
                        self._enable_custom_color_value_key,
                    )
                except HomeConnectError as err:
                    _LOGGER.error("Error while trying selecting customcolor: %s", err)
                if self._attr_brightness is not None:
                    brightness_arg = self._attr_brightness
                    if ATTR_BRIGHTNESS in kwargs:
                        brightness_arg = kwargs[ATTR_BRIGHTNESS]

                    brightness = ceil(
                        color_util.brightness_to_value(
                            self._brightness_scale, brightness_arg
                        )
                    )
                    hs_color = kwargs.get(ATTR_HS_COLOR, self._attr_hs_color)

                    if hs_color is not None:
                        rgb = color_util.color_hsv_to_RGB(
                            hs_color[0], hs_color[1], brightness
                        )
                        hex_val = color_util.color_rgb_to_hex(rgb[0], rgb[1], rgb[2])
                        try:
                            await self.hass.async_add_executor_job(
                                self.device.appliance.set_setting,
                                self._custom_color_key,
                                f"#{hex_val}",
                            )
                        except HomeConnectError as err:
                            _LOGGER.error(
                                "Error while trying setting the color: %s", err
                            )

        elif ATTR_BRIGHTNESS in kwargs:
            _LOGGER.debug(
                "Changing brightness for: %s, to: %s",
                self.name,
                kwargs[ATTR_BRIGHTNESS],
            )
            brightness = ceil(
                color_util.brightness_to_value(
                    self._brightness_scale, kwargs[ATTR_BRIGHTNESS]
                )
            )
            try:
                await self.hass.async_add_executor_job(
                    self.device.appliance.set_setting, self._brightness_key, brightness
                )
            except HomeConnectError as err:
                _LOGGER.error("Error while trying set the brightness: %s", err)
        else:
            _LOGGER.debug("Switching light on for: %s", self.name)
            try:
                await self.hass.async_add_executor_job(
                    self.device.appliance.set_setting, self.bsh_key, True
                )
            except HomeConnectError as err:
                _LOGGER.error("Error while trying to turn on light: %s", err)

        self.async_entity_update()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Switch the light off."""
        _LOGGER.debug("Switching light off for: %s", self.name)
        try:
            await self.hass.async_add_executor_job(
                self.device.appliance.set_setting, self.bsh_key, False
            )
        except HomeConnectError as err:
            _LOGGER.error("Error while trying to turn off light: %s", err)
        self.async_entity_update()

    async def async_update(self) -> None:
        """Update the light's status."""
        if self.device.appliance.status.get(self.bsh_key, {}).get(ATTR_VALUE) is True:
            self._attr_is_on = True
        elif (
            self.device.appliance.status.get(self.bsh_key, {}).get(ATTR_VALUE) is False
        ):
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
                hsv = color_util.color_RGB_to_hsv(rgb[0], rgb[1], rgb[2])
                self._attr_hs_color = (hsv[0], hsv[1])
                self._attr_brightness = color_util.value_to_brightness(
                    self._brightness_scale, hsv[2]
                )
                _LOGGER.debug("Updated, new brightness: %s", self._attr_brightness)

        elif self._brightness_key:
            brightness = self.device.appliance.status.get(self._brightness_key, {})
            if brightness is None:
                self._attr_brightness = None
            else:
                self._attr_brightness = color_util.value_to_brightness(
                    self._brightness_scale, brightness[ATTR_VALUE]
                )
            _LOGGER.debug("Updated, new brightness: %s", self._attr_brightness)
