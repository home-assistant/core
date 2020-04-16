"""Support for the Philips Hue lights."""
from datetime import timedelta
from functools import partial
import logging
import random

import aiohue
import async_timeout

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_EFFECT,
    ATTR_FLASH,
    ATTR_HS_COLOR,
    ATTR_TRANSITION,
    EFFECT_COLORLOOP,
    EFFECT_RANDOM,
    FLASH_LONG,
    FLASH_SHORT,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_COLOR_TEMP,
    SUPPORT_EFFECT,
    SUPPORT_FLASH,
    SUPPORT_TRANSITION,
    Light,
)
from homeassistant.core import callback
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import color

from .const import DOMAIN as HUE_DOMAIN, REQUEST_REFRESH_DELAY
from .helpers import remove_devices

SCAN_INTERVAL = timedelta(seconds=5)

_LOGGER = logging.getLogger(__name__)

SUPPORT_HUE_ON_OFF = SUPPORT_FLASH | SUPPORT_TRANSITION
SUPPORT_HUE_DIMMABLE = SUPPORT_HUE_ON_OFF | SUPPORT_BRIGHTNESS
SUPPORT_HUE_COLOR_TEMP = SUPPORT_HUE_DIMMABLE | SUPPORT_COLOR_TEMP
SUPPORT_HUE_COLOR = SUPPORT_HUE_DIMMABLE | SUPPORT_EFFECT | SUPPORT_COLOR
SUPPORT_HUE_EXTENDED = SUPPORT_HUE_COLOR_TEMP | SUPPORT_HUE_COLOR

SUPPORT_HUE = {
    "Extended color light": SUPPORT_HUE_EXTENDED,
    "Color light": SUPPORT_HUE_COLOR,
    "Dimmable light": SUPPORT_HUE_DIMMABLE,
    "On/Off plug-in unit": SUPPORT_HUE_ON_OFF,
    "Color temperature light": SUPPORT_HUE_COLOR_TEMP,
}

ATTR_IS_HUE_GROUP = "is_hue_group"
GAMUT_TYPE_UNAVAILABLE = "None"
# Minimum Hue Bridge API version to support groups
# 1.4.0 introduced extended group info
# 1.12 introduced the state object for groups
# 1.13 introduced "any_on" to group state objects
GROUP_MIN_API_VERSION = (1, 13, 0)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Old way of setting up Hue lights.

    Can only be called when a user accidentally mentions hue platform in their
    config. But even in that case it would have been ignored.
    """


def create_light(item_class, coordinator, bridge, is_group, api, item_id):
    """Create the light."""
    if is_group:
        supported_features = 0
        for light_id in api[item_id].lights:
            if light_id not in bridge.api.lights:
                continue
            light = bridge.api.lights[light_id]
            supported_features |= SUPPORT_HUE.get(light.type, SUPPORT_HUE_EXTENDED)
        supported_features = supported_features or SUPPORT_HUE_EXTENDED
    else:
        supported_features = SUPPORT_HUE.get(api[item_id].type, SUPPORT_HUE_EXTENDED)
    return item_class(coordinator, bridge, is_group, api[item_id], supported_features)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Hue lights from a config entry."""
    bridge = hass.data[HUE_DOMAIN][config_entry.entry_id]

    light_coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="light",
        update_method=partial(async_safe_fetch, bridge, bridge.api.lights.update),
        update_interval=SCAN_INTERVAL,
        request_refresh_debouncer=Debouncer(
            bridge.hass, _LOGGER, cooldown=REQUEST_REFRESH_DELAY, immediate=True
        ),
    )

    # First do a refresh to see if we can reach the hub.
    # Otherwise we will declare not ready.
    await light_coordinator.async_refresh()

    if not light_coordinator.last_update_success:
        raise PlatformNotReady

    update_lights = partial(
        async_update_items,
        bridge,
        bridge.api.lights,
        {},
        async_add_entities,
        partial(create_light, HueLight, light_coordinator, bridge, False),
    )

    # We add a listener after fetching the data, so manually trigger listener
    bridge.reset_jobs.append(light_coordinator.async_add_listener(update_lights))
    update_lights()

    api_version = tuple(int(v) for v in bridge.api.config.apiversion.split("."))

    allow_groups = bridge.allow_groups
    if allow_groups and api_version < GROUP_MIN_API_VERSION:
        _LOGGER.warning("Please update your Hue bridge to support groups")
        allow_groups = False

    if not allow_groups:
        return

    group_coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="group",
        update_method=partial(async_safe_fetch, bridge, bridge.api.groups.update),
        update_interval=SCAN_INTERVAL,
        request_refresh_debouncer=Debouncer(
            bridge.hass, _LOGGER, cooldown=REQUEST_REFRESH_DELAY, immediate=True
        ),
    )

    update_groups = partial(
        async_update_items,
        bridge,
        bridge.api.groups,
        {},
        async_add_entities,
        partial(create_light, HueLight, group_coordinator, bridge, True),
    )

    bridge.reset_jobs.append(group_coordinator.async_add_listener(update_groups))
    await group_coordinator.async_refresh()


