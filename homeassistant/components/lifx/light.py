"""Support for LIFX lights."""

import asyncio
from datetime import datetime, timedelta
from typing import Any, cast, override

from lifx import (
    HSBK,
    CeilingLight,
    FirmwareEffect,
    HevLight,
    InfraredLight,
    LifxError,
    Light,
    LightWaveform,
    MatrixLight,
    MatrixLightState,
    MultiZoneLight,
    MultiZoneLightState,
)
import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_BRIGHTNESS_STEP,
    ATTR_BRIGHTNESS_STEP_PCT,
    ATTR_EFFECT,
    ATTR_TRANSITION,
    LIGHT_TURN_ON_SCHEMA,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.typing import VolDictType

from .const import (
    ATTR_DURATION,
    ATTR_INFRARED,
    ATTR_POWER,
    ATTR_ZONES,
    DATA_LIFX_MANAGER,
    DOMAIN,
    INFRARED_BRIGHTNESS,
    LOGGER,
)
from .coordinator import LIFXConfigEntry, LIFXUpdateCoordinator
from .entity import LIFXEntity
from .manager import (
    SERVICE_EFFECT_COLORLOOP,
    SERVICE_EFFECT_FLAME,
    SERVICE_EFFECT_MORPH,
    SERVICE_EFFECT_MOVE,
    SERVICE_EFFECT_PULSE,
    SERVICE_EFFECT_SKY,
    SERVICE_EFFECT_STOP,
    LIFXManager,
)
from .util import (
    device_error,
    find_hsbk,
    overwrites_existing_color,
    parse_hsbk_changes,
    replace_hsbk,
)

PARALLEL_UPDATES = 1

LIFX_STATE_SETTLE_DELAY = 0.3

LIFX_MIN_COLOR_RAMP = 0.25

SERVICE_LIFX_SET_STATE = "set_state"

LIFX_SET_STATE_SCHEMA: VolDictType = {
    **LIGHT_TURN_ON_SCHEMA,
    ATTR_INFRARED: vol.All(vol.Coerce(int), vol.Clamp(min=0, max=255)),
    ATTR_ZONES: vol.All(cv.ensure_list, [cv.positive_int]),
    ATTR_POWER: cv.boolean,
}

SERVICE_LIFX_SET_HEV_CYCLE_STATE = "set_hev_cycle_state"

