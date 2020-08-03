"""
Support for real Exta Life light controllers (RDP, RDM, SLR) + fake lights (on/off switches: ROP,ROM devices) mapped as light in HA
"""
import logging
from pprint import pformat

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ATTR_WHITE_VALUE,
    DOMAIN as DOMAIN_LIGHT,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_EFFECT,
    SUPPORT_WHITE_VALUE,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType
import homeassistant.util.color as color_util

from . import ExtaLifeChannel
from .helpers.const import DOMAIN
from .helpers.core import Core
from .pyextalife import (
    DEVICE_ARR_ALL_LIGHT,
    DEVICE_ARR_EXTA_FREE_RGB,
    DEVICE_ARR_LIGHT_EFFECT,
    DEVICE_ARR_LIGHT_RGB,
    DEVICE_ARR_LIGHT_RGBW,
    ExtaLifeAPI,
)

_LOGGER = logging.getLogger(__name__)

EFFECT_1 = "Program 1"
EFFECT_2 = "Program 2"
EFFECT_3 = "Program 3"
EFFECT_4 = "Program 4"
EFFECT_5 = "Program 5"
EFFECT_6 = "Program 6"
EFFECT_7 = "Program 7"
EFFECT_8 = "Program 8"
EFFECT_9 = "Program 9"
EFFECT_10 = "Program 10"
EFFECT_FLOAT = "Floating"
EFFECT_LIST = [
    EFFECT_1,
    EFFECT_2,
    EFFECT_3,
    EFFECT_4,
    EFFECT_5,
    EFFECT_6,
    EFFECT_7,
    EFFECT_8,
    EFFECT_9,
    EFFECT_10,
    EFFECT_FLOAT,
]
EFFECT_LIST_SLR = EFFECT_LIST

MAP_MODE_VAL_EFFECT = {
    0: EFFECT_FLOAT,
    1: EFFECT_1,
    2: EFFECT_2,
    3: EFFECT_3,
    4: EFFECT_4,
    5: EFFECT_5,
    6: EFFECT_6,
    7: EFFECT_7,
    8: EFFECT_8,
    9: EFFECT_9,
    10: EFFECT_10,
}
MAP_EFFECT_MODE_VAL = {
    EFFECT_FLOAT: 0,
    EFFECT_1: 1,
    EFFECT_2: 2,
    EFFECT_3: 3,
    EFFECT_4: 4,
    EFFECT_5: 5,
    EFFECT_6: 6,
    EFFECT_7: 7,
    EFFECT_8: 8,
    EFFECT_9: 9,
    EFFECT_10: 10,
}


def scaleto255(value):
    """Scale the input value from 0-100 to 0-255."""
    return max(0, min(255, ((value * 255.0) / 100.0)))


def scaleto100(value):
    """Scale the input value from 0-255 to 0-100."""
    # Make sure a low but non-zero value is not rounded down to zero
    if 0 < value < 3:
        return 1
    return int(max(0, min(100, ((value * 100.0) / 255.0))))


def modevaltohex(mode_val):
    """ convert mode_val value that can be either xeh string or int to a hex string """
    if isinstance(mode_val, int):
        return (hex(mode_val)[2:]).upper()
    if isinstance(mode_val, str):
        return mode_val
    return None


def modevaltoint(mode_val):
    """ convert mode_val value that can be either xeh string or int to int """
    if isinstance(mode_val, str):
        return int(mode_val, 16)
    if isinstance(mode_val, int):
        return mode_val
    return None


def modeval_upd(old, new):
    """ Update mode_val contextually. Convert to type of the old value and update"""
    if isinstance(old, int):
        if isinstance(new, int):
            return new
        return modevaltoint(new)

    if isinstance(old, str):
        if isinstance(new, str):
            return new
        return modevaltohex(new)

    return None


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """setup via configuration.yaml not supported anymore"""
    pass


async def async_setup_entry(
    hass: HomeAssistantType, config_entry: ConfigEntry, async_add_entities
):
    """Set up an Exta Life light based on existing config."""

    core = Core.get(config_entry.entry_id)
    channels = core.get_channels(DOMAIN_LIGHT)

    _LOGGER.debug("Discovery: %s", pformat(channels))
    async_add_entities([ExtaLifeLight(device, config_entry) for device in channels])

    core.pop_channels(DOMAIN_LIGHT)


