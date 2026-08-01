"""Support for LIFX lights."""

import asyncio
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from lifx import (
    HSBK,
    Conductor,
    Device,
    Direction,
    EffectColorloop,
    EffectPulse,
    FirmwareEffect,
    LifxError,
    Light,
    MatrixLight,
    MultiZoneEffect,
    MultiZoneLight,
    Theme,
    ThemeLibrary,
    TileEffectSkyType,
)
import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_BRIGHTNESS_PCT,
    ATTR_COLOR_NAME,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    ATTR_RGB_COLOR,
    ATTR_TRANSITION,
    ATTR_XY_COLOR,
    COLOR_GROUP,
    VALID_BRIGHTNESS,
    VALID_BRIGHTNESS_PCT,
)
from homeassistant.const import ATTR_MODE
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.target import (
    TargetSelection,
    async_extract_referenced_entity_ids,
)

from .const import ATTR_THEME, DOMAIN
from .coordinator import LIFXUpdateCoordinator
from .util import device_error, find_hsbk

SERVICE_EFFECT_COLORLOOP = "effect_colorloop"
SERVICE_EFFECT_FLAME = "effect_flame"
SERVICE_EFFECT_MORPH = "effect_morph"
SERVICE_EFFECT_MOVE = "effect_move"
SERVICE_EFFECT_PULSE = "effect_pulse"
SERVICE_EFFECT_SKY = "effect_sky"
SERVICE_EFFECT_STOP = "effect_stop"
SERVICE_PAINT_THEME = "paint_theme"

ATTR_CHANGE = "change"
ATTR_CLOUD_SATURATION_MIN = "cloud_saturation_min"
ATTR_CLOUD_SATURATION_MAX = "cloud_saturation_max"
ATTR_CYCLES = "cycles"
ATTR_DIRECTION = "direction"
ATTR_PALETTE = "palette"
ATTR_PERIOD = "period"
ATTR_POWER_ON = "power_on"
ATTR_SATURATION_MAX = "saturation_max"
ATTR_SATURATION_MIN = "saturation_min"
ATTR_SKY_TYPE = "sky_type"
ATTR_SPEED = "speed"
ATTR_SPREAD = "spread"

# The firmware effect palette is carried in a fixed sixteen color field
EFFECT_PALETTE_MAX = 16

EFFECT_FLAME_DEFAULT_SPEED = 3

EFFECT_MORPH_DEFAULT_SPEED = 3
EFFECT_MORPH_DEFAULT_THEME = "exciting"

EFFECT_MOVE_DEFAULT_SPEED = 3
EFFECT_MOVE_DEFAULT_DIRECTION = "right"
EFFECT_MOVE_DIRECTION_RIGHT = "right"
EFFECT_MOVE_DIRECTION_LEFT = "left"

EFFECT_MOVE_DIRECTIONS = [EFFECT_MOVE_DIRECTION_LEFT, EFFECT_MOVE_DIRECTION_RIGHT]

EFFECT_MOVE_DIRECTION = {
    EFFECT_MOVE_DIRECTION_LEFT: Direction.FORWARD,
    EFFECT_MOVE_DIRECTION_RIGHT: Direction.REVERSED,
}

EFFECT_SKY_DEFAULT_SPEED = 50
EFFECT_SKY_DEFAULT_SKY_TYPE = "Clouds"
EFFECT_SKY_DEFAULT_CLOUD_SATURATION_MIN = 50
EFFECT_SKY_DEFAULT_CLOUD_SATURATION_MAX = 180

EFFECT_SKY_SKY_TYPES = ["Sunrise", "Sunset", "Clouds"]
EFFECT_SKY_TYPE = {
    "Sunrise": TileEffectSkyType.SUNRISE,
    "Sunset": TileEffectSkyType.SUNSET,
    "Clouds": TileEffectSkyType.CLOUDS,
}


PAINT_THEME_DEFAULT_TRANSITION = 1

