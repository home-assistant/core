"""Support for LIFX lights."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any

import aiolifx_effects as aiolifx_effects_module
import voluptuous as vol

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
from homeassistant.helpers.event import async_call_later

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
    SERVICE_EFFECT_FLAME,
    SERVICE_EFFECT_MORPH,
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
    if lifx_features(device)["matrix"]:
        entity: LIFXLight = LIFXMatrix(coordinator, manager, entry)
    elif lifx_features(device)["extended_multizone"]:
        entity = LIFXExtendedMultiZone(coordinator, manager, entry)
    elif lifx_features(device)["multizone"]:
        entity = LIFXMultiZone(coordinator, manager, entry)
    elif lifx_features(device)["color"]:
        entity = LIFXColor(coordinator, manager, entry)
    else:
        entity = LIFXWhite(coordinator, manager, entry)
    async_add_entities([entity])


class LIFXLight(LIFXEntity, LightEntity):
    """Representation of a LIFX light."""

    _attr_supported_features = LightEntityFeature.TRANSITION | LightEntityFeature.EFFECT
    _attr_name = None

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
        self._attr_min_color_temp_kelvin = bulb_features["min_kelvin"]
        self._attr_max_color_temp_kelvin = bulb_features["max_kelvin"]
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
    def color_temp_kelvin(self) -> int | None:
        """Return the color temperature of this light in kelvin."""
        return int(self.bulb.color[HSBK_KELVIN])

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
        self._cancel_postponed_update()

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

            self.postponed_update = async_call_later(
                self.hass,
                timedelta(milliseconds=when),
                _async_refresh,
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
                (
                    "The 'infrared' attribute of 'lifx.set_state' is deprecated:"
                    " call 'select.select_option' targeting '%s' instead"
                ),
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
        except TimeoutError as ex:
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
        except TimeoutError as ex:
            raise HomeAssistantError(f"Timeout setting color for {self.name}") from ex

    async def get_color(
        self,
    ) -> None:
        """Send a get color message to the bulb."""
        try:
            await self.coordinator.async_get_color()
        except TimeoutError as ex:
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

    def _cancel_postponed_update(self) -> None:
        """Cancel postponed update, if applicable."""
        if self.postponed_update:
            self.postponed_update()
            self.postponed_update = None

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        self._cancel_postponed_update()
        return await super().async_will_remove_from_hass()


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


class LIFXMultiZone(LIFXColor):
    """Representation of a legacy LIFX multizone device."""

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
        num_zones = self.coordinator.get_number_of_zones()

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

            zones = list(range(num_zones))
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
            except TimeoutError as ex:
                raise HomeAssistantError(
                    f"Timeout setting color zones for {self.name}"
                ) from ex

        # set_color_zones does not update the
        # state of the device, so we need to do that
        await self.get_color()

    async def update_color_zones(
        self,
    ) -> None:
        """Send a get color zones message to the device."""
        try:
            await self.coordinator.async_get_color_zones()
        except TimeoutError as ex:
            raise HomeAssistantError(
                f"Timeout getting color zones from {self.name}"
            ) from ex


class LIFXExtendedMultiZone(LIFXMultiZone):
    """Representation of a LIFX device that supports extended multizone messages."""

    async def set_color(
        self, hsbk: list[float | int | None], kwargs: dict[str, Any], duration: int = 0
    ) -> None:
        """Set colors on all zones of the device."""

        # trigger an update of all zone values before merging new values
        await self.coordinator.async_get_extended_color_zones()

        color_zones = self.bulb.color_zones
        if (zones := kwargs.get(ATTR_ZONES)) is None:
            # merge the incoming hsbk across all zones
            for index, zone in enumerate(color_zones):
                color_zones[index] = merge_hsbk(zone, hsbk)
        else:
            # merge the incoming HSBK with only the specified zones
            for index, zone in enumerate(color_zones):
                if index in zones:
                    color_zones[index] = merge_hsbk(zone, hsbk)

        # send the updated color zones list to the device
        try:
            await self.coordinator.async_set_extended_color_zones(
                color_zones, duration=duration
            )
        except TimeoutError as ex:
            raise HomeAssistantError(
                f"Timeout setting color zones on {self.name}"
            ) from ex

        # set_extended_color_zones does not update the
        # state of the device, so we need to do that
        await self.get_color()


class LIFXMatrix(LIFXColor):
    """Representation of a LIFX matrix device."""

    _attr_effect_list = [
        SERVICE_EFFECT_COLORLOOP,
        SERVICE_EFFECT_FLAME,
        SERVICE_EFFECT_PULSE,
        SERVICE_EFFECT_MORPH,
        SERVICE_EFFECT_STOP,
    ]
