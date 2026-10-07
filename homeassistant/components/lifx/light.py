"""Support for LIFX lights."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Self, cast, override

from lifx import (
    HSBK,
    CeilingLight,
    CeilingLightState,
    FirmwareEffect,
    HevLight,
    InfraredLight,
    LifxError,
    Light,
    LightWaveform,
    MatrixLight,
    MatrixLightState,
    MirrorLight,
    MirrorLightState,
    MultiZoneLight,
    MultiZoneLightState,
)
from lifx.products import supports_sky_effect

from homeassistant.components.light import (
    ATTR_EFFECT,
    ATTR_TRANSITION,
    ColorMode,
    LightEntity,
    LightEntityDescription,
    LightEntityFeature,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity

from .const import (
    ATTR_INFRARED,
    ATTR_POWER,
    ATTR_ZONES,
    DATA_LIFX_MANAGER,
    DOMAIN,
    INFRARED_BRIGHTNESS,
    LOGGER,
    SERVICE_EFFECT_COLORLOOP,
    SERVICE_EFFECT_COLORSWEEP,
    SERVICE_EFFECT_FLAME,
    SERVICE_EFFECT_MORPH,
    SERVICE_EFFECT_MOVE,
    SERVICE_EFFECT_PULSE,
    SERVICE_EFFECT_SKY,
    SERVICE_EFFECT_STOP,
)
from .coordinator import LIFXConfigEntry, LIFXUpdateCoordinator
from .entity import LIFXEntity
from .manager import LIFXManager
from .util import (
    HSBKChanges,
    device_error,
    find_hsbk,
    overwrites_existing_color,
    parse_hsbk_changes,
    replace_hsbk,
    requested,
    resolve_brightness_step,
)

PARALLEL_UPDATES = 1

LIFX_STATE_SETTLE_DELAY = 0.3

LIFX_MIN_COLOR_RAMP = 0.25

# Matrix firmware effects run on the whole device, and stopping covers every effect
COMPONENT_FORWARDED_EFFECTS = {
    SERVICE_EFFECT_COLORSWEEP,
    SERVICE_EFFECT_FLAME,
    SERVICE_EFFECT_MORPH,
    SERVICE_EFFECT_SKY,
    SERVICE_EFFECT_STOP,
}


@callback
def _async_setup_component_sync(
    hass: HomeAssistant,
    entry: LIFXConfigEntry,
    main_unique_id: str,
    unique_ids: set[str],
) -> None:
    """Keep components enabled together, and only while their main light is.

    Each component routes by the other, and a component forwards firmware
    effects through the main light, which does nothing while it is disabled.
    """
    entity_registry = er.async_get(hass)

    @callback
    def _event_filter(event_data: er.EventEntityRegistryUpdatedData) -> bool:
        """Skip everything except a disable or enable, cheaply."""
        return (
            event_data["action"] == "update" and "disabled_by" in event_data["changes"]
        )

    @callback
    def _async_update(
        unique_id: str, disabled_by: er.RegistryEntryDisabler | None
    ) -> None:
        """Set whether one of this device's lights is disabled."""
        if (
            entity_id := entity_registry.async_get_entity_id(
                Platform.LIGHT, DOMAIN, unique_id
            )
        ) is not None:
            entity_registry.async_update_entity(entity_id, disabled_by=disabled_by)

    @callback
    def _async_sync(event: Event[er.EventEntityRegistryUpdatedData]) -> None:
        """Carry an enable or disable over to the device's other lights.

        No reentrancy guard is needed: the registry fires no event at all
        for an entity already at the target disabled_by, which is what each
        carried-over update ends at, so the chain runs out on its own.
        """
        changed = entity_registry.async_get(event.data["entity_id"])
        if (
            changed is None
            or changed.domain != Platform.LIGHT
            or changed.platform != DOMAIN
        ):
            return
        if changed.unique_id == main_unique_id:
            # Re-enabling the main light leaves its components as they were
            if changed.disabled_by is not None:
                for unique_id in unique_ids:
                    _async_update(unique_id, changed.disabled_by)
            return
        if changed.unique_id not in unique_ids:
            return
        for unique_id in unique_ids - {changed.unique_id}:
            _async_update(unique_id, changed.disabled_by)
        if changed.disabled_by is None:
            _async_update(main_unique_id, None)

    entry.async_on_unload(
        hass.bus.async_listen(
            er.EVENT_ENTITY_REGISTRY_UPDATED,
            _async_sync,
            event_filter=_event_filter,
        )
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LIFXConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up LIFX from a config entry."""
    coordinator = entry.runtime_data
    manager = hass.data[DATA_LIFX_MANAGER]
    device = coordinator.device
    entity: LIFXLight
    components: list[
        LIFXComponentLight[CeilingLight, CeilingLightState]
        | LIFXComponentLight[MirrorLight, MirrorLightState]
    ] = []
    if isinstance(device, MirrorLight):
        entity = LIFXMirror(coordinator, manager)
        components = [
            LIFXComponentLight(coordinator, manager, device, description)
            for description in MIRROR_COMPONENTS
        ]
    elif isinstance(device, CeilingLight):
        entity = LIFXMatrix(coordinator, manager)
        components = [
            LIFXComponentLight(coordinator, manager, device, description)
            for description in CEILING_COMPONENTS
        ]
    elif isinstance(device, MatrixLight):
        entity = LIFXMatrix(coordinator, manager)
    elif isinstance(device, MultiZoneLight):
        entity = LIFXMultiZone(coordinator, manager)
    elif isinstance(device, HevLight):
        entity = LIFXHevLight(coordinator, manager)
    elif coordinator.data.capabilities.has_color:
        entity = LIFXColor(coordinator, manager)
    else:
        entity = LIFXLight(coordinator, manager)
    async_add_entities([entity, *components])
    if components:
        _async_setup_component_sync(
            hass,
            entry,
            cast(str, entity.unique_id),
            {cast(str, component.unique_id) for component in components},
        )


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
            # The library reads an effect the protocol does not document as an
            # UNKNOWN member, which no effect list offers
            and effect.name in FirmwareEffect.__members__
        ):
            # Action names drop the underscore, as in effect_colorsweep
            return f"effect_{effect.name.lower().replace('_', '')}"
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
            self.raise_no_infrared()

        LOGGER.warning(
            (
                "The 'infrared' attribute of 'lifx.set_state' is deprecated:"
                " call 'select.select_option' targeting '%s' instead"
            ),
            self.coordinator.async_get_entity_id(Platform.SELECT, INFRARED_BRIGHTNESS),
        )

        try:
            await self.device.set_infrared(kwargs[ATTR_INFRARED] / 255)
        except LifxError as err:
            raise device_error(err) from err

    def _resolve_brightness_step(self, kwargs: dict[str, Any]) -> None:
        """Turn a relative brightness step into the absolute brightness it asks for."""
        resolve_brightness_step(
            kwargs, self.brightness if self.is_on and self.brightness else 0
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
            await self.async_refresh_before_merge()

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

    # Firmware effects that only some matrix models run
    _model_effects: tuple[str, ...] = ()

    def __init__(
        self,
        coordinator: LIFXUpdateCoordinator,
        manager: LIFXManager,
    ) -> None:
        """Initialize the matrix light, offering Sky if its firmware runs it."""
        super().__init__(coordinator, manager)
        state = coordinator.data
        effects = [
            SERVICE_EFFECT_COLORLOOP,
            SERVICE_EFFECT_FLAME,
            SERVICE_EFFECT_PULSE,
            SERVICE_EFFECT_MORPH,
        ]
        if supports_sky_effect(
            state.capabilities.has_matrix, state.host_firmware.version_major
        ):
            effects.append(SERVICE_EFFECT_SKY)
        self._attr_effect_list = [*effects, *self._model_effects, SERVICE_EFFECT_STOP]

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
            await self.async_refresh_before_merge()
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


class LIFXMirror(LIFXMatrix):
    """Representation of a LIFX Mirror device."""

    _model_effects = (SERVICE_EFFECT_COLORSWEEP,)


@dataclass(frozen=True, kw_only=True)
class LIFXComponentDescription[
    DeviceT: CeilingLight | MirrorLight,
    StateT: CeilingLightState | MirrorLightState,
](LightEntityDescription):
    """Describes one component of a LIFX device, as a list of zone colours."""

    is_on_fn: Callable[[StateT], bool]
    colors_fn: Callable[[StateT], list[HSBK]]
    partner_colors_fn: Callable[[StateT], list[HSBK]]
    stored_colors_fn: Callable[[StateT], list[HSBK] | None]
    turn_on_fn: Callable[[DeviceT, list[HSBK] | None, float], Awaitable[None]]
    turn_off_fn: Callable[[DeviceT, list[HSBK] | None, float], Awaitable[None]]


async def _turn_uplight_on(
    device: CeilingLight, colors: list[HSBK] | None, duration: float
) -> None:
    """Turn the single-zone uplight on."""
    await device.turn_uplight_on(colors[0] if colors else None, duration)


async def _turn_uplight_off(
    device: CeilingLight, colors: list[HSBK] | None, duration: float
) -> None:
    """Turn the single-zone uplight off, remembering a color if given."""
    await device.turn_uplight_off(colors[0] if colors else None, duration)


CEILING_COMPONENTS: tuple[
    LIFXComponentDescription[CeilingLight, CeilingLightState], ...
] = (
    LIFXComponentDescription[CeilingLight, CeilingLightState](
        key="uplight",
        translation_key="uplight",
        is_on_fn=lambda state: state.uplight_is_on,
        colors_fn=lambda state: [state.uplight_color],
        partner_colors_fn=lambda state: state.downlight_colors,
        stored_colors_fn=lambda state: (
            None if state.stored_uplight_color is None else [state.stored_uplight_color]
        ),
        turn_on_fn=_turn_uplight_on,
        turn_off_fn=_turn_uplight_off,
    ),
    LIFXComponentDescription[CeilingLight, CeilingLightState](
        key="downlight",
        translation_key="downlight",
        is_on_fn=lambda state: state.downlight_is_on,
        colors_fn=lambda state: state.downlight_colors,
        partner_colors_fn=lambda state: [state.uplight_color],
        stored_colors_fn=lambda state: state.stored_downlight_colors,
        turn_on_fn=lambda device, colors, duration: device.turn_downlight_on(
            colors, duration
        ),
        turn_off_fn=lambda device, colors, duration: device.turn_downlight_off(
            colors, duration
        ),
    ),
)

MIRROR_COMPONENTS: tuple[
    LIFXComponentDescription[MirrorLight, MirrorLightState], ...
] = (
    LIFXComponentDescription[MirrorLight, MirrorLightState](
        key="front",
        translation_key="front",
        is_on_fn=lambda state: state.front_is_on,
        colors_fn=lambda state: state.front_colors,
        partner_colors_fn=lambda state: state.back_colors,
        stored_colors_fn=lambda state: state.stored_front_colors,
        turn_on_fn=lambda device, colors, duration: device.turn_front_on(
            colors, duration
        ),
        turn_off_fn=lambda device, colors, duration: device.turn_front_off(
            colors, duration
        ),
    ),
    LIFXComponentDescription[MirrorLight, MirrorLightState](
        key="back",
        translation_key="back",
        is_on_fn=lambda state: state.back_is_on,
        colors_fn=lambda state: state.back_colors,
        partner_colors_fn=lambda state: state.front_colors,
        stored_colors_fn=lambda state: state.stored_back_colors,
        turn_on_fn=lambda device, colors, duration: device.turn_back_on(
            colors, duration
        ),
        turn_off_fn=lambda device, colors, duration: device.turn_back_off(
            colors, duration
        ),
    ),
)


@dataclass
class LIFXComponentExtraData(ExtraStoredData):
    """The colors a component returns to when turned on after a restart."""

    colors: list[HSBK] | None

    @override
    def as_dict(self) -> dict[str, Any]:
        """Return the colors in a form that can be saved."""
        return {
            "colors": None
            if self.colors is None
            else [
                [color.hue, color.saturation, color.brightness, color.kelvin]
                for color in self.colors
            ]
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Return the colors saved by as_dict, or none if they cannot be read."""
        if (colors := data.get("colors")) is None:
            return cls(None)
        try:
            return cls([HSBK(*color) for color in colors])
        except TypeError, ValueError:
            return cls(None)


class LIFXComponentLight[
    DeviceT: CeilingLight | MirrorLight,
    StateT: CeilingLightState | MirrorLightState,
](LIFXEntity, LightEntity, RestoreEntity):
    """Representation of one component of a LIFX device, controlled on its own."""

    entity_description: LIFXComponentDescription[DeviceT, StateT]

    _attr_entity_registry_enabled_default = False
    _attr_supported_features = LightEntityFeature.TRANSITION
    _attr_supported_color_modes = {ColorMode.COLOR_TEMP, ColorMode.HS}

    def __init__(
        self,
        coordinator: LIFXUpdateCoordinator,
        manager: LIFXManager,
        device: DeviceT,
        description: LIFXComponentDescription[DeviceT, StateT],
    ) -> None:
        """Initialise the component light."""
        super().__init__(coordinator, description)
        self.device = device
        self.manager = manager
        capabilities = coordinator.data.capabilities
        if (kelvin_min := capabilities.kelvin_min) is not None:
            self._attr_min_color_temp_kelvin = kelvin_min
        if (kelvin_max := capabilities.kelvin_max) is not None:
            self._attr_max_color_temp_kelvin = kelvin_max
        self._restored_colors: list[HSBK] | None = None
        self._async_update_attrs()

    @property
    def _state(self) -> StateT:
        """Return the device state, which is always the state of DeviceT."""
        return cast(StateT, self.coordinator.data)

    @override
    async def async_added_to_hass(self) -> None:
        """Pick up the colors the component had before the restart."""
        await super().async_added_to_hass()
        if (extra := await self.async_get_last_extra_data()) is not None:
            self._restored_colors = LIFXComponentExtraData.from_dict(
                extra.as_dict()
            ).colors

    @property
    @override
    def extra_restore_state_data(self) -> LIFXComponentExtraData:
        """Return the colors to restore after the next restart."""
        return LIFXComponentExtraData(
            self._library_remembered_colors() or self._restored_colors
        )

    @callback
    @override
    def _async_update_attrs(self) -> None:
        """Update the attributes that track coordinator data."""
        state = self._state
        description = self.entity_description
        self._attr_is_on = description.is_on_fn(state)
        # The firmware only averages the whole device, so average each component
        color = HSBK.average(description.colors_fn(state))
        self._attr_brightness = color.brightness_uint8
        self._attr_hs_color = (color.hue, color.saturation_pct)
        self._attr_color_temp_kelvin = color.kelvin
        self._attr_color_mode = (
            ColorMode.COLOR_TEMP if color.saturation == 0 else ColorMode.HS
        )

    def _library_remembered_colors(self) -> list[HSBK] | None:
        """Return the colors the library remembers, if any of them are lit."""
        stored = self.entity_description.stored_colors_fn(self._state)
        if stored is None or all(color.brightness == 0 for color in stored):
            return None
        return stored

    def _remembered_colors(self) -> list[HSBK] | None:
        """Prefer the library's memory, then what was restored after a restart."""
        return self._library_remembered_colors() or self._valid_restored_colors()

    def _valid_restored_colors(self) -> list[HSBK] | None:
        """Return the restored colors if they still fit the device."""
        restored = self._restored_colors
        # The library refuses a dark color, so dark colors are never restored
        if restored is None or all(color.brightness == 0 for color in restored):
            return None
        current = self.entity_description.colors_fn(self._state)
        # A color changed while Home Assistant was down no longer matches. The
        # zone count is fixed in hardware and the data belongs to this serial
        if any(
            now.replace(brightness=then.brightness) != then
            for then, now in zip(restored, current, strict=True)
        ):
            return None
        return restored

    def _bare_turn_on_colors(self) -> list[HSBK] | None:
        """Use the restored colors once, until the library remembers its own."""
        if self._library_remembered_colors() is not None:
            return None
        colors, self._restored_colors = self._valid_restored_colors(), None
        return colors

    def _merge_base(self) -> list[HSBK]:
        """Return the colors a change is merged onto, which are never dark."""
        state = self._state
        description = self.entity_description
        current = description.colors_fn(state)
        if any(color.brightness > 0 for color in current):
            return current
        if (remembered := self._remembered_colors()) is not None:
            return remembered
        # The library powers the device off rather than leave both components
        # dark, so the other component has a brightness to borrow
        brightness = HSBK.average(description.partner_colors_fn(state)).brightness
        return [color.with_brightness(brightness) for color in current]

    def _colors_to_write(self, changes: HSBKChanges) -> list[HSBK]:
        """Return every zone's color with the change applied."""
        return [replace_hsbk(color, changes) for color in self._merge_base()]

    async def _async_apply(self, kwargs: dict[str, Any], *, power: bool) -> None:
        """Apply a light call to the component, leaving it on or off as asked."""
        # Stopping an effect restores the pre-effect state, which writes to the device
        try:
            await self.manager.async_stop_effects(self.device)
        except LifxError as err:
            raise device_error(err) from err
        duration = kwargs.pop(ATTR_TRANSITION, 0.0)
        resolve_brightness_step(
            kwargs, self.brightness if self.is_on and self.brightness else 0
        )
        changes = parse_hsbk_changes(**kwargs)
        colors: list[HSBK] | None = None
        if changes["brightness"] == 0:
            # The library refuses a dark color, so zero brightness means off
            power = False
        elif requested(changes):
            if not overwrites_existing_color(changes):
                # Every zone is written back, so a zone changed outside Home
                # Assistant has to be read before it is merged over
                await self.async_refresh_before_merge()
            colors = self._colors_to_write(changes)
        elif power and self.is_on:
            # Turning on again would repaint the component from the library's
            # remembered colors, which can be older than what it shows now
            await self.coordinator.async_request_refresh()
            return
        elif power:
            colors = self._bare_turn_on_colors()
        write = (
            self.entity_description.turn_on_fn
            if power
            else self.entity_description.turn_off_fn
        )
        try:
            await write(self.device, colors, duration)
        except LifxError as err:
            raise device_error(err) from err
        await self.coordinator.async_request_refresh()

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the component on."""
        await self._async_apply(kwargs, power=True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the component off."""
        await self._async_apply(kwargs, power=False)

    async def set_state(self, **kwargs: Any) -> None:
        """Carry out lifx.set_state on the component as far as it can."""
        if ATTR_INFRARED in kwargs:
            self.raise_no_infrared()
        if (effect := kwargs.pop(ATTR_EFFECT, None)) is not None:
            await self._async_forward_effect(effect)
            return
        # Resolved here so a step counts towards whether anything was
        # requested; _async_apply's own resolve then has nothing left to do
        resolve_brightness_step(
            kwargs, self.brightness if self.is_on and self.brightness else 0
        )
        if (power := kwargs.pop(ATTR_POWER, None)) is None:
            if not self.is_on and not requested(parse_hsbk_changes(**kwargs)):
                return
            # Without a power change, a color set while off is kept for later
            power = self.is_on
        await self._async_apply(kwargs, power=power)

    async def _async_forward_effect(self, effect: str) -> None:
        """Run a firmware effect on the whole device, through its main light."""
        if effect not in COMPONENT_FORWARDED_EFFECTS:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="component_software_effect",
                translation_placeholders={
                    "entity_id": self.entity_id,
                    "effect": effect,
                },
            )
        entity_id = er.async_get(self.hass).async_get_entity_id(
            Platform.LIGHT, DOMAIN, self.coordinator.serial_number
        )
        assert entity_id is not None
        await self.hass.services.async_call(
            DOMAIN,
            effect,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
            context=self._context,
        )
