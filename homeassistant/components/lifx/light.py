"""Support for LIFX lights."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
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
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_platform
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_utc_time
import homeassistant.util.color as color_util

from .const import (
    _LOGGER,
    ATTR_DURATION,
    ATTR_INFRARED,
    ATTR_POWER,
    ATTR_ZONES,
    DATA_LIFX_MANAGER,
    DOMAIN,
    INFRARED_BRIGHTNESS,
)
from .coordinator import FirmwareEffect, LIFXUpdateCoordinator
from .entity import LIFXEntity
from .manager import (
    SERVICE_EFFECT_COLORLOOP,
    SERVICE_EFFECT_MOVE,
    SERVICE_EFFECT_PULSE,
    SERVICE_EFFECT_STOP,
    LIFXManager,
)
from .util import convert_8_to_16, convert_16_to_8, find_hsbk, lifx_features, merge_hsbk

LIFX_STATE_SETTLE_DELAY = 0.3

SERVICE_LIFX_SET_STATE = "set_state"

LIFX_SET_STATE_SCHEMA = {
    **LIGHT_TURN_ON_SCHEMA,
    ATTR_INFRARED: vol.All(vol.Coerce(int), vol.Clamp(min=0, max=255)),
    ATTR_ZONES: vol.All(cv.ensure_list, [cv.positive_int]),
    ATTR_POWER: cv.boolean,
}


SERVICE_LIFX_SET_HEV_CYCLE_STATE = "set_hev_cycle_state"

LIFX_SET_HEV_CYCLE_STATE_SCHEMA = {
    ATTR_POWER: vol.Required(cv.boolean),
    ATTR_DURATION: vol.All(vol.Coerce(float), vol.Clamp(min=0, max=86400)),
}

HSBK_HUE = 0
HSBK_SATURATION = 1
HSBK_BRIGHTNESS = 2
HSBK_KELVIN = 3


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up LIFX from a config entry."""
    domain_data = hass.data[DOMAIN]
    coordinator: LIFXUpdateCoordinator = domain_data[entry.entry_id]
    manager: LIFXManager = domain_data[DATA_LIFX_MANAGER]
    device = coordinator.device
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_LIFX_SET_STATE,
        LIFX_SET_STATE_SCHEMA,
        "set_state",
    )
    platform.async_register_entity_service(
        SERVICE_LIFX_SET_HEV_CYCLE_STATE,
        LIFX_SET_HEV_CYCLE_STATE_SCHEMA,
        "set_hev_cycle_state",
    )
    if lifx_features(device)["multizone"]:
        entity: LIFXLight = LIFXStrip(coordinator, manager, entry)
    elif lifx_features(device)["color"]:
        entity = LIFXColor(coordinator, manager, entry)
    else:
        entity = LIFXWhite(coordinator, manager, entry)
    async_add_entities([entity])


