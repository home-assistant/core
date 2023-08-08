"""Support for VeSync bulbs and wall dimmers."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .common import VeSyncDevice
from .const import DOMAIN, VS_DISCOVERY, VS_LIGHTS

_LOGGER = logging.getLogger(__name__)

DEV_TYPE_TO_HA = {
    "ESD16": "walldimmer",
    "ESWD16": "walldimmer",
    "ESL100": "bulb-dimmable",
    "ESL100CW": "bulb-tunable-white",
    "XYD0001": "bulb-multicolor",
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up lights."""

    @callback
    def discover(devices):
        """Add new devices to platform."""
        _setup_entities(devices, async_add_entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, VS_DISCOVERY.format(VS_LIGHTS), discover)
    )

    _setup_entities(hass.data[DOMAIN][VS_LIGHTS], async_add_entities)


@callback
def _setup_entities(devices, async_add_entities):
    """Check if device is online and add entity."""
    entities = []
    for dev in devices:
        if DEV_TYPE_TO_HA.get(dev.device_type) in ("walldimmer", "bulb-dimmable"):
            entities.append(VeSyncDimmableLightHA(dev))
        elif DEV_TYPE_TO_HA.get(dev.device_type) in ("bulb-tunable-white",):
            entities.append(VeSyncTunableWhiteLightHA(dev))
        elif DEV_TYPE_TO_HA.get(dev.device_type) in ("bulb-multicolor",):
            entities.append(VeSyncMulticolorLightHA(dev))
        else:
            _LOGGER.warning(
                "%s - Unknown device type - %s", dev.device_name, dev.device_type
            )
            continue

    async_add_entities(entities, update_before_add=True)


class VeSyncBaseLight(VeSyncDevice, LightEntity):
    """Base class for VeSync Light Devices Representations."""

    @property
    def brightness(self) -> int | None:
        """Get light brightness."""
        # get value from pyvesync library api,
        result = self.device.brightness
        try:
            # check for validity of brightness value received
            brightness_value = int(result)
        except ValueError:
            # deal if any unexpected/non numeric value
            _LOGGER.debug(
                "VeSync - received unexpected 'brightness' value from pyvesync api: %s",
                result,
            )
            return 0
        # convert percent brightness to ha expected range
        return round((max(1, brightness_value) / 100) * 255)

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        attribute_adjustment_only = False
        # set white temperature
        if self.color_mode == ColorMode.COLOR_TEMP and ATTR_COLOR_TEMP in kwargs:
            # get white temperature from HA data
            color_temp = int(kwargs[ATTR_COLOR_TEMP])
            # ensure value between min-max supported Mireds
            color_temp = max(self.min_mireds, min(color_temp, self.max_mireds))
            # convert Mireds to Percent value that api expects
            color_temp = round(
                ((color_temp - self.min_mireds) / (self.max_mireds - self.min_mireds))
                * 100
            )
            # flip cold/warm to what pyvesync api expects
            color_temp = 100 - color_temp
            # ensure value between 0-100
            color_temp = max(0, min(color_temp, 100))
            # call pyvesync library api method to set color_temp
            self.device.set_color_temp(color_temp)
            # flag attribute_adjustment_only, so it doesn't turn_on the device twice
            attribute_adjustment_only = True
        # set brightness level
        if (
            self.color_mode in (ColorMode.BRIGHTNESS, ColorMode.COLOR_TEMP)
            and ATTR_BRIGHTNESS in kwargs
        ):
            # get brightness from HA data
            brightness = int(kwargs[ATTR_BRIGHTNESS])
            # ensure value between 1-255
            brightness = max(1, min(brightness, 255))
            # convert to percent that vesync api expects
            brightness = round((brightness / 255) * 100)
            # ensure value between 1-100
            brightness = max(1, min(brightness, 100))
            # call pyvesync library api method to set brightness
            self.device.set_brightness(brightness)
            # flag attribute_adjustment_only, so it doesn't turn_on the device twice
            attribute_adjustment_only = True
        # check flag if should skip sending the turn_on command
        if attribute_adjustment_only:
            return
        # send turn_on command to pyvesync api
        self.device.turn_on()


