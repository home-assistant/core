"""Provides a light for Home Connect."""

from collections.abc import Callable
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
from homeassistant.const import CONF_ENTITIES
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.util.color as color_util

from .api import HomeConnectDevice
from .const import (
    ATTR_DEVICE,
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


@dataclass(frozen=True)
class HomeConnectLightEntityDescription(LightEntityDescription):
    """Light entity description."""

    on_key: str | None = None
    brightness_key: str | None = None
    exists_fn: Callable[[HomeConnectDevice], bool] = lambda _: True


LIGHTS: tuple[HomeConnectLightEntityDescription, ...] = (
    HomeConnectLightEntityDescription(
        key="InternalLight",
        on_key=REFRIGERATION_INTERNAL_LIGHT_POWER,
        brightness_key=REFRIGERATION_INTERNAL_LIGHT_BRIGHTNESS,
        exists_fn=lambda device: bool(
            device.appliance.status.get(REFRIGERATION_INTERNAL_LIGHT_POWER)
        ),
    ),
    HomeConnectLightEntityDescription(
        key="ExternalLight",
        on_key=REFRIGERATION_EXTERNAL_LIGHT_POWER,
        brightness_key=REFRIGERATION_EXTERNAL_LIGHT_BRIGHTNESS,
        exists_fn=lambda device: bool(
            device.appliance.status.get(REFRIGERATION_EXTERNAL_LIGHT_POWER)
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Home Connect light."""

    def get_entities():
        """Get a list of entities."""
        entities = []
        hc_api = hass.data[DOMAIN][config_entry.entry_id]
        for device_dict in hc_api.devices:
            entity_dicts = device_dict.get(CONF_ENTITIES, {}).get("light", [])
            entity_list = [
                HomeConnectLight(**d)
                if d["desc"] != "CoolingLight"
                else HomeConnectCoolingLight(**d, entity_description=description)
                for d in entity_dicts
                for description in LIGHTS
                if description.exists_fn(d[ATTR_DEVICE])
            ]
            entities += entity_list
        return entities

    async_add_entities(await hass.async_add_executor_job(get_entities), True)


class HomeConnectLight(HomeConnectEntity, LightEntity):
    """Light for Home Connect."""

    def __init__(self, device, desc, ambient):
        """Initialize the entity."""
        super().__init__(device, desc)
        self._ambient = ambient
        self._percentage_scale = (10, 100)
        if ambient:
            self._brightness_key = BSH_AMBIENT_LIGHT_BRIGHTNESS
            self._key = BSH_AMBIENT_LIGHT_ENABLED
            self._custom_color_key = BSH_AMBIENT_LIGHT_CUSTOM_COLOR
            self._color_key = BSH_AMBIENT_LIGHT_COLOR
            self._attr_color_mode = ColorMode.HS
            self._attr_supported_color_modes = {ColorMode.HS}
        else:
            self._brightness_key = COOKING_LIGHTING_BRIGHTNESS
            self._key = COOKING_LIGHTING
            self._custom_color_key = None
            self._color_key = None
            self._attr_color_mode = ColorMode.BRIGHTNESS
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Switch the light on, change brightness, change color."""
        if self._ambient:
            _LOGGER.debug("Switching ambient light on for: %s", self.name)
            try:
                await self.hass.async_add_executor_job(
                    self.device.appliance.set_setting, self._key, True
                )
            except HomeConnectError as err:
                _LOGGER.error("Error while trying to turn on ambient light: %s", err)
                return
            if ATTR_BRIGHTNESS in kwargs or ATTR_HS_COLOR in kwargs:
                try:
                    await self.hass.async_add_executor_job(
                        self.device.appliance.set_setting,
                        self._color_key,
                        BSH_AMBIENT_LIGHT_COLOR_CUSTOM_COLOR,
                    )
                except HomeConnectError as err:
                    _LOGGER.error("Error while trying selecting customcolor: %s", err)
                if self._attr_brightness is not None:
                    brightness_arg = self._attr_brightness
                    if ATTR_BRIGHTNESS in kwargs:
                        brightness_arg = kwargs[ATTR_BRIGHTNESS]

                    brightness = ceil(
                        color_util.brightness_to_value(
                            self._percentage_scale, brightness_arg
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
                    self._percentage_scale, kwargs[ATTR_BRIGHTNESS]
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
                    self.device.appliance.set_setting, self._key, True
                )
            except HomeConnectError as err:
                _LOGGER.error("Error while trying to turn on light: %s", err)

        self.async_entity_update()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Switch the light off."""
        _LOGGER.debug("Switching light off for: %s", self.name)
        try:
            await self.hass.async_add_executor_job(
                self.device.appliance.set_setting, self._key, False
            )
        except HomeConnectError as err:
            _LOGGER.error("Error while trying to turn off light: %s", err)
        self.async_entity_update()

    async def async_update(self) -> None:
        """Update the light's status."""
        if self.device.appliance.status.get(self._key, {}).get(ATTR_VALUE) is True:
            self._attr_is_on = True
        elif self.device.appliance.status.get(self._key, {}).get(ATTR_VALUE) is False:
            self._attr_is_on = False
        else:
            self._attr_is_on = None

        _LOGGER.debug("Updated, new light state: %s", self._attr_is_on)

        if self._ambient:
            color = self.device.appliance.status.get(self._custom_color_key, {})

            if not color:
                self._attr_hs_color = None
                self._attr_brightness = None
            else:
                colorvalue = color.get(ATTR_VALUE)[1:]
                rgb = color_util.rgb_hex_to_rgb_list(colorvalue)
                hsv = color_util.color_RGB_to_hsv(rgb[0], rgb[1], rgb[2])
                self._attr_hs_color = (hsv[0], hsv[1])
                self._attr_brightness = ceil((hsv[2] - 10) * 255 / 90)
                _LOGGER.debug("Updated, new brightness: %s", self._attr_brightness)

        else:
            brightness = self.device.appliance.status.get(self._brightness_key, {})
            if not brightness:
                self._attr_brightness = None
            else:
                self._attr_brightness = color_util.value_to_brightness(
                    self._percentage_scale, brightness.get(ATTR_VALUE)
                )
            _LOGGER.debug("Updated, new brightness: %s", self._attr_brightness)


class HomeConnectCoolingLight(HomeConnectLight):
    """Light entity for Cooling Appliances."""

    def __init__(
        self,
        device: HomeConnectDevice,
        desc: str,
        ambient: bool,
        entity_description: HomeConnectLightEntityDescription,
    ) -> None:
        """Initialize Cooling Light Entity."""
        super().__init__(device, entity_description.key, ambient)
        self.entity_description = entity_description
        self._key = self.entity_description.on_key
        self._brightness_key = self.entity_description.brightness_key
        self._percentage_scale = (1, 100)
