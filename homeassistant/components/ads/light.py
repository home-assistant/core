"""Support for ADS light sources."""

from __future__ import annotations

from typing import Any

import pyads
import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    PLATFORM_SCHEMA as LIGHT_PLATFORM_SCHEMA,
    ColorMode,
    LightEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    ADS_TYPEMAP,
    CONF_ADS_FIELDS,
    CONF_ADS_HUB,
    CONF_ADS_HUB_DEFAULT,
    CONF_ADS_SYMBOLS,
    CONF_ADS_TEMPLATE,
    DOMAIN,
    STATE_KEY_BRIGHTNESS,
    STATE_KEY_COLOR_MODE,
    STATE_KEY_COLOR_TEMP_KELVIN,
    STATE_KEY_HUE,
    STATE_KEY_SATURATION,
    STATE_KEY_STATE,
    AdsDiscoveryKeys,
    AdsLightKeys,
    AdsType,
)
from .entity import AdsEntity
from .hub import AdsHub

PLATFORM_SCHEMA = LIGHT_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_ADS_HUB, default=CONF_ADS_HUB_DEFAULT): cv.string,
        vol.Required(AdsLightKeys.VAR): cv.string,
        vol.Optional(AdsLightKeys.TYPE, default=AdsType.BYTE): vol.All(
            vol.Coerce(AdsType),
            vol.In(
                [
                    AdsType.BYTE,
                    AdsType.INT,
                    AdsType.UINT,
                    AdsType.SINT,
                    AdsType.USINT,
                    AdsType.DINT,
                    AdsType.UDINT,
                    AdsType.WORD,
                    AdsType.DWORD,
                ]
            ),
        ),
        vol.Optional(AdsLightKeys.TYPE_MODE, default=AdsType.UINT): vol.All(
            vol.Coerce(AdsType),
            vol.In(
                [
                    AdsType.BYTE,
                    AdsType.INT,
                    AdsType.UINT,
                    AdsType.SINT,
                    AdsType.USINT,
                    AdsType.DINT,
                    AdsType.UDINT,
                    AdsType.WORD,
                    AdsType.DWORD,
                ]
            ),
        ),
        vol.Optional(AdsLightKeys.VAR_COLOR_MODE): cv.string,
        vol.Optional(AdsLightKeys.VAR_BRIGHTNESS): cv.string,
        vol.Optional(AdsLightKeys.VAL_MIN_BRIGHTNESS, default=0): vol.Coerce(int),
        vol.Optional(AdsLightKeys.VAL_MAX_BRIGHTNESS, default=255): vol.Coerce(int),
        vol.Optional(AdsLightKeys.VAR_COLOR_TEMP_KELVIN): cv.string,
        vol.Optional(AdsLightKeys.VAL_MIN_COLOR_TEMP_KELVIN, default=2000): vol.Coerce(
            int
        ),
        vol.Optional(AdsLightKeys.VAL_MAX_COLOR_TEMP_KELVIN, default=6500): vol.Coerce(
            int
        ),
        vol.Optional(AdsLightKeys.VAR_HUE): cv.string,
        vol.Optional(AdsLightKeys.VAR_SATURATION): cv.string,
        vol.Optional(AdsLightKeys.NAME, default=AdsLightKeys.DEFAULT_NAME): cv.string,
    }
)


def _color_modes_to_int(modes: list[ColorMode]) -> int:
    """Convert a list of supported ColorModes to a bitmask."""
    mapping = {
        ColorMode.ONOFF: 1,
        ColorMode.BRIGHTNESS: 2,
        ColorMode.COLOR_TEMP: 4,
        ColorMode.HS: 8,
    }
    return sum(mapping[mode] for mode in modes if mode in mapping)


def _int_to_color_modes(value: int) -> list[ColorMode]:
    """Convert a bitmask to a list of supported ColorModes."""
    mapping = {
        1: ColorMode.ONOFF,
        2: ColorMode.BRIGHTNESS,
        4: ColorMode.COLOR_TEMP,
        8: ColorMode.HS,
    }
    return [mode for bit, mode in mapping.items() if value & bit]


def _map_color_mode(mode: int) -> ColorMode:
    """Map integer mode to ColorMode enum."""
    mapping = {
        1: ColorMode.ONOFF,
        2: ColorMode.BRIGHTNESS,
        4: ColorMode.COLOR_TEMP,
        8: ColorMode.HS,
    }
    return mapping.get(mode, ColorMode.ONOFF)