class VeSyncDimmableLightHA(VeSyncBaseLight, LightEntity):
    """Representation of a VeSync dimmable light device."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}


class VeSyncTunableWhiteLightHA(VeSyncBaseLight, LightEntity):
    """Representation of a VeSync Tunable White Light device."""

    _attr_color_mode = ColorMode.COLOR_TEMP
    _attr_max_mireds = 370  # 1,000,000 divided by 2700 Kelvin = 370 Mireds
    _attr_min_mireds = 154  # 1,000,000 divided by 6500 Kelvin = 154 Mireds
    _attr_supported_color_modes = {ColorMode.COLOR_TEMP}

    @property
    def color_temp(self) -> int | None:
        """Get device white temperature."""
        # get value from pyvesync library api,
        result = self.device.color_temp_pct
        try:
            # check for validity of brightness value received
            color_temp_value = int(result)
        except ValueError:
            # deal if any unexpected/non numeric value
            _LOGGER.debug(
                (
                    "VeSync - received unexpected 'color_temp_pct' value from pyvesync"
                    " api: %s"
                ),
                result,
            )
            return 0
        # flip cold/warm
        color_temp_value = 100 - color_temp_value
        # ensure value between 0-100
        color_temp_value = max(0, min(color_temp_value, 100))
        # convert percent value to Mireds
        color_temp_value = round(
            self.min_mireds
            + ((self.max_mireds - self.min_mireds) / 100 * color_temp_value)
        )
        # ensure value between minimum and maximum Mireds
        return max(self.min_mireds, min(color_temp_value, self.max_mireds))


class VeSyncMulticolorLightHA(VeSyncTunableWhiteLightHA, LightEntity):
    """Representation of a VeSync Multicolor Light device."""

    _attr_supported_color_modes = {ColorMode.HS, ColorMode.COLOR_TEMP}

    @property
    def color_mode(self) -> ColorMode:
        """Return the current color mode."""
        # get value from pyvesync library api,
        color_mode_value = self.device.color_mode
        if color_mode_value.lower() == "white":
            return ColorMode.COLOR_TEMP
        if color_mode_value.lower() in ["hsv", "color"]:
            return ColorMode.HS
        return ColorMode.ONOFF

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the current color mode."""
        # get value from pyvesync library api,
        color_value_hsv = None
        try:
            # get hsv named tuple from pyvesync library (hue, sat, value)
            color_value_hsv = self.device.color_value_hsv
        except ValueError:
            # deal if any unexpected/non numeric value
            _LOGGER.debug(
                "VeSync - received unexpected 'color_value_hsv' value "
                "from pyvesync api: %s",
                str(color_value_hsv),
            )
            return None
        return (color_value_hsv.hue, color_value_hsv.saturation)

    @property
    def brightness(self) -> int | None:
        """Get light brightness."""
        # If Color Mode = COLOR use HSV value
        if self.color_mode == ColorMode.HS:
            # get value from pyvesync library api,
            color_value_hsv = None
            try:
                # get hsv named tuple from pyvesync library (hue, sat, value)
                color_value_hsv = self.device.color_value_hsv
                # check for validity of brightness value received
                hsv_value = int(color_value_hsv.value)
            except ValueError:
                # deal if any unexpected/non numeric value
                _LOGGER.debug(
                    "VeSync - received unexpected 'color_value_hsv' value "
                    "from pyvesync api: %s",
                    str(color_value_hsv),
                )
                return None
            # convert percent brightness to ha expected range
            return round((max(1, hsv_value) / 100) * 255)

        # get value from pyvesync library api,
        result = self.device.brightness
        try:
            # check for validity of brightness value received
            brightness_value = int(result)
        except ValueError:
            # deal if any unexpected/non numeric value
            _LOGGER.debug(
                "VeSync - received unexpected 'brightness' value "
                "from pyvesync api: %s",
                str(result),
            )
            return None
        # convert percent brightness to ha expected range
        return round((max(1, brightness_value) / 100) * 255)

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the device on, and adjust attributes."""
        # The Valceno Multicolor bulb use the V2 API endpoint,
        #   so it has the capability of setting every light parameter in a single call

        # initialize vars
        attribute_adjustments = False
        brightness = None
        color_temp = None
        color_saturation = None
        color_hue = None
        color_mode = None

        # set color hue + saturation
        if (
            self.color_mode in (ColorMode.COLOR_TEMP, ColorMode.HS)
            and ATTR_HS_COLOR in kwargs
        ):
            # flag attribute_adjustment_only, so it doesn't turn_on the device twice
            attribute_adjustments = True
            # set color_mode to white
            color_mode = "hsv"
            # get HS color from HA data
            color_hue = float(kwargs[ATTR_HS_COLOR][0])
            color_saturation = int(round(kwargs[ATTR_HS_COLOR][1]))

        # set white temperature
        if (
            self.color_mode in (ColorMode.COLOR_TEMP, ColorMode.HS)
            and ATTR_COLOR_TEMP in kwargs
        ):
            # flag attribute_adjustment_only, so it doesn't turn_on the device twice
            attribute_adjustments = True
            # set color_mode to white
            color_mode = "white"
            # get white temperature from HA data
            color_temp = int(kwargs[ATTR_COLOR_TEMP])
            # ensure value between min-max supported Mireds
            color_temp = max(self.min_mireds, min(color_temp, self.max_mireds))
            # convert Mireds to Percent value that api expects
            color_temp = round(
                ((color_temp - self.min_mireds) / (self.max_mireds - self.min_mireds))
                * 100
            )
            # flip cold/warm to what pyvesync api expects
            color_temp = 100 - color_temp
            # ensure value between 0-100
            color_temp = max(0, min(color_temp, 100))

        # set brightness level
        if (
            self.color_mode
            in (ColorMode.BRIGHTNESS, ColorMode.COLOR_TEMP, ColorMode.HS)
            and ATTR_BRIGHTNESS in kwargs
        ):
            # flag attribute_adjustment_only, so it doesn't turn_on the device twice
            attribute_adjustments = True
            # get brightness from HA data
            brightness = int(kwargs[ATTR_BRIGHTNESS])
            # ensure value between 1-255
            brightness = max(1, min(brightness, 255))
            # convert to percent that vesync api expects
            brightness = round((brightness / 255) * 100)
            # ensure value between 1-100
            brightness = max(1, min(brightness, 100))

        # construct parameters dictionary
        params = {
            "brightness": brightness,
            "color_temp": color_temp,
            "color_mode": color_mode,
            "color_saturation": color_saturation,
            "color_hue": color_hue,
        }
        # call pyvesync library api method to set light status
        self.device.set_status(**params)
        _LOGGER.debug(
            "Vesync set_status() params: \n %s",
            str(params),
        )

        # check flag if should skip sending the basic turn_on command
        if attribute_adjustments:
            return
        # send turn_on command to pyvesync library
        self.device.turn_on()