class LIFXLight(LIFXEntity, LightEntity):
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

        self.mac_addr = self.bulb.mac_addr
        bulb_features = lifx_features(self.bulb)
        self.manager = manager
        self.effects_conductor: aiolifx_effects_module.Conductor = (
            manager.effects_conductor
        )
        self.postponed_update: CALLBACK_TYPE | None = None
        self.entry = entry
        self._attr_unique_id = self.coordinator.serial_number
        self._attr_name = self.bulb.label
        self._attr_min_mireds = math.floor(
            color_util.color_temperature_kelvin_to_mired(bulb_features["max_kelvin"])
        )
        self._attr_max_mireds = math.ceil(
            color_util.color_temperature_kelvin_to_mired(bulb_features["min_kelvin"])
        )
        if bulb_features["min_kelvin"] != bulb_features["max_kelvin"]:
            color_mode = ColorMode.COLOR_TEMP
        else:
            color_mode = ColorMode.BRIGHTNESS
        self._attr_color_mode = color_mode
        self._attr_supported_color_modes = {color_mode}
        self._attr_effect = None

    @property
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255."""
        fade = self.bulb.power_level / 65535
        return convert_16_to_8(int(fade * self.bulb.color[HSBK_BRIGHTNESS]))

    @property
    def color_temp(self) -> int | None:
        """Return the color temperature."""
        return color_util.color_temperature_kelvin_to_mired(
            self.bulb.color[HSBK_KELVIN]
        )

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return bool(self.bulb.power_level != 0)

    @property
    def effect(self) -> str | None:
        """Return the name of the currently running effect."""
        if effect := self.effects_conductor.effect(self.bulb):
            return f"effect_{effect.name}"
        if effect := self.coordinator.async_get_active_effect():
            return f"effect_{FirmwareEffect(effect).name.lower()}"
        return None

    async def update_during_transition(self, when: int) -> None:
        """Update state at the start and end of a transition."""
        if self.postponed_update:
            self.postponed_update()
            self.postponed_update = None

        # Transition has started
        self.async_write_ha_state()

        # The state reply we get back may be stale so we also request
        # a refresh to get a fresh state
        # https://lan.developer.lifx.com/docs/changing-a-device
        await self.coordinator.async_request_refresh()

        # Transition has ended
        if when > 0:

            async def _async_refresh(now: datetime) -> None:
                """Refresh the state."""
                await self.coordinator.async_refresh()

            self.postponed_update = async_track_point_in_utc_time(
                self.hass,
                _async_refresh,
                util.dt.utcnow() + timedelta(milliseconds=when),
            )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        await self.set_state(**{**kwargs, ATTR_POWER: True})

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self.set_state(**{**kwargs, ATTR_POWER: False})

    async def set_state(self, **kwargs: Any) -> None:
        """Set a color on the light and turn it on/off."""
        self.coordinator.async_set_updated_data(None)
        async with self.coordinator.lock:
            # Cancel any pending refreshes
            bulb = self.bulb

            await self.effects_conductor.stop([bulb])

            if ATTR_EFFECT in kwargs:
                await self.default_effect(**kwargs)
                return

            if ATTR_INFRARED in kwargs:
                infrared_entity_id = self.coordinator.async_get_entity_id(
                    Platform.SELECT, INFRARED_BRIGHTNESS
                )
                _LOGGER.warning(
                    "The 'infrared' attribute of 'lifx.set_state' is deprecated: call 'select.select_option' targeting '%s' instead",
                    infrared_entity_id,
                )
                bulb.set_infrared(convert_8_to_16(kwargs[ATTR_INFRARED]))

            if ATTR_TRANSITION in kwargs:
                fade = int(kwargs[ATTR_TRANSITION] * 1000)
            else:
                fade = 0

            # These are both False if ATTR_POWER is not set
            power_on = kwargs.get(ATTR_POWER, False)
            power_off = not kwargs.get(ATTR_POWER, True)

            hsbk = find_hsbk(self.hass, **kwargs)

            if not self.is_on:
                if power_off:
                    await self.set_power(False)
                # If fading on with color, set color immediately
                if hsbk and power_on:
                    await self.set_color(hsbk, kwargs)
                    await self.set_power(True, duration=fade)
                elif hsbk:
                    await self.set_color(hsbk, kwargs, duration=fade)
                elif power_on:
                    await self.set_power(True, duration=fade)
            else:
                if power_on:
                    await self.set_power(True)
                if hsbk:
                    await self.set_color(hsbk, kwargs, duration=fade)
                if power_off:
                    await self.set_power(False, duration=fade)

            # Avoid state ping-pong by holding off updates as the state settles
            await asyncio.sleep(LIFX_STATE_SETTLE_DELAY)

        # Update when the transition starts and ends
        await self.update_during_transition(fade)

    async def set_hev_cycle_state(
        self, power: bool, duration: int | None = None
    ) -> None:
        """Set the state of the HEV LEDs on a LIFX Clean bulb."""
        if lifx_features(self.bulb)["hev"] is False:
            raise HomeAssistantError(
                "This device does not support setting HEV cycle state"
            )

        await self.coordinator.async_set_hev_cycle_state(power, duration or 0)
        await self.update_during_transition(duration or 0)

    async def set_power(
        self,
        pwr: bool,
        duration: int = 0,
    ) -> None:
        """Send a power change to the bulb."""
        try:
            await self.coordinator.async_set_power(pwr, duration)
        except asyncio.TimeoutError as ex:
            raise HomeAssistantError(f"Timeout setting power for {self.name}") from ex

    async def set_color(
        self,
        hsbk: list[float | int | None],
        kwargs: dict[str, Any],
        duration: int = 0,
    ) -> None:
        """Send a color change to the bulb."""
        merged_hsbk = merge_hsbk(self.bulb.color, hsbk)
        try:
            await self.coordinator.async_set_color(merged_hsbk, duration)
        except asyncio.TimeoutError as ex:
            raise HomeAssistantError(f"Timeout setting color for {self.name}") from ex

    async def get_color(
        self,
    ) -> None:
        """Send a get color message to the bulb."""
        try:
            await self.coordinator.async_get_color()
        except asyncio.TimeoutError as ex:
            raise HomeAssistantError(
                f"Timeout setting getting color for {self.name}"
            ) from ex

    async def default_effect(self, **kwargs: Any) -> None:
        """Start an effect with default parameters."""
        await self.hass.services.async_call(
            DOMAIN,
            kwargs[ATTR_EFFECT],
            {ATTR_ENTITY_ID: self.entity_id},
            context=self._context,
        )

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.async_on_remove(
            self.manager.async_register_entity(self.entity_id, self.entry.entry_id)
        )
        return await super().async_added_to_hass()


class LIFXWhite(LIFXLight):
    """Representation of a white-only LIFX light."""

    _attr_effect_list = [SERVICE_EFFECT_PULSE, SERVICE_EFFECT_STOP]


class LIFXColor(LIFXLight):
    """Representation of a color LIFX light."""

    _attr_effect_list = [
        SERVICE_EFFECT_COLORLOOP,
        SERVICE_EFFECT_PULSE,
        SERVICE_EFFECT_STOP,
    ]

    @property
    def supported_color_modes(self) -> set[ColorMode]:
        """Return the supported color modes."""
        return {ColorMode.COLOR_TEMP, ColorMode.HS}

    @property
    def color_mode(self) -> ColorMode:
        """Return the color mode of the light."""
        has_sat = self.bulb.color[HSBK_SATURATION]
        return ColorMode.HS if has_sat else ColorMode.COLOR_TEMP

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hs value."""
        hue, sat, _, _ = self.bulb.color
        hue = hue / 65535 * 360
        sat = sat / 65535 * 100
        return (hue, sat) if sat else None