class ExtaLifeLight(ExtaLifeChannel, LightEntity):
    """Representation of an ExtaLife light-contorlling device."""

    def __init__(self, channel_data, config_entry):
        super().__init__(channel_data, config_entry)

        self._supported_flags = 0
        self._effect_list = None
        self.channel_data = channel_data.get("data")
        self._assumed_on = False

        dev_type = self.channel_data.get("type")
        _LOGGER.debug("Light type: %s", dev_type)
        if dev_type in DEVICE_ARR_ALL_LIGHT:
            if not self.is_exta_free:
                self._supported_flags |= SUPPORT_BRIGHTNESS
            # elif
            # self.is_exta_free and DEVICE_ARR_EXTA_FREE_RGB:    # for Exta Free only RGB controller supports brightness level adjustment
            #     self._supported_flags |= SUPPORT_BRIGHTNESS

        if dev_type in DEVICE_ARR_LIGHT_RGBW:
            self._supported_flags |= SUPPORT_COLOR | SUPPORT_WHITE_VALUE
        elif (
            dev_type in DEVICE_ARR_LIGHT_RGB
        ):  # do not add Exta Free as RDP-11 support in controller is limited to on/off only
            self._supported_flags |= SUPPORT_COLOR

        if dev_type in DEVICE_ARR_LIGHT_EFFECT:
            self._supported_flags |= SUPPORT_EFFECT
            if dev_type in [27, 38]:
                self._effect_list = EFFECT_LIST_SLR

    async def async_turn_on(self, **kwargs):
        """Turn on the switch."""
        data = self.channel_data
        params = dict()
        rgb = w = None
        if self._supported_flags & SUPPORT_BRIGHTNESS:
            target_brightness = kwargs.get(ATTR_BRIGHTNESS)

            if target_brightness is not None:
                # We set it to the target brightness and turn it on
                if data is not None:
                    params.update({"value": scaleto100(target_brightness)})
            else:
                params.update({"value": data.get("value")})

        mode_val = self.channel_data.get("mode_val")
        mode_val_int = modevaltoint(mode_val)
        effect = kwargs.get(ATTR_EFFECT)
        _LOGGER.debug("kwargs: %s", kwargs)
        _LOGGER.debug("'mode_val' value: %s", mode_val)
        _LOGGER.debug(
            "turn_on for entity: %s(%s). mode_val_int: %s",
            self.entity_id,
            self.channel_id,
            mode_val_int,
        )

        # WARNING: Exta LIfe 'mode_val' from command 37 is a HEX STRING, but command 20 requires INT!!! 🤦‍♂️
        if self._supported_flags & SUPPORT_WHITE_VALUE and effect is None:
            if kwargs.get(ATTR_WHITE_VALUE) is None:
                w = mode_val_int & 255  # default
            else:
                w = int(kwargs.get(ATTR_WHITE_VALUE)) & 255

        if self._supported_flags & SUPPORT_COLOR and effect is None:
            if not kwargs.get(ATTR_HS_COLOR):
                rgb = mode_val_int >> 8  # default
            else:
                hs = kwargs.get(ATTR_HS_COLOR)  # should return a tuple (h, s)
                rgb = color_util.color_hs_to_RGB(*hs)  # returns a tuple (R, G, B)
                rgb = (int(rgb[0]) << 16) | (int(rgb[1]) << 8) | (int(rgb[2]))

        if (
            self._supported_flags & SUPPORT_WHITE_VALUE
            and self._supported_flags & SUPPORT_COLOR
            and effect is None
        ):
            # Exta Life colors in SLR22 are 4 bytes: RGBW
            _LOGGER.debug("RGB value: %s. W value: %s", rgb, w)
            rgbw = (rgb << 8) | w  # merge RGB & W
            params.update({"mode_val": rgbw})
            params.update(
                {"mode": 1}
            )  # mode - still light or predefined programs; set it as still light

        if effect is not None:
            params.update({"mode": 2})  # mode - turn on effect
            params.update(
                {"mode_val": MAP_EFFECT_MODE_VAL[effect]}
            )  # mode - one of effects

        if not self.is_exta_free:
            if await self.async_action(ExtaLifeAPI.ACTN_TURN_ON, **params):
                # update channel data with new values
                data["power"] = 1
                mode_val_new = params.get("mode_val")
                if mode_val_new is not None:
                    params["mode_val"] = modeval_upd(
                        mode_val, mode_val_new
                    )  # convert new value to the format of the old value from channel_data
                data.update(params)
                self.async_schedule_update_ha_state()
        else:
            if await self.async_action(
                ExtaLifeAPI.ACTN_EXFREE_TURN_ON_PRESS, **params
            ) and await self.async_action(
                ExtaLifeAPI.ACTN_EXFREE_TURN_ON_RELEASE, **params
            ):
                self._assumed_on = True
                self.schedule_update_ha_state()

    async def async_turn_off(self, **kwargs):
        """Turn off the switch."""
        data = self.channel_data
        params = dict()
        mode = data.get("mode")
        if mode is not None:
            params.update({"mode": mode})
        mode_val = data.get("mode_val")
        if mode_val is not None:
            params.update({"mode_val": modevaltoint(mode_val)})
        value = data.get("value")
        if value is not None:
            params.update({"value": value})

        if not self.is_exta_free:
            if await self.async_action(ExtaLifeAPI.ACTN_TURN_OFF, **params):
                data["power"] = 0
                data["mode"] = mode
                self.async_schedule_update_ha_state()
        else:
            if await self.async_action(
                ExtaLifeAPI.ACTN_EXFREE_TURN_OFF_PRESS, **params
            ) and await self.async_action(
                ExtaLifeAPI.ACTN_EXFREE_TURN_OFF_RELEASE, **params
            ):
                self._assumed_on = False
                self.schedule_update_ha_state()

    @property
    def effect(self):
        mode = self.channel_data.get("mode")
        if mode is None or mode != 2:
            return None
        mode_val = self.channel_data.get("mode_val")
        if mode_val is None:
            return None
        return MAP_MODE_VAL_EFFECT[modevaltoint(mode_val)]

    @property
    def effect_list(self):
        return self._effect_list

    @property
    def brightness(self):
        """ Device brightness """
        data = self.channel_data
        # brightness is only supported for native Exta Life light-controlling devices
        if data.get("type") in DEVICE_ARR_ALL_LIGHT:
            return scaleto255(data.get("value"))

    @property
    def supported_features(self):
        _LOGGER.debug("Supported flags: %s", self._supported_flags)
        return self._supported_flags

    @property
    def hs_color(self):
        """ Device colour setting """
        rgbw = modevaltoint(self.channel_data.get("mode_val"))
        rgb = rgbw >> 8
        r = rgb >> 16
        g = (rgb >> 8) & 255
        b = rgb & 255

        hs = color_util.color_RGB_to_hs(float(r), float(g), float(b))
        return hs

    @property
    def white_value(self):
        rgbw = modevaltoint(self.channel_data.get("mode_val"))
        return rgbw & 255

    @property
    def is_on(self):
        """Return true if switch is on."""
        if self.is_exta_free:
            return self._assumed_on

        state = self.channel_data.get("power")

        _LOGGER.debug("is_on for entity: %s, state: %s", self.entity_id, state)

        if state == 1:
            return True
        return False

    def on_state_notification(self, data):
        """ React on state notification from controller """
        state = data.get("state")
        ch_data = self.channel_data.copy()

        ch_data["power"] = 1 if state else 0
        if self._supported_flags & SUPPORT_BRIGHTNESS:
            ch_data["value"] = data.get("value")

        if self._supported_flags & SUPPORT_COLOR:
            mode_val = ch_data.get("mode_val")
            ch_data["mode_val"] = modeval_upd(mode_val, data.get("mode_val"))

        # update only if notification data contains new status; prevent HS event bus overloading
        if ch_data != self.channel_data:
            self.channel_data.update(ch_data)

            # synchronize DataManager data with processed update & entity data
            self.sync_data_update_ha()