PULSE_MODE_BLINK = "blink"
PULSE_MODE_BREATHE = "breathe"
PULSE_MODE_PING = "ping"
PULSE_MODE_SOLID = "solid"
PULSE_MODE_STROBE = "strobe"

PULSE_MODES = [
    PULSE_MODE_BLINK,
    PULSE_MODE_BREATHE,
    PULSE_MODE_PING,
    PULSE_MODE_STROBE,
    PULSE_MODE_SOLID,
]

LIFX_EFFECT_SCHEMA = {
    vol.Optional(ATTR_POWER_ON, default=True): cv.boolean,
}

LIFX_EFFECT_PULSE_SCHEMA = cv.make_entity_service_schema(
    {
        **LIFX_EFFECT_SCHEMA,
        vol.Exclusive(ATTR_BRIGHTNESS, ATTR_BRIGHTNESS): VALID_BRIGHTNESS,
        vol.Exclusive(ATTR_BRIGHTNESS_PCT, ATTR_BRIGHTNESS): VALID_BRIGHTNESS_PCT,
        vol.Exclusive(ATTR_COLOR_NAME, COLOR_GROUP): cv.string,
        vol.Exclusive(ATTR_RGB_COLOR, COLOR_GROUP): vol.All(
            vol.Coerce(tuple), vol.ExactSequence((cv.byte, cv.byte, cv.byte))
        ),
        vol.Exclusive(ATTR_XY_COLOR, COLOR_GROUP): vol.All(
            vol.Coerce(tuple), vol.ExactSequence((cv.small_float, cv.small_float))
        ),
        vol.Exclusive(ATTR_HS_COLOR, COLOR_GROUP): vol.All(
            vol.Coerce(tuple),
            vol.ExactSequence(
                (
                    vol.All(vol.Coerce(float), vol.Range(min=0, max=360)),
                    vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
                )
            ),
        ),
        vol.Exclusive(ATTR_COLOR_TEMP_KELVIN, COLOR_GROUP): vol.All(
            vol.Coerce(int), vol.Range(min=1500, max=9000)
        ),
        ATTR_PERIOD: vol.All(vol.Coerce(float), vol.Range(min=0.05)),
        ATTR_CYCLES: vol.All(vol.Coerce(float), vol.Range(min=1)),
        ATTR_MODE: vol.In(PULSE_MODES),
    }
)

LIFX_EFFECT_COLORLOOP_SCHEMA = cv.make_entity_service_schema(
    {
        **LIFX_EFFECT_SCHEMA,
        vol.Exclusive(ATTR_BRIGHTNESS, ATTR_BRIGHTNESS): VALID_BRIGHTNESS,
        vol.Exclusive(ATTR_BRIGHTNESS_PCT, ATTR_BRIGHTNESS): VALID_BRIGHTNESS_PCT,
        ATTR_SATURATION_MAX: vol.All(vol.Coerce(int), vol.Clamp(min=0, max=100)),
        ATTR_SATURATION_MIN: vol.All(vol.Coerce(int), vol.Clamp(min=0, max=100)),
        ATTR_PERIOD: vol.All(vol.Coerce(float), vol.Clamp(min=0.05)),
        ATTR_CHANGE: vol.All(vol.Coerce(float), vol.Clamp(min=0, max=360)),
        ATTR_SPREAD: vol.All(vol.Coerce(float), vol.Clamp(min=0, max=360)),
        ATTR_TRANSITION: cv.positive_float,
    }
)

LIFX_EFFECT_STOP_SCHEMA = cv.make_entity_service_schema({})

LIFX_EFFECT_FLAME_SCHEMA = cv.make_entity_service_schema(
    {
        **LIFX_EFFECT_SCHEMA,
        ATTR_SPEED: vol.All(vol.Coerce(int), vol.Clamp(min=1, max=25)),
    }
)

HSBK_SCHEMA = vol.All(
    vol.Coerce(tuple),
    vol.ExactSequence(
        (
            vol.All(vol.Coerce(float), vol.Range(min=0, max=360)),
            vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
            vol.All(vol.Coerce(float), vol.Clamp(min=0, max=100)),
            vol.All(vol.Coerce(int), vol.Clamp(min=1500, max=9000)),
        )
    ),
)

