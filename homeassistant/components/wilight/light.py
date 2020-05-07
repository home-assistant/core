"""Support for WiLight lights."""
import logging

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    LightEntity,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from . import DATA_DEVICE_REGISTER, WiLightDevice
from .const import (
    ITEM_LIGHT,
    LIGHT_COLOR,
    LIGHT_DIMMER,
    LIGHT_NONE,
    LIGHT_ON_OFF,
    SUPPORT_NONE,
)

_LOGGER = logging.getLogger(__name__)


def devices_from_config(hass, discovery_info):
    """Parse configuration and add WiLights switch devices."""
    device_id = discovery_info[0]
    model = discovery_info[1]
    indexes = discovery_info[2]
    item_names = discovery_info[3]
    item_types = discovery_info[4]
    item_sub_types = discovery_info[5]
    device_client = hass.data[DATA_DEVICE_REGISTER][device_id]
    devices = []
    for i in range(0, len(indexes)):
        if item_types[i] != ITEM_LIGHT:
            continue
        if item_sub_types[i] == LIGHT_NONE:
            continue
        index = indexes[i]
        item_name = item_names[i]
        item_type = f"{item_types[i]}.{item_sub_types[i]}"
        if item_sub_types[i] == LIGHT_ON_OFF:
            device = WiLightLightOnOff(
                item_name, index, device_id, model, item_type, device_client
            )
        elif item_sub_types[i] == LIGHT_DIMMER:
            device = WiLightLightDimmer(
                item_name, index, device_id, model, item_type, device_client
            )
        elif item_sub_types[i] == LIGHT_COLOR:
            device = WiLightLightColor(
                item_name, index, device_id, model, item_type, device_client
            )
        else:
            continue
        devices.append(device)
    return devices


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the WiLights platform."""
    async_add_entities(devices_from_config(hass, discovery_info))


class WiLightLightOnOff(WiLightDevice, LightEntity):
    """Representation of a WiLights light on-off."""

    @callback
    def handle_event_callback(self, event):
        """Propagate changes through ha."""
        self._status = event
        self.async_write_ha_state()

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_NONE

    @property
    def is_on(self):
        """Return true if device is on."""
        self._on = self._status["on"]
        return self._on

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        await self._client.turn_on(self._index)

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        await self._client.turn_off(self._index)

    @callback
    def _availability_callback(self, availability):
        """Update availability state."""
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Register update callback."""
        self._client.register_status_callback(self.handle_event_callback, self._index)
        self._status = await self._client.status(self._index)
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"wilight_device_available_{self._device_id}",
                self._availability_callback,
            )
        )


class WiLightLightDimmer(WiLightDevice, LightEntity):
    """Representation of a WiLights light dimmer."""

    @callback
    def handle_event_callback(self, event):
        """Propagate changes through ha."""
        self._status = event
        self.async_write_ha_state()

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return int(self._status["brightness"])

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._status["on"]

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

    @callback
    def _availability_callback(self, availability):
        """Update availability state."""
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Register update callback."""
        self._client.register_status_callback(self.handle_event_callback, self._index)
        self._status = await self._client.status(self._index)
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"wilight_device_available_{self._device_id}",
                self._availability_callback,
            )
        )


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

    @callback
    def handle_event_callback(self, event):
        """Propagate changes through ha."""
        self._status = event
        self.async_write_ha_state()

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS + SUPPORT_COLOR

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return int(self._status["brightness"])

    @property
    def hs_color(self):
        """Return the hue and saturation color value [float, float]."""
        hue = wilight_to_hass_hue(int(self._status["hue"]))
        saturation = wilight_to_hass_saturation(int(self._status["saturation"]))
        return [hue, saturation]

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._status["on"]

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

    @callback
    def _availability_callback(self, availability):
        """Update availability state."""
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Register update callback."""
        self._client.register_status_callback(self.handle_event_callback, self._index)
        self._status = await self._client.status(self._index)
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"wilight_device_available_{self._device_id}",
                self._availability_callback,
            )
        )