LIFX_SET_HEV_CYCLE_STATE_SCHEMA: VolDictType = {
    vol.Required(ATTR_POWER): cv.boolean,
    ATTR_DURATION: vol.All(vol.Coerce(float), vol.Clamp(min=0, max=86400)),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LIFXConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up LIFX from a config entry."""
    coordinator = entry.runtime_data
    manager = hass.data[DATA_LIFX_MANAGER]
    device = coordinator.device
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_LIFX_SET_STATE,
        LIFX_SET_STATE_SCHEMA,
        "set_state",
    )
    if isinstance(device, CeilingLight):
        entity: LIFXLight = LIFXCeiling(coordinator, manager)
    elif isinstance(device, MatrixLight):
        entity = LIFXMatrix(coordinator, manager)
    elif isinstance(device, MultiZoneLight):
        entity = LIFXMultiZone(coordinator, manager)
    elif isinstance(device, HevLight):
        entity = LIFXHevLight(coordinator, manager)
        # Offered only once a bulb that has HEV LEDs is set up
        platform.async_register_entity_service(
            SERVICE_LIFX_SET_HEV_CYCLE_STATE,
            LIFX_SET_HEV_CYCLE_STATE_SCHEMA,
            "set_hev_cycle_state",
        )
    elif coordinator.data.capabilities.has_color:
        entity = LIFXColor(coordinator, manager)
    else:
        entity = LIFXLight(coordinator, manager)
    async_add_entities([entity])


class LIFXLight(LIFXEntity, LightEntity):
    """Representation of a LIFX light."""

    _attr_supported_features = LightEntityFeature.TRANSITION | LightEntityFeature.EFFECT
    _attr_name = None
    # A light without hue runs the effects that do not paint a color
    _attr_effect_list = [SERVICE_EFFECT_PULSE, SERVICE_EFFECT_STOP]

    def __init__(
        self,
        coordinator: LIFXUpdateCoordinator,
        manager: LIFXManager,
    ) -> None:
        """Initialize the light."""
        super().__init__(coordinator)

        state = coordinator.data
        device = coordinator.device
        assert isinstance(device, Light)
        self.device: Light = device
        self.manager = manager
        self.postponed_update: CALLBACK_TYPE | None = None
        if (kelvin_min := state.capabilities.kelvin_min) is not None:
            self._attr_min_color_temp_kelvin = kelvin_min
        if (kelvin_max := state.capabilities.kelvin_max) is not None:
            self._attr_max_color_temp_kelvin = kelvin_max
        if state.capabilities.has_variable_color_temp:
            color_mode = ColorMode.COLOR_TEMP
        else:
            color_mode = ColorMode.BRIGHTNESS

        self._attr_color_mode = color_mode
        self._attr_supported_color_modes = {color_mode}

    @property
    @override
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255."""
        return self.coordinator.data.color.brightness_uint8

    @property
    @override
    def color_temp_kelvin(self) -> int | None:
        """Return the color temperature of this light in kelvin."""
        return self.coordinator.data.color.kelvin

    @property
    @override
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self.coordinator.data.power != 0

    @property
    @override
    def effect(self) -> str | None:
        """Return the name of the currently running effect."""
        if software_effect := self.manager.effects_conductor.effect(self.device):
            return f"effect_{software_effect.name}"
        state = self.coordinator.data
        if (
            isinstance(state, (MultiZoneLightState, MatrixLightState))
            and (effect := state.effect) is not FirmwareEffect.OFF
        ):
            return f"effect_{effect.name.lower()}"
        return None

    async def update_during_transition(self, duration: float) -> None:
        """Update state at the start and end of a transition."""
        self._cancel_postponed_update()
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

        if duration > 0:

            async def _async_refresh(now: datetime) -> None:
                """Refresh the state."""
                await self.coordinator.async_refresh()

            self.postponed_update = async_call_later(
                self.hass,
                timedelta(seconds=duration),
                _async_refresh,
            )

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        await self.set_state(**{**kwargs, ATTR_POWER: True})

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        await self.set_state(**{**kwargs, ATTR_POWER: False})

    async def set_state(self, **kwargs: Any) -> None:
        """Set a color on the light and turn it on/off."""
        self._cancel_postponed_update()

        # Stopping an effect restores the pre-effect state, which writes to the device
        try:
            await self.manager.effects_conductor.stop([self.device])
        except LifxError as err:
            raise device_error(err) from err

        if ATTR_EFFECT in kwargs:
            await self.default_effect(**kwargs)
            return

        await self._async_set_deprecated_infrared(kwargs)

        duration = kwargs.get(ATTR_TRANSITION, 0.0)

        self._resolve_brightness_step(kwargs)

        # These are both False if ATTR_POWER is not set
        power_on = kwargs.get(ATTR_POWER, False)
        power_off = not kwargs.get(ATTR_POWER, True)

        new_hsbk = find_hsbk(self.coordinator.data.color, **kwargs)

        fading_on = power_on and not self.is_on

        if new_hsbk:
            await self.set_color(
                new_hsbk,
                kwargs,
                duration=0.0 if fading_on else max(duration, LIFX_MIN_COLOR_RAMP),
            )
        if power_on:
            await self.set_power(True, duration=duration if fading_on else 0.0)
        if power_off:
            await self.set_power(False, duration=duration if self.is_on else 0.0)

        # Avoid state ping-pong by holding off updates as the state settles
        await asyncio.sleep(LIFX_STATE_SETTLE_DELAY)

        # Update when the transition starts and ends
        await self.update_during_transition(duration)

    async def _async_set_deprecated_infrared(self, kwargs: dict[str, Any]) -> None:
        """Handle the deprecated 'infrared' attribute of 'lifx.set_state'."""
        if ATTR_INFRARED not in kwargs:
            return

        if not isinstance(self.device, InfraredLight):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="no_infrared",
                translation_placeholders={"entity_id": self.entity_id},
            )

        LOGGER.warning(
            (
                "The 'infrared' attribute of 'lifx.set_state' is deprecated:"
                " call 'number.set_value' targeting '%s' instead"
            ),
            self.coordinator.async_get_entity_id(Platform.NUMBER, INFRARED_BRIGHTNESS),
        )

        try:
            await self.device.set_infrared(kwargs[ATTR_INFRARED] / 255)
        except LifxError as err:
            raise device_error(err) from err

    def _resolve_brightness_step(self, kwargs: dict[str, Any]) -> None:
        """Turn a relative brightness step into the absolute brightness it asks for."""
        if ATTR_BRIGHTNESS_STEP in kwargs:
            brightness = self.brightness if self.is_on and self.brightness else 0
            brightness += kwargs.pop(ATTR_BRIGHTNESS_STEP)
        elif ATTR_BRIGHTNESS_STEP_PCT in kwargs:
            brightness = self.brightness if self.is_on and self.brightness else 0
            brightness_pct = round(brightness / 255 * 100)
            brightness = round(
                (brightness_pct + kwargs.pop(ATTR_BRIGHTNESS_STEP_PCT)) / 100 * 255
            )
        else:
            return
        kwargs[ATTR_BRIGHTNESS] = max(0, min(255, brightness))

    async def set_hev_cycle_state(
        self, power: bool, duration: float | None = None
    ) -> None:
        """Reject the action, since only a LIFX Clean bulb has HEV LEDs."""
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="no_hev",
            translation_placeholders={"entity_id": self.entity_id},
        )

    async def set_power(
        self,
        pwr: bool,
        duration: float = 0.0,
    ) -> None:
        """Send a power change to the bulb."""
        try:
            await self.device.set_power(pwr, duration=duration)
        except LifxError as err:
            raise device_error(err) from err

    async def set_color(
        self,
        hsbk: HSBK,
        kwargs: dict[str, Any],
        duration: float = 0.0,
    ) -> None:
        """Send a color change to the bulb."""
        changes = parse_hsbk_changes(**kwargs)
        try:
            await self.device.set_waveform_optional(
                hsbk,
                period=duration,
                cycles=1,
                waveform=LightWaveform.HALF_SINE,
                transient=False,
                set_hue=changes["hue"] is not None,
                set_saturation=changes["saturation"] is not None,
                set_brightness=changes["brightness"] is not None,
                set_kelvin=changes["kelvin"] is not None,
            )
        except LifxError as err:
            raise device_error(err) from err

    async def default_effect(self, **kwargs: Any) -> None:
        """Start an effect with default parameters."""
        await self.hass.services.async_call(
            DOMAIN,
            kwargs[ATTR_EFFECT],
            {ATTR_ENTITY_ID: self.entity_id},
            blocking=True,
            context=self._context,
        )

    @override
    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.async_on_remove(
            self.manager.async_register_entity(self.entity_id, self.coordinator)
        )
        return await super().async_added_to_hass()

    def _cancel_postponed_update(self) -> None:
        """Cancel postponed update, if applicable."""
        if self.postponed_update:
            self.postponed_update()
            self.postponed_update = None

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        self._cancel_postponed_update()
        return await super().async_will_remove_from_hass()


