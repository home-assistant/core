"""Support for VeSync lights."""
import logging

from homeassistant.components.light import (ATTR_BRIGHTNESS,
                                            SUPPORT_BRIGHTNESS,
                                            SUPPORT_COLOR, SUPPORT_COLOR_TEMP,
                                            Light)
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from . import CONF_LIGHTS
from .common import async_add_entities_retry
from .const import VS_DISCOVERY, VS_DISPATCHERS

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'vesync'


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up switches."""
    async def async_discover(devices):
        await async_add_entities_retry(
            hass,
            async_add_entities,
            devices,
            _async_setup_entity)

    disp = async_dispatcher_connect(
        hass, VS_DISCOVERY.format(CONF_LIGHTS), async_discover)

    hass.data[DOMAIN][VS_DISPATCHERS].append(disp)

    await async_add_entities_retry(
        hass,
        async_add_entities,
        hass.data[DOMAIN][CONF_LIGHTS],
        _async_setup_entity
    )
    return True


async def _async_setup_entity(device, async_add_entities):
    """Add VeSync Light Bulbs."""
    async_add_entities(
        [VeSyncSmartBulb(device)],
        update_before_add=True
    )


def brightness_to_percentage(byt):
    """Convert brightness from absolute 0..255 to percentage."""
    return int((byt * 100.0) / 255.0)


def brightness_from_percentage(percent):
    """Convert percentage to absolute value 0..255."""
    return (percent * 255.0) / 100.0


class VeSyncSmartBulb(Light):
    """Representation of VeSync Light Bulb."""

    def __init__(self, smartbulb):
        """Initialize Bulb."""
        self.smartbulb = smartbulb
        self._dimmable = smartbulb.dimmable_feature
        self._bulb_temp_feature = smartbulb.bulb_temp_feature
        self._color_change_feature = smartbulb.color_change_feature
        self._brightness = None
        self._supported_features = None

    @property
    def unique_id(self):
        """Return the ID of this bulb."""
        if isinstance(self.smartbulb.sub_device_no, int):
            return (self.smartbulb.cid + str(self.smartbulb.sub_device_no))
        else:
            return self.smartbulb.cid

    @property
    def name(self):
        """Return the name of the bulb."""
        return self.smartbulb.device_name

    def turn_on(self, **kwargs):
        """Turn on bulb."""
        if self._supported_features is None:
            self.get_features()
        self.smartbulb.turn_on()
        if ATTR_BRIGHTNESS in kwargs:
            brightness = brightness_to_percentage(
                kwargs.get(ATTR_BRIGHTNESS, 255))
            self.smartbulb.set_brightness(brightness)

    def turn_off(self, **kwargs):
        """Turn off bulb."""
        self.smartbulb.turn_off()

    @property
    def is_on(self):
        """Return true if bulb is on."""
        return (self.smartbulb.device_status == 'on')

    @property
    def available(self):
        """Return true if device is available."""
        return (self.smartbulb.connection_status == 'online')

    @property
    def brightness(self):
        """Return Brightness of device between 0...255."""
        if self._dimmable:
            return self._brightness

    @property
    def supported_features(self):
        """Flag supported features."""
        return self._supported_features

    def get_features(self):
        """Determine Supported Features of Bulb."""
        self._supported_features = 0

        if self._dimmable:
            self._supported_features += SUPPORT_BRIGHTNESS
        if self._bulb_temp_feature:
            self._supported_features += SUPPORT_COLOR_TEMP
        if self._color_change_feature:
            self._supported_features += SUPPORT_COLOR

    def update(self):
        """Update smart bulb state."""
        if self._supported_features is None:
            self.get_features()
        self.smartbulb.update()
        if self._supported_features & SUPPORT_BRIGHTNESS:
            self._brightness = brightness_from_percentage(
                int(self.smartbulb.brightness))
