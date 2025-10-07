"""Support for ADS light sources."""

from __future__ import annotations

from typing import Any

import pyads
import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    PLATFORM_SCHEMA as LIGHT_PLATFORM_SCHEMA,
    ColorMode,
    LightEntity,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CONF_ADS_VAR, DATA_ADS, STATE_KEY_STATE
from .entity import AdsEntity
from .hub import AdsHub

CONF_ADS_VAR_BRIGHTNESS = "adsvar_brightness"
CONF_ADS_VAR_COLOR_TEMP_KELVIN = "adsvar_color_temp_kelvin"
CONF_MIN_COLOR_TEMP_KELVIN = "min_color_temp_kelvin"
CONF_MAX_COLOR_TEMP_KELVIN = "max_color_temp_kelvin"
STATE_KEY_BRIGHTNESS = "brightness"
STATE_KEY_COLOR_TEMP_KELVIN = "color_temp_kelvin"

DEFAULT_NAME = "ADS Light"
PLATFORM_SCHEMA = LIGHT_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ADS_VAR): cv.string,
        vol.Optional(CONF_ADS_VAR_BRIGHTNESS): cv.string,
        vol.Optional(CONF_ADS_VAR_COLOR_TEMP_KELVIN): cv.string,
        vol.Optional(CONF_MIN_COLOR_TEMP_KELVIN): cv.positive_int,
        vol.Optional(CONF_MAX_COLOR_TEMP_KELVIN): cv.positive_int,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the light platform for ADS."""
    ads_hub = hass.data[DATA_ADS]

    ads_var_enable: str = config[CONF_ADS_VAR]
    ads_var_brightness: str | None = config.get(CONF_ADS_VAR_BRIGHTNESS)
    ads_var_color_temp_kelvin: str | None = config.get(CONF_ADS_VAR_COLOR_TEMP_KELVIN)
    min_color_temp_kelvin: int | None = config.get(CONF_MIN_COLOR_TEMP_KELVIN)
    max_color_temp_kelvin: int | None = config.get(CONF_MAX_COLOR_TEMP_KELVIN)
    name: str = config[CONF_NAME]

    add_entities(
        [
            AdsLight(
                ads_hub,
                ads_var_enable,
                ads_var_brightness,
                ads_var_color_temp_kelvin,
                min_color_temp_kelvin,
                max_color_temp_kelvin,
                name,
            )
        ]
    )


class AdsLight(AdsEntity, LightEntity):
    """Representation of ADS light."""

    def __init__(
        self,
        ads_hub: AdsHub,
        ads_var_enable: str,
        ads_var_brightness: str | None,
        ads_var_color_temp_kelvin: str | None,
        min_color_temp_kelvin: int | None,
        max_color_temp_kelvin: int | None,
        name: str,
    ) -> None:
        """Initialize AdsLight entity."""
        super().__init__(ads_hub, name, ads_var_enable)
        self._state_dict[STATE_KEY_BRIGHTNESS] = None
        self._state_dict[STATE_KEY_COLOR_TEMP_KELVIN] = None
        self._ads_var_brightness = ads_var_brightness
        self._ads_var_color_temp_kelvin = ads_var_color_temp_kelvin
        self._min_color_temp_kelvin = min_color_temp_kelvin
        self._max_color_temp_kelvin = max_color_temp_kelvin

        # Determine supported color modes
        supported_modes = {ColorMode.ONOFF}
        if ads_var_brightness is not None:
            supported_modes.add(ColorMode.BRIGHTNESS)
        if ads_var_color_temp_kelvin is not None:
            supported_modes.add(ColorMode.COLOR_TEMP)

        self._attr_supported_color_modes = supported_modes
        self._attr_color_mode = next(iter(supported_modes))

        # Set color temperature range (static config values take precedence over defaults)
        self._attr_min_color_temp_kelvin = (
            min_color_temp_kelvin if min_color_temp_kelvin is not None else 2000
        )
        self._attr_max_color_temp_kelvin = (
            max_color_temp_kelvin if max_color_temp_kelvin is not None else 6500
        )

    async def async_added_to_hass(self) -> None:
        """Register device notification."""
        await self.async_initialize_device(self._ads_var, pyads.PLCTYPE_BOOL)

        if self._ads_var_brightness is not None:
            await self.async_initialize_device(
                self._ads_var_brightness,
                pyads.PLCTYPE_UINT,
                STATE_KEY_BRIGHTNESS,
            )

        if self._ads_var_color_temp_kelvin is not None:
            await self.async_initialize_device(
                self._ads_var_color_temp_kelvin,
                pyads.PLCTYPE_UINT,
                STATE_KEY_COLOR_TEMP_KELVIN,
            )

    @property
    def brightness(self) -> int | None:
        """Return the brightness of the light (0..255)."""
        return self._state_dict[STATE_KEY_BRIGHTNESS]

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return the color temperature in Kelvin."""
        return self._state_dict[STATE_KEY_COLOR_TEMP_KELVIN]

    @property
    def min_color_temp_kelvin(self) -> int:
        """Return the minimum color temperature in Kelvin."""
        return self._attr_min_color_temp_kelvin or 2000

    @property
    def max_color_temp_kelvin(self) -> int:
        """Return the maximum color temperature in Kelvin."""
        return self._attr_max_color_temp_kelvin or 6500

    @property
    def is_on(self) -> bool:
        """Return True if the entity is on."""
        return self._state_dict[STATE_KEY_STATE]

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the light on or set a specific dimmer value."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        color_temp = kwargs.get(ATTR_COLOR_TEMP_KELVIN)

        self._ads_hub.write_by_name(self._ads_var, True, pyads.PLCTYPE_BOOL)

        if self._ads_var_brightness is not None and brightness is not None:
            self._ads_hub.write_by_name(
                self._ads_var_brightness, brightness, pyads.PLCTYPE_UINT
            )

        if self._ads_var_color_temp_kelvin is not None and color_temp is not None:
            self._ads_hub.write_by_name(
                self._ads_var_color_temp_kelvin, color_temp, pyads.PLCTYPE_UINT
            )

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        self._ads_hub.write_by_name(self._ads_var, False, pyads.PLCTYPE_BOOL)
