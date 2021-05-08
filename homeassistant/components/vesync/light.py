"""Support for VeSync bulbs and wall dimmers."""
import logging

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    COLOR_MODE_BRIGHTNESS,
    COLOR_MODE_COLOR_TEMP,
    COLOR_MODE_ONOFF,
    LightEntity,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .common import VeSyncDevice
from .const import DOMAIN, VS_DISCOVERY, VS_DISPATCHERS, VS_LIGHTS

_LOGGER = logging.getLogger(__name__)

DEV_TYPE_TO_HA = {
    "ESD16": "dimmerswitch",
    "ESWD16": "dimmerswitch",
    "ESL100": "bulb",
    "ESL100CW": "bulb",
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up lights."""

    async def async_discover(devices):
        """Add new devices to platform."""
        _async_setup_entities(devices, async_add_entities)

    disp = async_dispatcher_connect(
        hass, VS_DISCOVERY.format(VS_LIGHTS), async_discover
    )
    hass.data[DOMAIN][VS_DISPATCHERS].append(disp)

    _async_setup_entities(hass.data[DOMAIN][VS_LIGHTS], async_add_entities)


@callback
def _async_setup_entities(devices, async_add_entities):
    """Check if device is online and add entity."""
    entities = []
    for dev in devices:
        if DEV_TYPE_TO_HA.get(dev.device_type) == "dimmerswitch":
            entities.append(VeSyncDimmerHA(dev))
        elif DEV_TYPE_TO_HA.get(dev.device_type) == "bulb":
            entities.append(VeSyncBulbHA(dev))
        else:
            _LOGGER.debug(
                "%s - Unknown device type - %s", dev.device_name, dev.device_type
            )
            continue

    async_add_entities(entities, update_before_add=True)


class VeSyncDimmerHA(VeSyncDevice, LightEntity):
    """Representation of a VeSync dimmer."""

    def __init__(self, dimmer):
        """Initialize the VeSync dimmer device."""
        super().__init__(dimmer)
        self.dimmer = dimmer

    def turn_on(self, **kwargs):
        """Turn the device on."""
        if ATTR_BRIGHTNESS in kwargs:
            # get brightness from HA data
            brightness = int(kwargs[ATTR_BRIGHTNESS])
            # convert to percent that vesync api expects
            brightness = round((brightness / 255) * 100)
            # clamp to 1-100
            brightness = max(1, min(brightness, 100))
            self.dimmer.set_brightness(brightness)
        # Avoid turning device back on if this is just a brightness adjustment
        if not self.is_on:
            self.device.turn_on()

    # @property
    # def supported_features(self):
    #     """Get supported features for this entity."""
    #     return COLOR_MODE_BRIGHTNESS

    @property
    def brightness(self):
        """Get dimmer brightness."""
        return round((int(self.dimmer.brightness) / 100) * 255)

    @property
    def color_mode(self):
        """Set color mode for this entity."""
        return COLOR_MODE_BRIGHTNESS

    @property
    def supported_color_modes(self):
        """Flag supported color_modes."""
        supported_color_modes = set()
        Dimmable = True
        Tunable_white = False
        if Tunable_white:
            supported_color_modes.add(COLOR_MODE_COLOR_TEMP)
        if not supported_color_modes and Dimmable:
            supported_color_modes.add(COLOR_MODE_BRIGHTNESS)
        if not supported_color_modes:
            supported_color_modes.add(COLOR_MODE_ONOFF)
        return supported_color_modes


class VeSyncBulbHA(VeSyncDevice, LightEntity):
    """Representation of a VeSync bulb."""

    def __init__(self, bulb):
        """Initialize the VeSync bulb device."""
        super().__init__(bulb)
        self.bulb = bulb

    def turn_on(self, **kwargs):
        """Turn the device on."""
        if ATTR_BRIGHTNESS in kwargs:
            # get brightness from HA data
            brightness = int(kwargs[ATTR_BRIGHTNESS])
            # convert to percent that vesync api expects
            brightness = round((brightness / 255) * 100)
            # clamp to 1-100
            brightness = max(1, min(brightness, 100))
            self.bulb.set_brightness(brightness)
        # Avoid turning device back on if this is just a brightness adjustment
        elif ATTR_COLOR_TEMP in kwargs:
            # get brightness from HA data
            color_temp = int(kwargs[ATTR_COLOR_TEMP])
            # convert to percent that vesync api expects
            color_temp = round(color_temp)
            # clamp to 1-100
            color_temp = max(1, min(color_temp, 100))
            self.bulb.set_color_temp(color_temp)
        # Avoid turning device back on if this is just a brightness adjustment
        if not self.is_on:
            self.device.turn_on()

    # @property
    # def supported_features(self):
    #    """Get supported features for this entity."""
    #    return ##%%##%#

    @property
    def brightness(self):
        """Get bulb brightness."""
        return round((int(self.bulb.brightness) / 100) * 255)

    @property
    def color_temp(self):
        """Get bulb white temperature."""
        return self.bulb.color_temp_pct

    @property
    def color_mode(self):
        """Set color mode for this entity."""
        return COLOR_MODE_COLOR_TEMP

    @property
    def supported_color_modes(self):
        """Flag supported color_modes."""
        supported_color_modes = set()
        Dimmable = False
        Tunable_white = True
        if Tunable_white:
            supported_color_modes.add(COLOR_MODE_COLOR_TEMP)
        if not supported_color_modes and Dimmable:
            supported_color_modes.add(COLOR_MODE_BRIGHTNESS)
        if not supported_color_modes:
            supported_color_modes.add(COLOR_MODE_ONOFF)
        return supported_color_modes