def _map_color_mode_to_int(mode: ColorMode) -> int:
    """Map ColorMode enum to integer mode."""
    mapping = {
        ColorMode.ONOFF: 1,
        ColorMode.BRIGHTNESS: 2,
        ColorMode.COLOR_TEMP: 4,
        ColorMode.HS: 8,
    }
    return mapping.get(mode, 1)  # Default to 1 if the mode is not found


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the light platform for ADS."""

    if discovery_info is not None:
        _hub_name = discovery_info.get(CONF_ADS_HUB)
        _hub_key = f"{DOMAIN}_{_hub_name}"
        _ads_hub = hass.data.get(_hub_key)
        if not _ads_hub:
            return

        _entities = []
        _symbols = discovery_info.get(CONF_ADS_SYMBOLS, [])
        _template = discovery_info.get(CONF_ADS_TEMPLATE, {})
        _fields = _template.get(CONF_ADS_FIELDS, {})

        for _symbol in _symbols:
            _path = _symbol.get(AdsDiscoveryKeys.ADSPATH)
            _name = _symbol.get(AdsDiscoveryKeys.NAME)
            _device_type = _symbol.get(AdsDiscoveryKeys.DEVICE_TYPE)
            if not _name or not _device_type:
                continue

            _ads_type = AdsType(_fields.get(AdsLightKeys.TYPE))
            _ads_type_mode = AdsType(_fields.get(AdsLightKeys.TYPE_MODE))
            _ads_val_min_brightness = int(_fields.get(AdsLightKeys.VAL_MIN_BRIGHTNESS))
            _ads_val_max_brightness = int(_fields.get(AdsLightKeys.VAL_MAX_BRIGHTNESS))
            _ads_val_min_color_temp_kelvin = int(
                _fields.get(AdsLightKeys.VAL_MIN_COLOR_TEMP_KELVIN)
            )
            _ads_val_max_color_temp_kelvin = int(
                _fields.get(AdsLightKeys.VAL_MAX_COLOR_TEMP_KELVIN)
            )

            _ads_var_enable = _path + "." + _fields.get(AdsLightKeys.VAR)

            _supported_modes = _int_to_color_modes(_device_type)
            _ads_var_color_mode = _path + "." + _fields.get(AdsLightKeys.VAR_COLOR_MODE)

            _ads_var_brightness = (
                _path + "." + _fields.get(AdsLightKeys.VAR_BRIGHTNESS)
                if ColorMode.BRIGHTNESS in _supported_modes
                else None
            )

            _ads_var_color_temp_kelvin = (
                _path + "." + _fields.get(AdsLightKeys.VAR_COLOR_TEMP_KELVIN)
                if ColorMode.COLOR_TEMP in _supported_modes
                else None
            )

            _ads_var_hue = (
                _path + "." + _fields.get(AdsLightKeys.VAR_HUE)
                if ColorMode.HS in _supported_modes
                else None
            )

            _ads_var_saturation = (
                _path + "." + _fields.get(AdsLightKeys.VAR_SATURATION)
                if ColorMode.HS in _supported_modes
                else None
            )

            _entities.append(
                AdsLight(
                    ads_hub=_ads_hub,
                    name=_name,
                    ads_type=_ads_type,
                    ads_type_mode=_ads_type_mode,
                    ads_var_enable=_ads_var_enable,
                    ads_var_brightness=_ads_var_brightness,
                    ads_val_min_brightness=_ads_val_min_brightness,
                    ads_val_max_brightness=_ads_val_max_brightness,
                    ads_var_color_temp_kelvin=_ads_var_color_temp_kelvin,
                    ads_val_min_color_temp_kelvin=_ads_val_min_color_temp_kelvin,
                    ads_val_max_color_temp_kelvin=_ads_val_max_color_temp_kelvin,
                    ads_var_hue=_ads_var_hue,
                    ads_var_saturation=_ads_var_saturation,
                    ads_var_color_mode=_ads_var_color_mode,
                )
            )

        add_entities(_entities)
        return

    hub_name: str = config[CONF_ADS_HUB]
    hub_key = f"{DOMAIN}_{hub_name}"
    ads_hub = hass.data.get(hub_key)
    if not ads_hub:
        return

    name: str = config[AdsLightKeys.NAME]
    ads_type: AdsType = config[AdsLightKeys.TYPE]
    ads_type_mode: AdsType = config[AdsLightKeys.TYPE_MODE]
    ads_val_min_brightness: int = config[AdsLightKeys.VAL_MIN_BRIGHTNESS]
    ads_val_max_brightness: int = config[AdsLightKeys.VAL_MAX_BRIGHTNESS]
    ads_val_min_color_temp_kelvin: int = config[AdsLightKeys.VAL_MIN_COLOR_TEMP_KELVIN]
    ads_val_max_color_temp_kelvin: int = config[AdsLightKeys.VAL_MAX_COLOR_TEMP_KELVIN]

    ads_var_enable: str = config[AdsLightKeys.VAR]
    ads_var_brightness: str | None = config.get(AdsLightKeys.VAR_BRIGHTNESS)
    ads_var_color_temp_kelvin: str | None = config.get(
        AdsLightKeys.VAR_COLOR_TEMP_KELVIN
    )
    ads_var_hue: str | None = config.get(AdsLightKeys.VAR_HUE)
    ads_var_saturation: str | None = config.get(AdsLightKeys.VAR_SATURATION)
    ads_var_color_mode: str | None = config.get(AdsLightKeys.VAR_COLOR_MODE)

    add_entities(
        [
            AdsLight(
                ads_hub=ads_hub,
                name=name,
                ads_type=ads_type,
                ads_type_mode=ads_type_mode,
                ads_var_enable=ads_var_enable,
                ads_var_brightness=ads_var_brightness,
                ads_val_min_brightness=ads_val_min_brightness,
                ads_val_max_brightness=ads_val_max_brightness,
                ads_var_color_temp_kelvin=ads_var_color_temp_kelvin,
                ads_val_min_color_temp_kelvin=ads_val_min_color_temp_kelvin,
                ads_val_max_color_temp_kelvin=ads_val_max_color_temp_kelvin,
                ads_var_hue=ads_var_hue,
                ads_var_saturation=ads_var_saturation,
                ads_var_color_mode=ads_var_color_mode,
            )
        ]
    )


class AdsLight(AdsEntity, LightEntity):
    """Representation of ADS light."""

    def __init__(
        self,
        ads_hub: AdsHub,
        ads_type: AdsType,
        ads_type_mode: AdsType,
        name: str,
        ads_var_enable: str,
        ads_var_brightness: str | None,
        ads_val_min_brightness: int,
        ads_val_max_brightness: int,
        ads_var_color_temp_kelvin: str | None,
        ads_val_min_color_temp_kelvin: int,
        ads_val_max_color_temp_kelvin: int,
        ads_var_hue: str | None,
        ads_var_saturation: str | None,
        ads_var_color_mode: str | None,
    ) -> None:
        """Initialize AdsLight entity."""
        super().__init__(ads_hub, name, ads_var_enable)

        self._state_dict[STATE_KEY_BRIGHTNESS] = None
        self._state_dict[STATE_KEY_COLOR_TEMP_KELVIN] = None
        self._state_dict[STATE_KEY_HUE] = None
        self._state_dict[STATE_KEY_SATURATION] = None
        self._state_dict[STATE_KEY_COLOR_MODE] = None

        self._ads_type = ads_type
        self._ads_type_mode = ads_type_mode

        self._ads_var_brightness = ads_var_brightness
        self._ads_val_min_brightness = ads_val_min_brightness
        self._ads_val_max_brightness = ads_val_max_brightness
        self._ads_var_color_temp_kelvin = ads_var_color_temp_kelvin
        self._ads_val_min_color_temp_kelvin = ads_val_min_color_temp_kelvin
        self._ads_val_max_color_temp_kelvin = ads_val_max_color_temp_kelvin
        self._ads_var_hue = ads_var_hue
        self._ads_var_saturation = ads_var_saturation
        self._ads_var_color_mode = ads_var_color_mode

        # Initialize supported color modes
        self._attr_supported_color_modes: set[str] = set()

        # Add supported color modes based on available ADS variables
        if ads_var_hue and ads_var_saturation:
            self._attr_supported_color_modes.add(ColorMode.HS)

        if ads_var_color_temp_kelvin:
            self._attr_supported_color_modes.add(ColorMode.COLOR_TEMP)
            self._attr_min_color_temp_kelvin = self._ads_val_min_color_temp_kelvin
            self._attr_max_color_temp_kelvin = self._ads_val_max_color_temp_kelvin

        if not self._attr_supported_color_modes:
            if ads_var_brightness:
                self._attr_supported_color_modes.add(ColorMode.BRIGHTNESS)
            else:
                self._attr_supported_color_modes.add(ColorMode.ONOFF)

        # Set the current color mode (default to the first one in the set)
        self._attr_color_mode = next(iter(self._attr_supported_color_modes))

    async def async_added_to_hass(self) -> None:
        """Register device notification."""
        # Initialize the main ADS variable
        if self._ads_var is not None:
            await self.async_initialize_device(
                self._ads_var, pyads.PLCTYPE_BOOL, STATE_KEY_STATE
            )

        # Optional: Initialize the brightness variable
        if self._ads_var_brightness:
            await self.async_initialize_device(
                self._ads_var_brightness,
                ADS_TYPEMAP[self._ads_type],
                STATE_KEY_BRIGHTNESS,
            )

        # Optional: Initialize the color temperature variable in Kelvin
        if self._ads_var_color_temp_kelvin:
            await self.async_initialize_device(
                self._ads_var_color_temp_kelvin,
                ADS_TYPEMAP[self._ads_type],
                STATE_KEY_COLOR_TEMP_KELVIN,
            )

        # Optional: Initialize the color variables (Hue, Saturation)
        if self._ads_var_hue:
            await self.async_initialize_device(
                self._ads_var_hue, ADS_TYPEMAP[self._ads_type], STATE_KEY_HUE
            )
        if self._ads_var_saturation:
            await self.async_initialize_device(
                self._ads_var_saturation,
                ADS_TYPEMAP[self._ads_type],
                STATE_KEY_SATURATION,
            )

        if self._ads_var_color_mode is not None:
            await self.async_initialize_device(
                self._ads_var_color_mode,
                ADS_TYPEMAP[self._ads_type_mode],
                STATE_KEY_COLOR_MODE,
            )

    def scale_value(
        self, value: int, src_min: int, src_max: int, dest_min: int, dest_max: int
    ) -> int:
        """Scale a value from one range (src_min-src_max) to another (dest_min-dest_max)."""
        diff_src = src_max - src_min
        if diff_src == 0:
            return dest_min
        scale_factor = (value - src_min) / diff_src
        return int(dest_min + scale_factor * (dest_max - dest_min))

    def scale_brightness_to_ads(self, hass_brightness: int) -> int:
        """Scale brightness from Home Assistant range (0-255) to ADS range."""
        return self.scale_value(
            hass_brightness,
            0,
            255,
            self._ads_val_min_brightness,
            self._ads_val_max_brightness,
        )

    def scale_brightness_from_ads(self, ads_brightness: int) -> int:
        """Scale brightness from ADS range to Home Assistant range (0-255)."""
        return self.scale_value(
            ads_brightness,
            self._ads_val_min_brightness,
            self._ads_val_max_brightness,
            0,
            255,
        )

    @property
    def color_mode(self) -> ColorMode | str | None:
        """Return the color mode of the light only if HS or COLOR_TEMP is supported."""
        colormode = _map_color_mode(self._state_dict[STATE_KEY_COLOR_MODE])
        if colormode in self._attr_supported_color_modes:
            return colormode
        return ColorMode.UNKNOWN

    @property
    def brightness(self) -> int | None:
        """Return the brightness of the light (0..255)."""
        ads_brightness = self._state_dict[STATE_KEY_BRIGHTNESS]
        if ads_brightness is not None:
            return self.scale_brightness_from_ads(ads_brightness)
        return None

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return the color temperature in Kelvin."""
        return self._state_dict[STATE_KEY_COLOR_TEMP_KELVIN]

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hue and saturation in HS format."""
        hue = self._state_dict[STATE_KEY_HUE]
        saturation = self._state_dict[STATE_KEY_SATURATION]
        if hue is not None and saturation is not None:
            return hue, saturation
        return None

    @property
    def is_on(self) -> bool:
        """Return True if the entity is on."""
        return self._state_dict[STATE_KEY_STATE]

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the light on or set a specific value."""
        self._ads_hub.write_by_name(self._ads_var, True, pyads.PLCTYPE_BOOL)

        # Brightness
        if self._ads_var_brightness and ATTR_BRIGHTNESS in kwargs:
            hass_brightness = kwargs[ATTR_BRIGHTNESS]
            ads_brightness = self.scale_brightness_to_ads(hass_brightness)
            self._ads_hub.write_by_name(
                self._ads_var_brightness, ads_brightness, ADS_TYPEMAP[self._ads_type]
            )

        # Color Temperature in Kelvin
        if self._ads_var_color_temp_kelvin and ATTR_COLOR_TEMP_KELVIN in kwargs:
            color_temp_kelvin = kwargs[ATTR_COLOR_TEMP_KELVIN]
            self._ads_hub.write_by_name(
                self._ads_var_color_temp_kelvin,
                color_temp_kelvin,
                ADS_TYPEMAP[self._ads_type],
            )

        # Hue and Saturation
        if self._ads_var_hue and self._ads_var_saturation and ATTR_HS_COLOR in kwargs:
            hue, saturation = kwargs[ATTR_HS_COLOR]
            self._ads_hub.write_by_name(
                self._ads_var_hue, int(hue), ADS_TYPEMAP[self._ads_type]
            )
            self._ads_hub.write_by_name(
                self._ads_var_saturation, int(saturation), ADS_TYPEMAP[self._ads_type]
            )

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        self._ads_hub.write_by_name(self._ads_var, False, pyads.PLCTYPE_BOOL)
