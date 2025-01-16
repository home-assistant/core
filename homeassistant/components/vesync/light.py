"""Support for VeSync bulbs and wall dimmers."""

import logging
from typing import Any

from pyvesync.vesyncbasedevice import VeSyncBaseDevice

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import color as color_util

from .const import DEV_TYPE_TO_HA, DOMAIN, VS_COORDINATOR, VS_DEVICES, VS_DISCOVERY
from .coordinator import VeSyncDataCoordinator
from .entity import VeSyncBaseEntity

_LOGGER = logging.getLogger(__name__)
MAX_MIREDS = 370  # 1,000,000 divided by 2700 Kelvin = 370 Mireds
MIN_MIREDS = 153  # 1,000,000 divided by 6500 Kelvin = 153 Mireds


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up lights."""

    coordinator = hass.data[DOMAIN][VS_COORDINATOR]

    @callback
    def discover(devices):
        """Add new devices to platform."""
        _setup_entities(devices, async_add_entities, coordinator)

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, VS_DISCOVERY.format(VS_DEVICES), discover)
    )

    _setup_entities(hass.data[DOMAIN][VS_DEVICES], async_add_entities, coordinator)


@callback
def _setup_entities(
    devices: list[VeSyncBaseDevice],
    async_add_entities,
    coordinator: VeSyncDataCoordinator,
):
    """Check if device is a light and add entity."""
    entities: list[VeSyncBaseLightHA] = []
    for dev in devices:
        if DEV_TYPE_TO_HA.get(dev.device_type) in ("walldimmer", "bulb-dimmable"):
            entities.append(VeSyncDimmableLightHA(dev, coordinator))
        elif DEV_TYPE_TO_HA.get(dev.device_type) in ("bulb-tunable-white",):
            entities.append(VeSyncTunableWhiteLightHA(dev, coordinator))

    async_add_entities(entities, update_before_add=True)


class VeSyncBaseLightHA(VeSyncBaseEntity, LightEntity):
    """Base class for VeSync Light Devices Representations."""

    _attr_name = None

    @property
    def is_on(self) -> bool:
        """Return True if device is on."""
        return self.device.device_status == "on"

    @property
    def brightness(self) -> int:
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
        if self.color_mode == ColorMode.COLOR_TEMP and ATTR_COLOR_TEMP_KELVIN in kwargs:
            # get white temperature from HA data
            color_temp = color_util.color_temperature_kelvin_to_mired(
                kwargs[ATTR_COLOR_TEMP_KELVIN]
            )
            # ensure value between min-max supported Mireds
            color_temp = max(MIN_MIREDS, min(color_temp, MAX_MIREDS))
            # convert Mireds to Percent value that api expects
            color_temp = round(
                ((color_temp - MIN_MIREDS) / (MAX_MIREDS - MIN_MIREDS)) * 100
            )
            # flip cold/warm to what pyvesync api expects
            color_temp = 100 - color_temp
            # ensure value between 0-100
            color_temp = max(0, min(color_temp, 100))
            # call pyvesync library api method to set color_temp
            self.device.set_color_temp(color_temp)
            # flag attribute_adjustment_only, so it doesn't turn_on the device redundantly
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
            # flag attribute_adjustment_only, so it doesn't
            # turn_on the device redundantly
            attribute_adjustment_only = True
        # check flag if should skip sending the turn_on command
        if attribute_adjustment_only:
            return
        # send turn_on command to pyvesync api
        self.device.turn_on()

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        self.device.turn_off()


class VeSyncDimmableLightHA(VeSyncBaseLightHA, LightEntity):
    """Representation of a VeSync dimmable light device."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}


class VeSyncTunableWhiteLightHA(VeSyncBaseLightHA, LightEntity):
    """Representation of a VeSync Tunable White Light device."""

    _attr_color_mode = ColorMode.COLOR_TEMP
    _attr_min_color_temp_kelvin = 2700  # 370 Mireds
    _attr_max_color_temp_kelvin = 6500  # 153 Mireds
    _attr_supported_color_modes = {ColorMode.COLOR_TEMP}

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return the color temperature value in Kelvin."""
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
            return None
        # flip cold/warm
        color_temp_value = 100 - color_temp_value
        # ensure value between 0-100
        color_temp_value = max(0, min(color_temp_value, 100))
        # convert percent value to Mireds
        color_temp_value = round(
            MIN_MIREDS + ((MAX_MIREDS - MIN_MIREDS) / 100 * color_temp_value)
        )
        # ensure value between minimum and maximum Mireds
        return color_util.color_temperature_mired_to_kelvin(
            max(MIN_MIREDS, min(color_temp_value, MAX_MIREDS))
        )
