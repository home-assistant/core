"""Support for WiLight lights."""
import asyncio
import logging

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    LightEntity,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import WiLightDevice
from .const import (
    DOMAIN,
    DT_PENDING,
    ITEM_LIGHT,
    LIGHT_COLOR,
    LIGHT_DIMMER,
    LIGHT_NONE,
    LIGHT_ON_OFF,
    SUPPORT_NONE,
)

_LOGGER = logging.getLogger(__name__)


def devices_from_discovered_wilight(hass, wilight):
    """Parse configuration and add WiLight light devices."""
    devices = []
    for item in wilight.items:
        if item["type"] != ITEM_LIGHT:
            continue
        if item["sub_type"] == LIGHT_NONE:
            continue
        index = item["index"]
        item_name = item["name"]
        aux1 = item["type"]
        aux2 = item["sub_type"]
        item_type = f"{aux1}.{aux2}"
        if item["sub_type"] == LIGHT_ON_OFF:
            device = WiLightLightOnOff(wilight, index, item_name, item_type)
        elif item["sub_type"] == LIGHT_DIMMER:
            device = WiLightLightDimmer(wilight, index, item_name, item_type)
        elif item["sub_type"] == LIGHT_COLOR:
            device = WiLightLightColor(wilight, index, item_name, item_type)
        else:
            continue
        devices.append(device)

    return devices


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up WiLights lights."""

    async def _discovered_wilight(hass, device):
        """Handle a discovered WiLight device."""
        async_add_entities(devices_from_discovered_wilight(hass, device))

    async_dispatcher_connect(hass, f"{DOMAIN}.light", _discovered_wilight)

    await asyncio.gather(
        *[
            _discovered_wilight(hass, device)
            for device in hass.data[DOMAIN][DT_PENDING].pop("light")
        ]
    )


class WiLightLightOnOff(WiLightDevice, LightEntity):
    """Representation of a WiLights light on-off."""

    def __init__(self, *args, **kwargs):
        """Initialize the device."""
        WiLightDevice.__init__(self, *args, **kwargs)
        self._on = False

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_NONE

    @property
    def is_on(self):
        """Return true if device is on."""
        if "on" in self._status:
            self._on = self._status["on"]
        return self._on

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        await self._client.turn_on(self._index)

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        await self._client.turn_off(self._index)


class WiLightLightDimmer(WiLightDevice, LightEntity):
    """Representation of a WiLights light dimmer."""

    def __init__(self, *args, **kwargs):
        """Initialize the device."""
        WiLightDevice.__init__(self, *args, **kwargs)
        self._on = False
        self._brightness = 0

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        if "brightness" in self._status:
            self._brightness = int(self._status["brightness"])
        return self._brightness

    @property
    def is_on(self):
        """Return true if device is on."""
        if "on" in self._status:
            self._on = self._status["on"]
        return self._on

    async def async_turn_on(self, **kwargs):
        """Turn the device on,set brightness if needed."""
        # Dimmer switches use a range of [0, 255] to control
        # brightness. Level 255 might mean to set it to previous value
        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS]
            await self._client.set_brightness(self._index, brightness)
        else:
            await self._client.turn_on(self._index)

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        await self._client.turn_off(self._index)


def wilight_to_hass_hue(value):
    """Convert wilight hue 1..255 to hass 0..360 scale."""
    return min(360, round((value * 360) / 255, 3))


def hass_to_wilight_hue(value):
    """Convert hass hue 0..360 to wilight 1..255 scale."""
    return min(255, round((value * 255) / 360))


def wilight_to_hass_saturation(value):
    """Convert wilight saturation 1..255 to hass 0..100 scale."""
    return min(100, round((value * 100) / 255, 3))


def hass_to_wilight_saturation(value):
    """Convert hass saturation 0..100 to wilight 1..255 scale."""
    return min(255, round((value * 255) / 100))


class WiLightLightColor(WiLightDevice, LightEntity):
    """Representation of a WiLights light rgb."""

    def __init__(self, *args, **kwargs):
        """Initialize the device."""
        WiLightDevice.__init__(self, *args, **kwargs)
        self._on = False
        self._brightness = 0
        self._hue = 0
        self._saturation = 100

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS + SUPPORT_COLOR

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        if "brightness" in self._status:
            self._brightness = int(self._status["brightness"])
        return self._brightness

    @property
    def hs_color(self):
        """Return the hue and saturation color value [float, float]."""
        if "hue" in self._status:
            self._hue = wilight_to_hass_hue(int(self._status["hue"]))
        if "saturation" in self._status:
            self._saturation = wilight_to_hass_saturation(
                int(self._status["saturation"])
            )
        return [self._hue, self._saturation]

    @property
    def is_on(self):
        """Return true if device is on."""
        if "on" in self._status:
            self._on = self._status["on"]
        return self._on

    async def async_turn_on(self, **kwargs):
        """Turn the device on,set brightness if needed."""
        # Brightness use a range of [0, 255] to control
        # Hue use a range of [0, 360] to control
        # Saturation use a range of [0, 100] to control
        if ATTR_BRIGHTNESS in kwargs and ATTR_HS_COLOR in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS]
            hue = hass_to_wilight_hue(kwargs[ATTR_HS_COLOR][0])
            saturation = hass_to_wilight_saturation(kwargs[ATTR_HS_COLOR][1])
            await self._client.set_hsb_color(self._index, hue, saturation, brightness)
        elif ATTR_BRIGHTNESS in kwargs and ATTR_HS_COLOR not in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS]
            await self._client.set_brightness(self._index, brightness)
        elif ATTR_BRIGHTNESS not in kwargs and ATTR_HS_COLOR in kwargs:
            hue = hass_to_wilight_hue(kwargs[ATTR_HS_COLOR][0])
            saturation = hass_to_wilight_saturation(kwargs[ATTR_HS_COLOR][1])
            await self._client.set_hs_color(self._index, hue, saturation)
        else:
            await self._client.turn_on(self._index)

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        await self._client.turn_off(self._index)