LIFX_EFFECT_MORPH_SCHEMA = cv.make_entity_service_schema(
    {
        **LIFX_EFFECT_SCHEMA,
        ATTR_SPEED: vol.All(vol.Coerce(int), vol.Clamp(min=1, max=25)),
        vol.Exclusive(ATTR_THEME, COLOR_GROUP): vol.In(
            ThemeLibrary.get_available_themes()
        ),
        vol.Exclusive(ATTR_PALETTE, COLOR_GROUP): vol.All(
            cv.ensure_list, [HSBK_SCHEMA], vol.Length(min=1, max=EFFECT_PALETTE_MAX)
        ),
    }
)

LIFX_EFFECT_MOVE_SCHEMA = cv.make_entity_service_schema(
    {
        **LIFX_EFFECT_SCHEMA,
        ATTR_SPEED: vol.All(vol.Coerce(float), vol.Clamp(min=0.1, max=60)),
        ATTR_DIRECTION: vol.In(EFFECT_MOVE_DIRECTIONS),
        vol.Optional(ATTR_THEME): vol.In(ThemeLibrary.get_available_themes()),
    }
)

LIFX_EFFECT_SKY_SCHEMA = cv.make_entity_service_schema(
    {
        **LIFX_EFFECT_SCHEMA,
        ATTR_SPEED: vol.All(vol.Coerce(int), vol.Clamp(min=1, max=86400)),
        ATTR_SKY_TYPE: vol.In(EFFECT_SKY_SKY_TYPES),
        ATTR_CLOUD_SATURATION_MIN: vol.All(vol.Coerce(int), vol.Clamp(min=0, max=255)),
        ATTR_CLOUD_SATURATION_MAX: vol.All(vol.Coerce(int), vol.Clamp(min=0, max=255)),
        ATTR_PALETTE: vol.All(
            cv.ensure_list, [HSBK_SCHEMA], vol.Length(min=1, max=EFFECT_PALETTE_MAX)
        ),
    }
)

LIFX_PAINT_THEME_SCHEMA = cv.make_entity_service_schema(
    {
        **LIFX_EFFECT_SCHEMA,
        ATTR_TRANSITION: vol.All(vol.Coerce(int), vol.Clamp(min=1, max=3600)),
        vol.Exclusive(ATTR_THEME, COLOR_GROUP): vol.In(
            ThemeLibrary.get_available_themes()
        ),
        vol.Exclusive(ATTR_PALETTE, COLOR_GROUP): vol.All(
            cv.ensure_list, [HSBK_SCHEMA], vol.Length(min=1)
        ),
    }
)

SERVICES_SCHEMA = {
    SERVICE_EFFECT_COLORLOOP: LIFX_EFFECT_COLORLOOP_SCHEMA,
    SERVICE_EFFECT_FLAME: LIFX_EFFECT_FLAME_SCHEMA,
    SERVICE_EFFECT_MORPH: LIFX_EFFECT_MORPH_SCHEMA,
    SERVICE_EFFECT_MOVE: LIFX_EFFECT_MOVE_SCHEMA,
    SERVICE_EFFECT_PULSE: LIFX_EFFECT_PULSE_SCHEMA,
    SERVICE_EFFECT_SKY: LIFX_EFFECT_SKY_SCHEMA,
    SERVICE_EFFECT_STOP: LIFX_EFFECT_STOP_SCHEMA,
    SERVICE_PAINT_THEME: LIFX_PAINT_THEME_SCHEMA,
}


