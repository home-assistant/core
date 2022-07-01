"""Support for LIFX lights."""
from __future__ import annotations

from datetime import timedelta
from functools import partial
import math
from typing import Any

import aiolifx_effects as aiolifx_effects_module
import voluptuous as vol

from homeassistant import util
from homeassistant.components.light import (
    ATTR_EFFECT,
    ATTR_TRANSITION,
    LIGHT_TURN_ON_SCHEMA,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, ATTR_MODEL, ATTR_SW_VERSION
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
import homeassistant.helpers.config_validation as cv
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import homeassistant.util.color as color_util

from . import DATA_LIFX_MANAGER
from .const import DOMAIN
from .coordinator import LIFXUpdateCoordinator
from .manager import (
    SERVICE_EFFECT_COLORLOOP,
    SERVICE_EFFECT_PULSE,
    SERVICE_EFFECT_STOP,
    LIFXManager,
)
from .util import (
    AwaitAioLIFX,
    aiolifx,
    convert_8_to_16,
    convert_16_to_8,
    find_hsbk,
    get_real_mac_addr,
    lifx_features,
    merge_hsbk,
)

SERVICE_LIFX_SET_STATE = "set_state"

ATTR_INFRARED = "infrared"
ATTR_ZONES = "zones"
ATTR_POWER = "power"

SERVICE_LIFX_SET_STATE = "set_state"

LIFX_SET_STATE_SCHEMA = cv.make_entity_service_schema(
    {
        **LIGHT_TURN_ON_SCHEMA,
        ATTR_INFRARED: vol.All(vol.Coerce(int), vol.Clamp(min=0, max=255)),
        ATTR_ZONES: vol.All(cv.ensure_list, [cv.positive_int]),
        ATTR_POWER: cv.boolean,
    }
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up LIFX from a config entry."""
    coordinator: LIFXUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    manager: LIFXManager = hass.data[DATA_LIFX_MANAGER]
    device = coordinator.device
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_LIFX_SET_STATE,
        LIFX_SET_STATE_SCHEMA,
        "set_state",
    )
    if lifx_features(device)["multizone"]:
        entity: LIFXLight = LIFXStrip(coordinator, manager, entry)
    elif lifx_features(device)["color"]:
        entity = LIFXColor(coordinator, manager, entry)
    else:
        entity = LIFXWhite(coordinator, manager, entry)
    async_add_entities([entity])


class LIFXLight(CoordinatorEntity[LIFXUpdateCoordinator], LightEntity):
    """Representation of a LIFX light."""

    _attr_supported_features = LightEntityFeature.TRANSITION | LightEntityFeature.EFFECT

    def __init__(
        self,
        coordinator: LIFXUpdateCoordinator,
        manager: LIFXManager,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the light."""
        super().__init__(coordinator)
        bulb = coordinator.device
        self.mac_addr = bulb.mac_addr
        self.bulb = bulb
        self.manager = manager
        self.effects_conductor: aiolifx_effects_module.Conductor = (
            manager.effects_conductor
        )
        self.postponed_update = None
        self.entry = entry
        mac_addr = get_real_mac_addr(self.mac_addr, self.bulb.host_firmware_version)
        info = DeviceInfo(
            identifiers={(DOMAIN, mac_addr)},
            connections={(dr.CONNECTION_NETWORK_MAC, mac_addr)},
            manufacturer="LIFX",
            name=self.name,
        )
        _map = aiolifx().products.product_map
        if (model := (_map.get(self.bulb.product) or self.bulb.product)) is not None:
            info[ATTR_MODEL] = str(model)
        if (version := self.bulb.host_firmware_version) is not None:
            info[ATTR_SW_VERSION] = version
        self._attr_device_info = info
        self._attr_unique_id = self.mac_addr
        self._attr_name = self.bulb.label
        self._attr_min_mireds = math.floor(
            color_util.color_temperature_kelvin_to_mired(
                lifx_features(bulb)["max_kelvin"]
            )
        )
        self._attr_max_mireds = math.ceil(
            color_util.color_temperature_kelvin_to_mired(
                lifx_features(bulb)["min_kelvin"]
            )
        )

    @property
    def color_mode(self) -> ColorMode:
        """Return the color mode of the light."""
        bulb_features = lifx_features(self.bulb)
        if bulb_features["min_kelvin"] != bulb_features["max_kelvin"]:
            return ColorMode.COLOR_TEMP
        return ColorMode.BRIGHTNESS

    @property
    def supported_color_modes(self) -> set[ColorMode]:
        """Flag supported color modes."""
        return {self.color_mode}

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        fade = self.bulb.power_level / 65535
        return convert_16_to_8(int(fade * self.bulb.color[2]))

    @property
    def color_temp(self):
        """Return the color temperature."""
        _, sat, _, kelvin = self.bulb.color
        if sat:
            return None
        return color_util.color_temperature_kelvin_to_mired(kelvin)

    @property
    def is_on(self):
        """Return true if light is on."""
        return self.bulb.power_level != 0

    @property
    def effect(self):
        """Return the name of the currently running effect."""
        effect = self.effects_conductor.effect(self.bulb)
        if effect:
            return f"lifx_effect_{effect.name}"
        return None

    async def update_during_transition(self, when):
        """Update state at the start and end of a transition."""
        if self.postponed_update:
            self.postponed_update()
            self.postponed_update = None

        # Transition has started
        await self.coordinator.async_request_refresh()

        # Transition has ended
        if when > 0:
            self.postponed_update = async_track_point_in_utc_time(
                self.hass,
                self.coordinator.async_request_refresh,
                util.dt.utcnow() + timedelta(milliseconds=when),
            )

    async def async_turn_on(self, **kwargs):
        """Turn the light on."""
        await self.set_state(**{**kwargs, ATTR_POWER: True})

    async def async_turn_off(self, **kwargs):
        """Turn the light off."""
        await self.set_state(**{ATTR_POWER: False})

    async def set_state(self, **kwargs: Any) -> None:
        """Set a color on the light and turn it on/off."""
        async with self.coordinator.lock:
            bulb = self.bulb

            await self.effects_conductor.stop([bulb])

            if ATTR_EFFECT in kwargs:
                await self.default_effect(**kwargs)
                return

            if ATTR_INFRARED in kwargs:
                bulb.set_infrared(convert_8_to_16(kwargs[ATTR_INFRARED]))

            if ATTR_TRANSITION in kwargs:
                fade = int(kwargs[ATTR_TRANSITION] * 1000)
            else:
                fade = 0

            # These are both False if ATTR_POWER is not set
            power_on = kwargs.get(ATTR_POWER, False)
            power_off = not kwargs.get(ATTR_POWER, True)

            hsbk = find_hsbk(self.hass, **kwargs)

            # Send messages, waiting for ACK each time
            ack = AwaitAioLIFX().wait

            if not self.is_on:
                if power_off:
                    await self.set_power(ack, False)
                # If fading on with color, set color immediately
                if hsbk and power_on:
                    await self.set_color(ack, hsbk, kwargs)
                    await self.set_power(ack, True, duration=fade)
                elif hsbk:
                    await self.set_color(ack, hsbk, kwargs, duration=fade)
                elif power_on:
                    await self.set_power(ack, True, duration=fade)
            else:
                if power_on:
                    await self.set_power(ack, True)
                if hsbk:
                    await self.set_color(ack, hsbk, kwargs, duration=fade)
                if power_off:
                    await self.set_power(ack, False, duration=fade)

        # Update when the transition starts and ends
        await self.update_during_transition(fade)

    async def set_power(self, ack, pwr, duration=0):
        """Send a power change to the bulb."""
        await ack(partial(self.bulb.set_power, pwr, duration=duration))

    async def set_color(self, ack, hsbk, kwargs, duration=0):
        """Send a color change to the bulb."""
        hsbk = merge_hsbk(self.bulb.color, hsbk)
        await ack(partial(self.bulb.set_color, hsbk, duration=duration))

    async def default_effect(self, **kwargs):
        """Start an effect with default parameters."""
        service = kwargs[ATTR_EFFECT]
        data = {ATTR_ENTITY_ID: self.entity_id}
        await self.hass.services.async_call(
            DOMAIN, service, data, context=self._context
        )

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.async_on_remove(
            self.manager.async_register_entity(self.entity_id, self.entry.entry_id)
        )
        return await super().async_added_to_hass()


class LIFXWhite(LIFXLight):
    """Representation of a white-only LIFX light."""

    @property
    def effect_list(self):
        """Return the list of supported effects for this light."""
        return [SERVICE_EFFECT_PULSE, SERVICE_EFFECT_STOP]


class LIFXColor(LIFXLight):
    """Representation of a color LIFX light."""

    @property
    def color_mode(self) -> ColorMode:
        """Return the color mode of the light."""
        sat = self.bulb.color[1]
        if sat:
            return ColorMode.HS
        return ColorMode.COLOR_TEMP

    @property
    def supported_color_modes(self) -> set[ColorMode]:
        """Flag supported color modes."""
        return {ColorMode.COLOR_TEMP, ColorMode.HS}

    @property
    def effect_list(self):
        """Return the list of supported effects for this light."""
        return [SERVICE_EFFECT_COLORLOOP, SERVICE_EFFECT_PULSE, SERVICE_EFFECT_STOP]

    @property
    def hs_color(self):
        """Return the hs value."""
        hue, sat, _, _ = self.bulb.color
        hue = hue / 65535 * 360
        sat = sat / 65535 * 100
        return (hue, sat) if sat else None


class LIFXStrip(LIFXColor):
    """Representation of a LIFX light strip with multiple zones."""

    async def set_color(self, ack, hsbk, kwargs, duration=0):
        """Send a color change to the bulb."""
        bulb = self.bulb
        num_zones = len(bulb.color_zones)

        if (zones := kwargs.get(ATTR_ZONES)) is None:
            # Fast track: setting all zones to the same brightness and color
            # can be treated as a single-zone bulb.
            if hsbk[2] is not None and hsbk[3] is not None:
                await super().set_color(ack, hsbk, kwargs, duration)
                return

            zones = list(range(0, num_zones))
        else:
            zones = [x for x in set(zones) if x < num_zones]

        # Zone brightness is not reported when powered off
        if not self.is_on and hsbk[2] is None:
            await self.set_power(ack, True)
            await self.coordinator.async_request_refresh()
            await self.set_power(ack, False)
            await self.coordinator.async_request_refresh()

        # Send new color to each zone
        for index, zone in enumerate(zones):
            zone_hsbk = merge_hsbk(bulb.color_zones[zone], hsbk)
            apply = 1 if (index == len(zones) - 1) else 0
            set_zone = partial(
                bulb.set_color_zones,
                start_index=zone,
                end_index=zone,
                color=zone_hsbk,
                duration=duration,
                apply=apply,
            )
            await ack(set_zone)
