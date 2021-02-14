"""Provides a light for Home Connect."""
import logging
from math import ceil

from homeconnect.api import HomeConnectError

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    LightEntity,
)
import homeassistant.util.color as color_util

from .const import (
    BSH_AMBIENT_LIGHT_BRIGHTNESS,
    BSH_AMBIENT_LIGHT_COLOR,
    BSH_AMBIENT_LIGHT_COLOR_CUSTOM_COLOR,
    BSH_AMBIENT_LIGHT_CUSTOM_COLOR,
    BSH_AMBIENT_LIGHT_ENABLED,
    COOKING_LIGHTING,
    COOKING_LIGHTING_BRIGHTNESS,
    DOMAIN,
)
from .entity import HomeConnectEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Home Connect light."""

    def get_entities():
        """Get a list of entities."""
        entities = []
        hc_api = hass.data[DOMAIN][config_entry.entry_id]
        for device_dict in hc_api.devices:
            entity_dicts = device_dict.get("entities", {}).get("light", [])
            entity_list = [HomeConnectLight(**d) for d in entity_dicts]
            entities += entity_list
        return entities

    async_add_entities(await hass.async_add_executor_job(get_entities), True)


class HomeConnectLight(HomeConnectEntity, LightEntity):
    """Light for Home Connect."""

    def __init__(self, device, desc, ambient):
        """Initialize the entity."""
        super().__init__(device, desc)
        self._state = None
        self._brightness = None
        self._hs_color = None
        self._ambient = ambient
        if self._ambient:
            self._brightness_key = BSH_AMBIENT_LIGHT_BRIGHTNESS
            self._key = BSH_AMBIENT_LIGHT_ENABLED
            self._custom_color_key = BSH_AMBIENT_LIGHT_CUSTOM_COLOR
            self._color_key = BSH_AMBIENT_LIGHT_COLOR
        else:
            self._brightness_key = COOKING_LIGHTING_BRIGHTNESS
            self._key = COOKING_LIGHTING
            self._custom_color_key = None
            self._color_key = None

    @property
    def is_on(self):
        """Return true if the light is on."""
        return bool(self._state)

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return self._brightness

    @property
    def hs_color(self):
        """Return the color property."""
        return self._hs_color

    @property
    def supported_features(self):
        """Flag supported features."""
        if self._ambient:
            return SUPPORT_BRIGHTNESS | SUPPORT_COLOR
        return SUPPORT_BRIGHTNESS

    async def async_turn_on(self, **kwargs):
        """Switch the light on, change brightness, change color."""
        if self._ambient:
            _LOGGER.debug("Switching ambient light on for: %s", self.name)
            try:
                await self.hass.async_add_executor_job(
                    self.device.appliance.set_setting,
                    self._key,
                    True,
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
                if self._brightness is not None:
                    brightness = 10 + ceil(self._brightness / 255 * 90)
                    if ATTR_BRIGHTNESS in kwargs:
                        brightness = 10 + ceil(kwargs[ATTR_BRIGHTNESS] / 255 * 90)

                    hs_color = kwargs.get(ATTR_HS_COLOR, self._hs_color)

                    if hs_color is not None:
                        rgb = color_util.color_hsv_to_RGB(*hs_color, brightness)
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
            _LOGGER.debug("Changing brightness for: %s", self.name)
            brightness = 10 + ceil(kwargs[ATTR_BRIGHTNESS] / 255 * 90)
            try:
                await self.hass.async_add_executor_job(
                    self.device.appliance.set_setting,
                    self._brightness_key,
                    brightness,
                )
            except HomeConnectError as err:
                _LOGGER.error("Error while trying set the brightness: %s", err)
        else:
            _LOGGER.debug("Switching light on for: %s", self.name)
            try:
                await self.hass.async_add_executor_job(
                    self.device.appliance.set_setting,
                    self._key,
                    True,
                )
            except HomeConnectError as err:
                _LOGGER.error("Error while trying to turn on light: %s", err)

        self.async_entity_update()

    async def async_turn_off(self, **kwargs):
        """Switch the light off."""
        _LOGGER.debug("Switching light off for: %s", self.name)
        try:
            await self.hass.async_add_executor_job(
                self.device.appliance.set_setting,
                self._key,
                False,
            )
        except HomeConnectError as err:
            _LOGGER.error("Error while trying to turn off light: %s", err)
        self.async_entity_update()

    async def async_update(self):
        """Update the light's status."""
        if self.device.appliance.status.get(self._key, {}).get("value") is True:
            self._state = True
        elif self.device.appliance.status.get(self._key, {}).get("value") is False:
            self._state = False
        else:
            self._state = None

        _LOGGER.debug("Updated, new light state: %s", self._state)

        if self._ambient:
            color = self.device.appliance.status.get(self._custom_color_key, {})

            if not color:
                self._hs_color = None
                self._brightness = None
            else:
                colorvalue = color.get("value")[1:]
                rgb = color_util.rgb_hex_to_rgb_list(colorvalue)
                hsv = color_util.color_RGB_to_hsv(rgb[0], rgb[1], rgb[2])
                self._hs_color = [hsv[0], hsv[1]]
                self._brightness = ceil((hsv[2] - 10) * 255 / 90)
                _LOGGER.debug("Updated, new brightness: %s", self._brightness)

        else:
            brightness = self.device.appliance.status.get(self._brightness_key, {})
            if brightness is None:
                self._brightness = None
            else:
                self._brightness = ceil((brightness.get("value") - 10) * 255 / 90)
            _LOGGER.debug("Updated, new brightness: %s", self._brightness)