class LIFXManager:
    """Representation of all known LIFX entities."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the manager."""
        self.hass = hass
        self.effects_conductor = Conductor()
        self.entity_id_to_coordinator: dict[str, LIFXUpdateCoordinator] = {}

    async def async_stop_effects(self, device: Device) -> None:
        """Stop any software effect still running on a device."""
        if isinstance(device, Light):
            await self.effects_conductor.stop([device])

    @callback
    def async_register_entity(
        self, entity_id: str, coordinator: LIFXUpdateCoordinator
    ) -> Callable[[], None]:
        """Register an entity to the config entry id."""
        self.entity_id_to_coordinator[entity_id] = coordinator

        @callback
        def unregister_entity() -> None:
            """Unregister entity when it is being destroyed."""
            self.entity_id_to_coordinator.pop(entity_id)

        return unregister_entity

    @callback
    def async_setup(self) -> None:
        """Register the LIFX effects as hass service calls."""

        async def service_handler(service: ServiceCall) -> None:
            """Apply a service, i.e. start an effect."""
            referenced = async_extract_referenced_entity_ids(
                self.hass, TargetSelection(service.data)
            )
            all_referenced = referenced.referenced | referenced.indirectly_referenced
            await self.start_effect(
                all_referenced,
                service,
                # An area or label that holds no usable LIFX light is a sweep
                # that caught nothing, not the mistake naming one directly is
                strict=bool(referenced.referenced),
            )

        for service, schema in SERVICES_SCHEMA.items():
            self.hass.services.async_register(
                DOMAIN, service, service_handler, schema=schema
            )

    @staticmethod
    def _build_palette(
        palette: list[tuple[float, float, float, int]] | None,
    ) -> list[HSBK]:
        """Build a public-unit palette from Home Assistant values."""
        if palette is None:
            return []
        return [
            HSBK(hue, saturation / 100, brightness / 100, kelvin)
            for hue, saturation, brightness, kelvin in palette
        ]

    @classmethod
    def build_theme(
        cls,
        theme_name: str = "exciting",
        palette: list[tuple[float, float, float, int]] | None = None,
    ) -> Theme:
        """Return a predefined theme or build one from a palette."""
        if palette is None:
            return ThemeLibrary.get(theme_name)
        return Theme(cls._build_palette(palette))

    @staticmethod
    def hsbk_from_service_data(
        device: Light, service_data: Mapping[str, object]
    ) -> HSBK | None:
        """Merge the requested color components onto a device's current color."""
        return find_hsbk(device.state.color, **service_data)

    @staticmethod
    async def _async_power_on(devices: Sequence[Light], power_on: bool) -> None:
        """Power on effect participants when requested."""
        if not power_on:
            return
        await asyncio.gather(
            *(
                device.set_power(True, duration=0.0)
                for device in devices
                if device.state.power == 0
            )
        )

    async def _start_matrix_effect(
        self,
        devices: list[Light],
        service: ServiceCall,
        effect: FirmwareEffect,
        **kwargs: Any,
    ) -> None:
        """Start a firmware effect on every matrix device in the target set."""
        compatible_devices = [
            device for device in devices if isinstance(device, MatrixLight)
        ]
        await self._async_power_on(
            compatible_devices, service.data.get(ATTR_POWER_ON, True)
        )
        await asyncio.gather(
            *(device.set_effect(effect, **kwargs) for device in compatible_devices)
        )

    async def _start_effect_flame(
        self,
        devices: list[Light],
        service: ServiceCall,
    ) -> None:
        """Start the firmware-based Flame effect."""
        await self._start_matrix_effect(
            devices,
            service,
            FirmwareEffect.FLAME,
            speed=service.data.get(ATTR_SPEED, EFFECT_FLAME_DEFAULT_SPEED),
        )

    async def _start_paint_theme(
        self,
        devices: list[Light],
        service: ServiceCall,
    ) -> None:
        """Paint a theme across one or more LIFX bulbs."""
        theme_name = service.data.get(ATTR_THEME, "exciting")
        palette = service.data.get(ATTR_PALETTE)
        theme = self.build_theme(theme_name, palette)
        power_on = service.data.get(ATTR_POWER_ON, True)
        duration = service.data.get(ATTR_TRANSITION, PAINT_THEME_DEFAULT_TRANSITION)
        await asyncio.gather(
            *(
                device.apply_theme(theme, power_on=power_on, duration=duration)
                for device in devices
            )
        )

    async def _start_effect_morph(
        self,
        devices: list[Light],
        service: ServiceCall,
    ) -> None:
        """Start the firmware-based Morph effect."""
        theme_name = service.data.get(ATTR_THEME, EFFECT_MORPH_DEFAULT_THEME)
        palette = service.data.get(ATTR_PALETTE)
        theme = self.build_theme(theme_name, palette)
        await self._start_matrix_effect(
            devices,
            service,
            FirmwareEffect.MORPH,
            speed=service.data.get(ATTR_SPEED, EFFECT_MORPH_DEFAULT_SPEED),
            palette=theme.colors,
        )

    async def _start_effect_move(
        self,
        devices: list[Light],
        service: ServiceCall,
    ) -> None:
        """Start the firmware-based Move effect."""
        compatible_devices = [
            device for device in devices if isinstance(device, MultiZoneLight)
        ]
        power_on = service.data.get(ATTR_POWER_ON, True)
        await self._async_power_on(compatible_devices, power_on)
        speed = service.data.get(ATTR_SPEED, EFFECT_MOVE_DEFAULT_SPEED)
        if theme_name := service.data.get(ATTR_THEME):
            theme = ThemeLibrary.get(theme_name)
            await asyncio.gather(
                *(
                    device.apply_theme(theme, power_on=False, duration=round(speed))
                    for device in compatible_devices
                )
            )
        direction = EFFECT_MOVE_DIRECTION[
            service.data.get(ATTR_DIRECTION, EFFECT_MOVE_DEFAULT_DIRECTION)
        ]
        effect = MultiZoneEffect(
            FirmwareEffect.MOVE,
            round(speed * 1000),
            parameters=[0, int(direction), 0, 0, 0, 0, 0, 0],
        )
        await asyncio.gather(
            *(device.set_effect(effect) for device in compatible_devices)
        )

    async def _start_effect_pulse(
        self,
        devices: list[Light],
        service: ServiceCall,
    ) -> None:
        """Start the software-based Pulse effect."""
        # Unspecified color components come from each device, so every device
        # gets its own effect
        await asyncio.gather(
            *(
                self.effects_conductor.start(
                    EffectPulse(
                        power_on=service.data.get(ATTR_POWER_ON, True),
                        mode=service.data.get(ATTR_MODE, PULSE_MODE_BLINK),
                        period=service.data.get(ATTR_PERIOD),
                        cycles=service.data.get(ATTR_CYCLES),
                        color=self.hsbk_from_service_data(device, service.data),
                    ),
                    [device],
                )
                for device in devices
            )
        )

    async def _start_effect_colorloop(
        self,
        devices: list[Light],
        service: ServiceCall,
    ) -> None:
        """Start the software based Color Loop effect."""
        brightness = None
        if ATTR_BRIGHTNESS in service.data:
            brightness = service.data[ATTR_BRIGHTNESS] / 255
        elif ATTR_BRIGHTNESS_PCT in service.data:
            brightness = service.data[ATTR_BRIGHTNESS_PCT] / 100

        saturation_min = service.data.get(ATTR_SATURATION_MIN, 80) / 100
        saturation_max = service.data.get(ATTR_SATURATION_MAX, 100) / 100
        # Only one bound has to be given, so they can arrive the wrong way around
        if saturation_min > saturation_max:
            saturation_min, saturation_max = saturation_max, saturation_min

        effect = EffectColorloop(
            power_on=service.data.get(ATTR_POWER_ON, True),
            period=service.data.get(ATTR_PERIOD, 60.0),
            change=service.data.get(ATTR_CHANGE, 20.0),
            spread=service.data.get(ATTR_SPREAD, 30.0),
            brightness=brightness,
            saturation_min=saturation_min,
            saturation_max=saturation_max,
            transition=service.data.get(ATTR_TRANSITION),
        )
        await self.effects_conductor.start(effect, devices)

    async def _start_effect_sky(
        self,
        devices: list[Light],
        service: ServiceCall,
    ) -> None:
        """Start the firmware-based Sky effect."""
        await self._start_matrix_effect(
            devices,
            service,
            FirmwareEffect.SKY,
            speed=service.data.get(ATTR_SPEED, EFFECT_SKY_DEFAULT_SPEED),
            sky_type=EFFECT_SKY_TYPE[
                service.data.get(ATTR_SKY_TYPE, EFFECT_SKY_DEFAULT_SKY_TYPE)
            ],
            cloud_saturation_min=service.data.get(
                ATTR_CLOUD_SATURATION_MIN,
                EFFECT_SKY_DEFAULT_CLOUD_SATURATION_MIN,
            ),
            cloud_saturation_max=service.data.get(
                ATTR_CLOUD_SATURATION_MAX,
                EFFECT_SKY_DEFAULT_CLOUD_SATURATION_MAX,
            ),
            # The library rejects an empty palette but accepts no palette at all
            palette=self._build_palette(service.data.get(ATTR_PALETTE)) or None,
        )

    async def _start_effect_stop(
        self,
        devices: list[Light],
        _service: ServiceCall,
    ) -> None:
        """Stop any running software or firmware effect."""
        await self.effects_conductor.stop(devices)
        await asyncio.gather(
            *(
                device.set_effect(FirmwareEffect.OFF)
                for device in devices
                if isinstance(device, MatrixLight)
            ),
            *(
                device.stop_effect()
                for device in devices
                if isinstance(device, MultiZoneLight)
            ),
        )

    _effect_dispatch = {
        SERVICE_EFFECT_COLORLOOP: _start_effect_colorloop,
        SERVICE_EFFECT_FLAME: _start_effect_flame,
        SERVICE_EFFECT_MORPH: _start_effect_morph,
        SERVICE_EFFECT_MOVE: _start_effect_move,
        SERVICE_EFFECT_PULSE: _start_effect_pulse,
        SERVICE_EFFECT_SKY: _start_effect_sky,
        SERVICE_EFFECT_STOP: _start_effect_stop,
        SERVICE_PAINT_THEME: _start_paint_theme,
    }

    # A firmware effect only runs on the devices that implement it, so a target
    # set holding none of them can do nothing at all
    _effect_requires: dict[str, tuple[type[Light], str]] = {
        SERVICE_EFFECT_FLAME: (MatrixLight, "no_matrix_target"),
        SERVICE_EFFECT_MORPH: (MatrixLight, "no_matrix_target"),
        SERVICE_EFFECT_MOVE: (MultiZoneLight, "no_multizone_target"),
        SERVICE_EFFECT_SKY: (MatrixLight, "no_matrix_target"),
    }

    async def start_effect(
        self, entity_ids: set[str], service: ServiceCall, strict: bool = True
    ) -> None:
        """Start a light effect on entities."""
        coordinators = [
            coordinator
            for entity_id, coordinator in self.entity_id_to_coordinator.items()
            if entity_id in entity_ids
        ]
        devices = [
            coordinator.device
            for coordinator in coordinators
            if isinstance(coordinator.device, Light)
        ]
        if not devices:
            if not strict:
                return
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="no_lifx_target",
                translation_placeholders={"service": service.service},
            )
        if requirement := self._effect_requires.get(service.service):
            device_type, translation_key = requirement
            if not any(isinstance(device, device_type) for device in devices):
                if not strict:
                    return
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key=translation_key,
                    translation_placeholders={"service": service.service},
                )
        if start_effect_func := self._effect_dispatch.get(service.service):
            try:
                await start_effect_func(self, devices, service)
            except LifxError as err:
                raise device_error(err) from err
            # A firmware effect is written straight to the device, so the state
            # the coordinator holds is stale until it is polled again
            await asyncio.gather(
                *(coordinator.async_request_refresh() for coordinator in coordinators)
            )
