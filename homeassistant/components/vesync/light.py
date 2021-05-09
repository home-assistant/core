"""Support for VeSync bulbs and wall dimmers."""
import logging

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    COLOR_MODE_BRIGHTNESS,
    COLOR_MODE_COLOR_TEMP,
    LightEntity,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .common import VeSyncDevice
from .const import DOMAIN, VS_DISCOVERY, VS_DISPATCHERS, VS_LIGHTS

_LOGGER = logging.getLogger(__name__)

DEV_TYPE_TO_HA = {
    "ESD16": "walldimmer",
    "ESWD16": "walldimmer",
    "ESL100": "bulb-dimmable",
    "ESL100CW": "bulb-tunable-white",
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
        if DEV_TYPE_TO_HA.get(dev.device_type) in ("walldimmer", "bulb-dimmable"):
            entities.append(VeSyncDimmableLightHA(dev))
        elif DEV_TYPE_TO_HA.get(dev.device_type) in ("bulb-tunable-white"):
            entities.append(VeSyncTunableWhiteLightHA(dev))
        else:
            _LOGGER.debug(
                "%s - Unknown device type - %s", dev.device_name, dev.device_type
            )
            continue

    async_add_entities(entities, update_before_add=True)


class VeSyncBaseLight(VeSyncDevice, LightEntity):
    """Base class for VeSync Light Devices Representations."""

    def __init__(self, device):
        """Initialize the VeSync LightDevice."""
        self.device = device

    @property
    def brightness(self):
        """Get light brightness."""
        return round((int(self.device.brightness) / 100) * 255)


class VeSyncDimmableLightHA(VeSyncBaseLight, LightEntity):
    """Representation of a VeSync dimmable light device."""

    def __init__(self, device):
        """Initialize the VeSync dimmable light device."""
        super().__init__(device)
        self.device = device

    def turn_on(self, **kwargs):
        """Turn the device on."""
        if ATTR_BRIGHTNESS in kwargs:
            # get brightness from HA data
            brightness = int(kwargs[ATTR_BRIGHTNESS])
            # convert to percent that vesync api expects
            brightness = round((brightness / 255) * 100)
            # clamp to 1-100
            brightness = max(1, min(brightness, 100))
            self.device.set_brightness(brightness)
        # Avoid turning device back on if this is just a brightness adjustment
        if not self.is_on:
            self.device.turn_on()

    @property
    def color_mode(self):
        """Set color mode for this entity."""
        return COLOR_MODE_BRIGHTNESS

    @property
    def supported_color_modes(self):
        """Flag supported color_modes (in an array format)."""
        return [COLOR_MODE_BRIGHTNESS]


class VeSyncTunableWhiteLightHA(VeSyncDevice, LightEntity):
    """Representation of a VeSync Tunable White Light device."""

    def __init__(self, device):
        """Initialize the VeSync Tunable White Light device."""
        super().__init__(device)
        self.device = device

    def turn_on(self, **kwargs):
        """Turn the device on."""
        if ATTR_BRIGHTNESS in kwargs:
            # get brightness from HA data
            brightness = int(kwargs[ATTR_BRIGHTNESS])
            # convert to percent that vesync api expects
            brightness = round((brightness / 255) * 100)
            # clamp to 1-100
            brightness = max(1, min(brightness, 100))
            self.device.set_brightness(brightness)
        # Avoid turning device back on if this is just a brightness adjustment
        elif ATTR_COLOR_TEMP in kwargs:
            # get brightness from HA data
            color_temp = int(kwargs[ATTR_COLOR_TEMP])
            # flip cold/warm to what pyvesync api expects
            color_temp = 100 - color_temp
            # ensure value between 1-100
            color_temp = max(1, min(color_temp, 100))
            # pass value to pyvesync library api
            self.device.set_color_temp(color_temp)
        # Avoid turning device back on if this is just a brightness adjustment
        if not self.is_on:
            self.device.turn_on()

    @property
    def color_temp(self):
        """Get device white temperature."""
        # get value from pyvesync library api, and flip cold/warm
        color_temp_value = 100 - int(self.device.color_temp_pct)
        # ensure value between 1-100
        color_temp_value = max(1, min(color_temp_value, 100))
        return color_temp_value

    @property
    def min_mireds(self):
        """Set device coldest white temperature."""
        return 1  # 6500K

    @property
    def max_mireds(self):
        """Set device warmest white temperature."""
        return 100  # 2700K

    @property
    def color_mode(self):
        """Set color mode for this entity."""
        return COLOR_MODE_COLOR_TEMP

    @property
    def supported_color_modes(self):
        """Flag supported color_modes (in an array format)."""
        return [COLOR_MODE_COLOR_TEMP]
