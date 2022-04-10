"""Support for the Philips Hue lights."""
from __future__ import annotations

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
    LightEntity,
)
from homeassistant.core import callback
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import color

from ..bridge import HueBridge
from ..const import (
    CONF_ALLOW_HUE_GROUPS,
    CONF_ALLOW_UNREACHABLE,
    DEFAULT_ALLOW_HUE_GROUPS,
    DEFAULT_ALLOW_UNREACHABLE,
    DOMAIN as HUE_DOMAIN,
    GROUP_TYPE_ENTERTAINMENT,
    GROUP_TYPE_LIGHT_GROUP,
    GROUP_TYPE_LIGHT_SOURCE,
    GROUP_TYPE_LUMINAIRE,
    GROUP_TYPE_ROOM,
    GROUP_TYPE_ZONE,
    REQUEST_REFRESH_DELAY,
)
from .helpers import remove_devices

SCAN_INTERVAL = timedelta(seconds=5)

LOGGER = logging.getLogger(__name__)

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


def create_light(item_class, coordinator, bridge, is_group, rooms, api, item_id):
    """Create the light."""
    api_item = api[item_id]

    if is_group:
        supported_features = 0
        for light_id in api_item.lights:
            if light_id not in bridge.api.lights:
                continue
            light = bridge.api.lights[light_id]
            supported_features |= SUPPORT_HUE.get(light.type, SUPPORT_HUE_EXTENDED)
        supported_features = supported_features or SUPPORT_HUE_EXTENDED
    else:
        supported_features = SUPPORT_HUE.get(api_item.type, SUPPORT_HUE_EXTENDED)
    return item_class(
        coordinator, bridge, is_group, api_item, supported_features, rooms
    )


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Hue lights from a config entry."""
    bridge: HueBridge = hass.data[HUE_DOMAIN][config_entry.entry_id]
    api_version = tuple(int(v) for v in bridge.api.config.apiversion.split("."))
    rooms = {}

    allow_groups = config_entry.options.get(
        CONF_ALLOW_HUE_GROUPS, DEFAULT_ALLOW_HUE_GROUPS
    )
    supports_groups = api_version >= GROUP_MIN_API_VERSION
    if allow_groups and not supports_groups:
        LOGGER.warning("Please update your Hue bridge to support groups")

    light_coordinator = DataUpdateCoordinator(
        hass,
        LOGGER,
        name="light",
        update_method=partial(async_safe_fetch, bridge, bridge.api.lights.update),
        update_interval=SCAN_INTERVAL,
        request_refresh_debouncer=Debouncer(
            bridge.hass, LOGGER, cooldown=REQUEST_REFRESH_DELAY, immediate=True
        ),
    )

    # First do a refresh to see if we can reach the hub.
    # Otherwise we will declare not ready.
    await light_coordinator.async_refresh()

    if not light_coordinator.last_update_success:
        raise PlatformNotReady

    if not supports_groups:
        update_lights_without_group_support = partial(
            async_update_items,
            bridge,
            bridge.api.lights,
            {},
            async_add_entities,
            partial(create_light, HueLight, light_coordinator, bridge, False, rooms),
            None,
        )
        # We add a listener after fetching the data, so manually trigger listener
        bridge.reset_jobs.append(
            light_coordinator.async_add_listener(update_lights_without_group_support)
        )
        return

    group_coordinator = DataUpdateCoordinator(
        hass,
        LOGGER,
        name="group",
        update_method=partial(async_safe_fetch, bridge, bridge.api.groups.update),
        update_interval=SCAN_INTERVAL,
        request_refresh_debouncer=Debouncer(
            bridge.hass, LOGGER, cooldown=REQUEST_REFRESH_DELAY, immediate=True
        ),
    )

    if allow_groups:
        update_groups = partial(
            async_update_items,
            bridge,
            bridge.api.groups,
            {},
            async_add_entities,
            partial(create_light, HueLight, group_coordinator, bridge, True, None),
            None,
        )

        bridge.reset_jobs.append(group_coordinator.async_add_listener(update_groups))

    cancel_update_rooms_listener = None

    @callback
    def _async_update_rooms():
        """Update rooms."""
        nonlocal cancel_update_rooms_listener
        rooms.clear()
        for item_id in bridge.api.groups:
            group = bridge.api.groups[item_id]
            if group.type not in [GROUP_TYPE_ROOM, GROUP_TYPE_ZONE]:
                continue
            for light_id in group.lights:
                rooms[light_id] = group.name

        # Once we do a rooms update, we cancel the listener
        # until the next time lights are added
        bridge.reset_jobs.remove(cancel_update_rooms_listener)
        cancel_update_rooms_listener()  # pylint: disable=not-callable
        cancel_update_rooms_listener = None

    @callback
    def _setup_rooms_listener():
        nonlocal cancel_update_rooms_listener
        if cancel_update_rooms_listener is not None:
            # If there are new lights added before _async_update_rooms
            # is called we should not add another listener
            return

        cancel_update_rooms_listener = group_coordinator.async_add_listener(
            _async_update_rooms
        )
        bridge.reset_jobs.append(cancel_update_rooms_listener)

    _setup_rooms_listener()
    await group_coordinator.async_refresh()

    update_lights_with_group_support = partial(
        async_update_items,
        bridge,
        bridge.api.lights,
        {},
        async_add_entities,
        partial(create_light, HueLight, light_coordinator, bridge, False, rooms),
        _setup_rooms_listener,
    )
    # We add a listener after fetching the data, so manually trigger listener
    bridge.reset_jobs.append(
        light_coordinator.async_add_listener(update_lights_with_group_support)
    )
    update_lights_with_group_support()


async def async_safe_fetch(bridge, fetch_method):
    """Safely fetch data."""
    try:
        with async_timeout.timeout(4):
            return await bridge.async_request_call(fetch_method)
    except aiohue.Unauthorized as err:
        await bridge.handle_unauthorized_error()
        raise UpdateFailed("Unauthorized") from err
    except aiohue.AiohueException as err:
        raise UpdateFailed(f"Hue error: {err}") from err


@callback
def async_update_items(
    bridge, api, current, async_add_entities, create_item, new_items_callback
):
    """Update items."""
    new_items = []

    for item_id in api:
        if item_id in current:
            continue

        current[item_id] = create_item(api, item_id)
        new_items.append(current[item_id])

    bridge.hass.async_create_task(remove_devices(bridge, api, current))

    if new_items:
        # This is currently used to setup the listener to update rooms
        if new_items_callback:
            new_items_callback()
        async_add_entities(new_items)


def hue_brightness_to_hass(value):
    """Convert hue brightness 1..254 to hass format 0..255."""
    return min(255, round((value / 254) * 255))


def hass_to_hue_brightness(value):
    """Convert hass brightness 0..255 to hue 1..254 scale."""
    return max(1, round((value / 255) * 254))


class HueLight(CoordinatorEntity, LightEntity):
    """Representation of a Hue light."""

    def __init__(self, coordinator, bridge, is_group, light, supported_features, rooms):
        """Initialize the light."""
        super().__init__(coordinator)
        self.light = light
        self.bridge = bridge
        self.is_group = is_group
        self._supported_features = supported_features
        self._rooms = rooms
        self.allow_unreachable = self.bridge.config_entry.options.get(
            CONF_ALLOW_UNREACHABLE, DEFAULT_ALLOW_UNREACHABLE
        )

        if is_group:
            self.is_osram = False
            self.is_philips = False
            self.is_innr = False
            self.is_ewelink = False
            self.is_livarno = False
            self.gamut_typ = GAMUT_TYPE_UNAVAILABLE
            self.gamut = None
        else:
            self.is_osram = light.manufacturername == "OSRAM"
            self.is_philips = light.manufacturername == "Philips"
            self.is_innr = light.manufacturername == "innr"
            self.is_ewelink = light.manufacturername == "eWeLink"
            self.is_livarno = light.manufacturername.startswith("_TZ3000_")
            self.gamut_typ = self.light.colorgamuttype
            self.gamut = self.light.colorgamut
            LOGGER.debug("Color gamut of %s: %s", self.name, str(self.gamut))
            if self.light.swupdatestate == "readytoinstall":
                err = (
                    "Please check for software updates of the %s "
                    "bulb in the Philips Hue App."
                )
                LOGGER.warning(err, self.name)
            if self.gamut and not color.check_valid_gamut(self.gamut):
                err = "Color gamut of %s: %s, not valid, setting gamut to None."
                LOGGER.debug(err, self.name, str(self.gamut))
                self.gamut_typ = GAMUT_TYPE_UNAVAILABLE
                self.gamut = None

    @property
    def unique_id(self):
        """Return the unique ID of this Hue light."""
        unique_id = self.light.uniqueid
        if not unique_id and self.is_group:
            unique_id = self.light.id

        return unique_id

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

        if bri is None:
            return bri

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
        if self.is_group:
            return super().min_mireds

        min_mireds = self.light.controlcapabilities.get("ct", {}).get("min")

        # We filter out '0' too, which can be incorrectly reported by 3rd party buls
        if not min_mireds:
            return super().min_mireds

        return min_mireds

    @property
    def max_mireds(self):
        """Return the warmest color_temp that this light supports."""
        if self.is_group:
            return super().max_mireds
        if self.is_livarno:
            return 500

        max_mireds = self.light.controlcapabilities.get("ct", {}).get("max")

        if not max_mireds:
            return super().max_mireds

        return max_mireds

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
            self.is_group or self.allow_unreachable or self.light.state["reachable"]
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
    def device_info(self) -> DeviceInfo | None:
        """Return the device info."""
        if self.light.type in (
            GROUP_TYPE_ENTERTAINMENT,
            GROUP_TYPE_LIGHT_GROUP,
            GROUP_TYPE_ROOM,
            GROUP_TYPE_LUMINAIRE,
            GROUP_TYPE_LIGHT_SOURCE,
            GROUP_TYPE_ZONE,
        ):
            return None

        suggested_area = None
        if self._rooms and self.light.id in self._rooms:
            suggested_area = self._rooms[self.light.id]

        return DeviceInfo(
            identifiers={(HUE_DOMAIN, self.device_id)},
            manufacturer=self.light.manufacturername,
            # productname added in Hue Bridge API 1.24
            # (published 03/05/2018)
            model=self.light.productname or self.light.modelid,
            name=self.name,
            sw_version=self.light.swversion,
            suggested_area=suggested_area,
            via_device=(HUE_DOMAIN, self.bridge.api.config.bridgeid),
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
        elif not self.is_innr and not self.is_ewelink and not self.is_livarno:
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
            await self.bridge.async_request_call(self.light.set_action, **command)
        else:
            await self.bridge.async_request_call(self.light.set_state, **command)

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
        elif not self.is_innr and not self.is_livarno:
            command["alert"] = "none"

        if self.is_group:
            await self.bridge.async_request_call(self.light.set_action, **command)
        else:
            await self.bridge.async_request_call(self.light.set_state, **command)

        await self.coordinator.async_request_refresh()

    @property
    def extra_state_attributes(self):
        """Return the device state attributes."""
        if not self.is_group:
            return {}
        return {ATTR_IS_HUE_GROUP: self.is_group}