class LIFXColor(LIFXLight):
    """Representation of a color LIFX light."""

    _attr_effect_list = [
        SERVICE_EFFECT_COLORLOOP,
        SERVICE_EFFECT_PULSE,
        SERVICE_EFFECT_STOP,
    ]

    @property
    @override
    def supported_color_modes(self) -> set[ColorMode]:
        """Return the supported color modes."""
        return {ColorMode.COLOR_TEMP, ColorMode.HS}

    @property
    @override
    def color_mode(self) -> ColorMode:
        """Return the color mode of the light."""
        has_sat = self.coordinator.data.color.saturation
        return ColorMode.HS if has_sat else ColorMode.COLOR_TEMP

    @property
    @override
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hs value."""
        color = self.coordinator.data.color
        sat = color.saturation_pct
        return (color.hue, sat) if sat else None


class LIFXHevLight(LIFXColor):
    """Representation of a LIFX Clean bulb, which has HEV LEDs."""

    @override
    async def set_hev_cycle_state(
        self, power: bool, duration: float | None = None
    ) -> None:
        """Run or stop a cycle of the HEV LEDs."""
        # The protocol carries the cycle duration as whole seconds
        await self.coordinator.async_set_hev_cycle_state(power, round(duration or 0))
        await self.update_during_transition(duration or 0)


class LIFXMultiZone(LIFXColor):
    """Representation of a LIFX multizone device."""

    device: MultiZoneLight

    _attr_effect_list = [
        SERVICE_EFFECT_COLORLOOP,
        SERVICE_EFFECT_PULSE,
        SERVICE_EFFECT_MOVE,
        SERVICE_EFFECT_STOP,
    ]

    @override
    async def set_color(
        self,
        hsbk: HSBK,
        kwargs: dict[str, Any],
        duration: float = 0.0,
    ) -> None:
        """Set the requested zones, leaving every other zone as it is."""
        device = self.device
        changes = parse_hsbk_changes(**kwargs)
        requested_zones = kwargs.get(ATTR_ZONES)

        overwrites_every_zone = requested_zones is None and overwrites_existing_color(
            changes
        )
        if not overwrites_every_zone:
            # Every zone is written back, so a zone changed outside Home
            # Assistant has to be read before it is merged over
            await self.coordinator.async_refresh()

        state = cast(MultiZoneLightState, self.coordinator.data)
        if overwrites_every_zone:
            colors = [hsbk] * state.zone_count
            zones = list(range(state.zone_count))
        else:
            colors = list(state.zones)
            # The device can report more zones than it has returned colors for
            zone_count = min(state.zone_count, len(colors))
            zones = (
                list(range(zone_count))
                if requested_zones is None
                else sorted({zone for zone in requested_zones if zone < zone_count})
            )
            for zone in zones:
                colors[zone] = replace_hsbk(colors[zone], changes)

        if not zones:
            return

        try:
            await device.set_all_color_zones(
                colors, start=zones[0], end=zones[-1], duration=duration
            )
        except LifxError as err:
            raise device_error(err) from err


class LIFXMatrix(LIFXColor):
    """Representation of a LIFX matrix device."""

    device: MatrixLight

    _attr_effect_list = [
        SERVICE_EFFECT_COLORLOOP,
        SERVICE_EFFECT_FLAME,
        SERVICE_EFFECT_PULSE,
        SERVICE_EFFECT_MORPH,
        SERVICE_EFFECT_STOP,
    ]

    @override
    async def set_color(
        self,
        hsbk: HSBK,
        kwargs: dict[str, Any],
        duration: float = 0.0,
    ) -> None:
        """Set the tile colors, leaving each tile at its own brightness."""
        device = self.device
        if not cast(MatrixLightState, self.coordinator.data).tile_colors:
            await super().set_color(hsbk, kwargs, duration)
            return
        changes = parse_hsbk_changes(**kwargs)
        if not overwrites_existing_color(changes):
            # Every tile is written back, so a tile changed outside Home
            # Assistant has to be read before it is merged over
            await self.coordinator.async_refresh()
        state = cast(MatrixLightState, self.coordinator.data)
        colors = [replace_hsbk(color, changes) for color in state.tile_colors]
        # tile_colors spans the whole chain, but each tile is written on its own
        offset = 0
        try:
            for tile in state.chain:
                tile_colors = colors[offset : offset + tile.total_zones]
                offset += tile.total_zones
                if len(tile_colors) != tile.total_zones:
                    LOGGER.warning(
                        "Not writing tile %s of %s: the device reported %s of the"
                        " %s colors the tile covers",
                        tile.tile_index,
                        self.entity_id,
                        len(tile_colors),
                        tile.total_zones,
                    )
                    continue
                await device.set_matrix_colors(
                    tile.tile_index,
                    tile_colors,
                    duration=round(duration * 1000),
                )
        except LifxError as err:
            raise device_error(err) from err


class LIFXCeiling(LIFXMatrix):
    """Representation of a LIFX Ceiling device."""

    _attr_effect_list = [
        SERVICE_EFFECT_COLORLOOP,
        SERVICE_EFFECT_FLAME,
        SERVICE_EFFECT_PULSE,
        SERVICE_EFFECT_MORPH,
        SERVICE_EFFECT_SKY,
        SERVICE_EFFECT_STOP,
    ]