async def async_safe_fetch(bridge, fetch_method):
    """Safely fetch data."""
    try:
        with async_timeout.timeout(4):
            return await bridge.async_request_call(fetch_method)
    except aiohue.Unauthorized:
        await bridge.handle_unauthorized_error()
        raise UpdateFailed("Unauthorized")
    except (aiohue.AiohueException,) as err:
        raise UpdateFailed(f"Hue error: {err}")


@callback
def async_update_items(bridge, api, current, async_add_entities, create_item):
    """Update items."""
    new_items = []

    for item_id in api:
        if item_id in current:
            continue

        current[item_id] = create_item(api, item_id)
        new_items.append(current[item_id])

    bridge.hass.async_create_task(remove_devices(bridge, api, current))

    if new_items:
        async_add_entities(new_items)


def hue_brightness_to_hass(value):
    """Convert hue brightness 1..254 to hass format 0..255."""
    return min(255, round((value / 254) * 255))


def hass_to_hue_brightness(value):
    """Convert hass brightness 0..255 to hue 1..254 scale."""
    return max(1, round((value / 255) * 254))


class HueLight(Light):
    """Representation of a Hue light."""

    def __init__(self, coordinator, bridge, is_group, light, supported_features):
        """Initialize the light."""
        self.light = light
        self.coordinator = coordinator
        self.bridge = bridge
        self.is_group = is_group
        self._supported_features = supported_features

        if is_group:
            self.is_osram = False
            self.is_philips = False
            self.is_innr = False
            self.gamut_typ = GAMUT_TYPE_UNAVAILABLE
            self.gamut = None
        else:
            self.is_osram = light.manufacturername == "OSRAM"
            self.is_philips = light.manufacturername == "Philips"
            self.is_innr = light.manufacturername == "innr"
            self.gamut_typ = self.light.colorgamuttype
            self.gamut = self.light.colorgamut
            _LOGGER.debug("Color gamut of %s: %s", self.name, str(self.gamut))
            if self.light.swupdatestate == "readytoinstall":
                err = (
                    "Please check for software updates of the %s "
                    "bulb in the Philips Hue App."
                )
                _LOGGER.warning(err, self.name)
            if self.gamut:
                if not color.check_valid_gamut(self.gamut):
                    err = "Color gamut of %s: %s, not valid, setting gamut to None."
                    _LOGGER.warning(err, self.name, str(self.gamut))
                    self.gamut_typ = GAMUT_TYPE_UNAVAILABLE
                    self.gamut = None

    @property
    def unique_id(self):
        """Return the unique ID of this Hue light."""
        return self.light.uniqueid

    @property
    def should_poll(self):
        """No polling required."""
        return False

    @property
    def device_id(self):
        """Return the ID of this Hue light."""
        return self.unique_id

    @property
    def name(self):
        """Return the name of the Hue light."""
        return self.light.name

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        if self.is_group:
            bri = self.light.action.get("bri")
        else:
            bri = self.light.state.get("bri")

        return hue_brightness_to_hass(bri)

    @property
    def _color_mode(self):
        """Return the hue color mode."""
        if self.is_group:
            return self.light.action.get("colormode")
        return self.light.state.get("colormode")

    @property
    def hs_color(self):
        """Return the hs color value."""
        mode = self._color_mode
        source = self.light.action if self.is_group else self.light.state

        if mode in ("xy", "hs") and "xy" in source:
            return color.color_xy_to_hs(*source["xy"], self.gamut)

        return None

    @property
    def color_temp(self):
        """Return the CT color value."""
        # Don't return color temperature unless in color temperature mode
        if self._color_mode != "ct":
            return None

        if self.is_group:
            return self.light.action.get("ct")
        return self.light.state.get("ct")

    @property
    def min_mireds(self):
        """Return the coldest color_temp that this light supports."""
        if self.is_group or "ct" not in self.light.controlcapabilities:
            return super().min_mireds

        return self.light.controlcapabilities["ct"]["min"]

    @property
    def max_mireds(self):
        """Return the warmest color_temp that this light supports."""
        if self.is_group or "ct" not in self.light.controlcapabilities:
            return super().max_mireds

        return self.light.controlcapabilities["ct"]["max"]

    @property
    def is_on(self):
        """Return true if device is on."""
        if self.is_group:
            return self.light.state["any_on"]
        return self.light.state["on"]

    @property
    def available(self):
        """Return if light is available."""
        return self.coordinator.last_update_success and (
            self.is_group
            or self.bridge.allow_unreachable
            or self.light.state["reachable"]
        )

    @property
    def supported_features(self):
        """Flag supported features."""
        return self._supported_features

    @property
    def effect(self):
        """Return the current effect."""
        return self.light.state.get("effect", None)

    @property
    def effect_list(self):
        """Return the list of supported effects."""
        if self.is_osram:
            return [EFFECT_RANDOM]
        return [EFFECT_COLORLOOP, EFFECT_RANDOM]

    @property
    def device_info(self):
        """Return the device info."""
        if self.light.type in ("LightGroup", "Room", "Luminaire", "LightSource"):
            return None

        return {
            "identifiers": {(HUE_DOMAIN, self.device_id)},
            "name": self.name,
            "manufacturer": self.light.manufacturername,
            # productname added in Hue Bridge API 1.24
            # (published 03/05/2018)
            "model": self.light.productname or self.light.modelid,
            # Not yet exposed as properties in aiohue
            "sw_version": self.light.raw["swversion"],
            "via_device": (HUE_DOMAIN, self.bridge.api.config.bridgeid),
        }

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_turn_on(self, **kwargs):
        """Turn the specified or all lights on."""
        command = {"on": True}

        if ATTR_TRANSITION in kwargs:
            command["transitiontime"] = int(kwargs[ATTR_TRANSITION] * 10)

        if ATTR_HS_COLOR in kwargs:
            if self.is_osram:
                command["hue"] = int(kwargs[ATTR_HS_COLOR][0] / 360 * 65535)
                command["sat"] = int(kwargs[ATTR_HS_COLOR][1] / 100 * 255)
            else:
                # Philips hue bulb models respond differently to hue/sat
                # requests, so we convert to XY first to ensure a consistent
                # color.
                xy_color = color.color_hs_to_xy(*kwargs[ATTR_HS_COLOR], self.gamut)
                command["xy"] = xy_color
        elif ATTR_COLOR_TEMP in kwargs:
            temp = kwargs[ATTR_COLOR_TEMP]
            command["ct"] = max(self.min_mireds, min(temp, self.max_mireds))

        if ATTR_BRIGHTNESS in kwargs:
            command["bri"] = hass_to_hue_brightness(kwargs[ATTR_BRIGHTNESS])

        flash = kwargs.get(ATTR_FLASH)

        if flash == FLASH_LONG:
            command["alert"] = "lselect"
            del command["on"]
        elif flash == FLASH_SHORT:
            command["alert"] = "select"
            del command["on"]
        elif not self.is_innr:
            command["alert"] = "none"

        if ATTR_EFFECT in kwargs:
            effect = kwargs[ATTR_EFFECT]
            if effect == EFFECT_COLORLOOP:
                command["effect"] = "colorloop"
            elif effect == EFFECT_RANDOM:
                command["hue"] = random.randrange(0, 65535)
                command["sat"] = random.randrange(150, 254)
            else:
                command["effect"] = "none"

        if self.is_group:
            await self.bridge.async_request_call(
                partial(self.light.set_action, **command)
            )
        else:
            await self.bridge.async_request_call(
                partial(self.light.set_state, **command)
            )

        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        """Turn the specified or all lights off."""
        command = {"on": False}

        if ATTR_TRANSITION in kwargs:
            command["transitiontime"] = int(kwargs[ATTR_TRANSITION] * 10)

        flash = kwargs.get(ATTR_FLASH)

        if flash == FLASH_LONG:
            command["alert"] = "lselect"
            del command["on"]
        elif flash == FLASH_SHORT:
            command["alert"] = "select"
            del command["on"]
        elif not self.is_innr:
            command["alert"] = "none"

        if self.is_group:
            await self.bridge.async_request_call(
                partial(self.light.set_action, **command)
            )
        else:
            await self.bridge.async_request_call(
                partial(self.light.set_state, **command)
            )

        await self.coordinator.async_request_refresh()

    async def async_update(self):
        """Update the entity.

        Only used by the generic entity update service.
        """
        await self.coordinator.async_request_refresh()

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        attributes = {}
        if self.is_group:
            attributes[ATTR_IS_HUE_GROUP] = self.is_group
        return attributes