class LIFXStrip(LIFXColor):
    """Representation of a LIFX light strip with multiple zones."""

    _attr_effect_list = [
        SERVICE_EFFECT_COLORLOOP,
        SERVICE_EFFECT_PULSE,
        SERVICE_EFFECT_MOVE,
        SERVICE_EFFECT_STOP,
    ]

    async def set_color(
        self,
        hsbk: list[float | int | None],
        kwargs: dict[str, Any],
        duration: int = 0,
    ) -> None:
        """Send a color change to the bulb."""
        bulb = self.bulb
        color_zones = bulb.color_zones
        num_zones = len(color_zones)

        # Zone brightness is not reported when powered off
        if not self.is_on and hsbk[HSBK_BRIGHTNESS] is None:
            await self.set_power(True)
            await asyncio.sleep(LIFX_STATE_SETTLE_DELAY)
            await self.update_color_zones()
            await self.set_power(False)

        if (zones := kwargs.get(ATTR_ZONES)) is None:
            # Fast track: setting all zones to the same brightness and color
            # can be treated as a single-zone bulb.
            first_zone = color_zones[0]
            first_zone_brightness = first_zone[HSBK_BRIGHTNESS]
            all_zones_have_same_brightness = all(
                color_zones[zone][HSBK_BRIGHTNESS] == first_zone_brightness
                for zone in range(num_zones)
            )
            all_zones_are_the_same = all(
                color_zones[zone] == first_zone for zone in range(num_zones)
            )
            if (
                all_zones_have_same_brightness or hsbk[HSBK_BRIGHTNESS] is not None
            ) and (all_zones_are_the_same or hsbk[HSBK_KELVIN] is not None):
                await super().set_color(hsbk, kwargs, duration)
                return

            zones = list(range(0, num_zones))
        else:
            zones = [x for x in set(zones) if x < num_zones]

        # Send new color to each zone
        for index, zone in enumerate(zones):
            zone_hsbk = merge_hsbk(color_zones[zone], hsbk)
            apply = 1 if (index == len(zones) - 1) else 0
            try:
                await self.coordinator.async_set_color_zones(
                    zone, zone, zone_hsbk, duration, apply
                )
            except asyncio.TimeoutError as ex:
                raise HomeAssistantError(
                    f"Timeout setting color zones for {self.name}"
                ) from ex

        # set_color_zones does not update the
        # state of the bulb, so we need to do that
        await self.get_color()

    async def update_color_zones(
        self,
    ) -> None:
        """Send a get color zones message to the bulb."""
        try:
            await self.coordinator.async_update_color_zones()
        except asyncio.TimeoutError as ex:
            raise HomeAssistantError(
                f"Timeout setting updating color zones for {self.name}"
            ) from ex
