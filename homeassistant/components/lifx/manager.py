"""Support for LIFX lights."""

import asyncio
from collections.abc import Callable
from datetime import timedelta
from typing import TYPE_CHECKING, Any

import aiolifx_effects
from aiolifx_themes.painter import ThemePainter
from aiolifx_themes.themes import Theme, ThemeLibrary

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_BRIGHTNESS_PCT,
    ATTR_TRANSITION,
)
from homeassistant.const import ATTR_MODE
from homeassistant.core import HomeAssistant, callback

from .const import (
    ATTR_CHANGE,
    ATTR_CLOUD_SATURATION_MAX,
    ATTR_CLOUD_SATURATION_MIN,
    ATTR_CYCLES,
    ATTR_DIRECTION,
    ATTR_PALETTE,
    ATTR_PERIOD,
    ATTR_POWER_ON,
    ATTR_SATURATION_MAX,
    ATTR_SATURATION_MIN,
    ATTR_SKY_TYPE,
    ATTR_SPEED,
    ATTR_SPREAD,
    ATTR_THEME,
    SERVICE_EFFECT_COLORLOOP,
    SERVICE_EFFECT_FLAME,
    SERVICE_EFFECT_MORPH,
    SERVICE_EFFECT_MOVE,
    SERVICE_EFFECT_PULSE,
    SERVICE_EFFECT_SKY,
    SERVICE_EFFECT_STOP,
    SERVICE_PAINT_THEME,
)
from .coordinator import LIFXUpdateCoordinator
from .util import convert_8_to_16, find_hsbk

if TYPE_CHECKING:
    from aiolifx.aiolifx import Light

SCAN_INTERVAL = timedelta(seconds=10)

EFFECT_FLAME = "FLAME"
EFFECT_MORPH = "MORPH"
EFFECT_MOVE = "MOVE"
EFFECT_OFF = "OFF"
EFFECT_SKY = "SKY"

EFFECT_FLAME_DEFAULT_SPEED = 3

EFFECT_MORPH_DEFAULT_SPEED = 3
EFFECT_MORPH_DEFAULT_THEME = "exciting"

EFFECT_MOVE_DEFAULT_SPEED = 3
EFFECT_MOVE_DEFAULT_DIRECTION = "right"
EFFECT_SKY_DEFAULT_SPEED = 50
EFFECT_SKY_DEFAULT_SKY_TYPE = "Clouds"
EFFECT_SKY_DEFAULT_CLOUD_SATURATION_MIN = 50
EFFECT_SKY_DEFAULT_CLOUD_SATURATION_MAX = 180

PAINT_THEME_DEFAULT_TRANSITION = 1


class LIFXManager:
    """Representation of all known LIFX entities."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the manager."""
        self.hass = hass
        self.effects_conductor = aiolifx_effects.Conductor(hass.loop)
        self.entity_id_to_coordinator: dict[str, LIFXUpdateCoordinator] = {}

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

    @staticmethod
    def build_theme(theme_name: str = "exciting", palette: list | None = None) -> Theme:
        """Either return the predefined theme or build one from the palette."""
        if palette is None:
            return ThemeLibrary().get_theme(theme_name)

        theme = Theme()
        for hsbk in palette:
            theme.add_hsbk(hsbk[0], hsbk[1], hsbk[2], hsbk[3])
        return theme

    async def _start_effect_flame(
        self,
        bulbs: list[Light],
        coordinators: list[LIFXUpdateCoordinator],
        **kwargs: Any,
    ) -> None:
        """Start the firmware-based Flame effect."""

        await asyncio.gather(
            *(
                coordinator.async_set_matrix_effect(
                    effect=EFFECT_FLAME,
                    speed=kwargs.get(ATTR_SPEED, EFFECT_FLAME_DEFAULT_SPEED),
                    power_on=kwargs.get(ATTR_POWER_ON, True),
                )
                for coordinator in coordinators
            )
        )

    async def _start_paint_theme(
        self,
        bulbs: list[Light],
        coordinators: list[LIFXUpdateCoordinator],
        **kwargs: Any,
    ) -> None:
        """Paint a theme across one or more LIFX bulbs."""
        theme_name = kwargs.get(ATTR_THEME, "exciting")
        palette = kwargs.get(ATTR_PALETTE)

        theme = self.build_theme(theme_name, palette)

        await ThemePainter(self.hass.loop).paint(
            theme,
            bulbs,
            duration=kwargs.get(ATTR_TRANSITION, PAINT_THEME_DEFAULT_TRANSITION),
            power_on=kwargs.get(ATTR_POWER_ON, True),
        )

    async def _start_effect_morph(
        self,
        bulbs: list[Light],
        coordinators: list[LIFXUpdateCoordinator],
        **kwargs: Any,
    ) -> None:
        """Start the firmware-based Morph effect."""
        theme_name = kwargs.get(ATTR_THEME, "exciting")
        palette = kwargs.get(ATTR_PALETTE)

        theme = self.build_theme(theme_name, palette)

        await asyncio.gather(
            *(
                coordinator.async_set_matrix_effect(
                    effect=EFFECT_MORPH,
                    speed=kwargs.get(ATTR_SPEED, EFFECT_MORPH_DEFAULT_SPEED),
                    palette=theme.colors,
                    power_on=kwargs.get(ATTR_POWER_ON, True),
                )
                for coordinator in coordinators
            )
        )

    async def _start_effect_move(
        self,
        bulbs: list[Light],
        coordinators: list[LIFXUpdateCoordinator],
        **kwargs: Any,
    ) -> None:
        """Start the firmware-based Move effect."""
        await asyncio.gather(
            *(
                coordinator.async_set_multizone_effect(
                    effect=EFFECT_MOVE,
                    speed=kwargs.get(ATTR_SPEED, EFFECT_MOVE_DEFAULT_SPEED),
                    direction=kwargs.get(ATTR_DIRECTION, EFFECT_MOVE_DEFAULT_DIRECTION),
                    theme_name=kwargs.get(ATTR_THEME),
                    power_on=kwargs.get(ATTR_POWER_ON, False),
                )
                for coordinator in coordinators
            )
        )

    async def _start_effect_pulse(
        self,
        bulbs: list[Light],
        coordinators: list[LIFXUpdateCoordinator],
        **kwargs: Any,
    ) -> None:
        """Start the software-based Pulse effect."""
        effect = aiolifx_effects.EffectPulse(
            power_on=bool(kwargs.get(ATTR_POWER_ON)),
            period=kwargs.get(ATTR_PERIOD),
            cycles=kwargs.get(ATTR_CYCLES),
            mode=kwargs.get(ATTR_MODE),
            hsbk=find_hsbk(self.hass, **kwargs),
        )
        await self.effects_conductor.start(effect, bulbs)

    async def _start_effect_colorloop(
        self,
        bulbs: list[Light],
        coordinators: list[LIFXUpdateCoordinator],
        **kwargs: Any,
    ) -> None:
        """Start the software based Color Loop effect."""
        brightness = None
        saturation_max = None
        saturation_min = None

        if ATTR_BRIGHTNESS in kwargs:
            brightness = convert_8_to_16(kwargs[ATTR_BRIGHTNESS])
        elif ATTR_BRIGHTNESS_PCT in kwargs:
            brightness = convert_8_to_16(round(255 * kwargs[ATTR_BRIGHTNESS_PCT] / 100))

        if ATTR_SATURATION_MAX in kwargs:
            saturation_max = int(kwargs[ATTR_SATURATION_MAX] / 100 * 65535)

        if ATTR_SATURATION_MIN in kwargs:
            saturation_min = int(kwargs[ATTR_SATURATION_MIN] / 100 * 65535)

        effect = aiolifx_effects.EffectColorloop(
            power_on=bool(kwargs.get(ATTR_POWER_ON)),
            period=kwargs.get(ATTR_PERIOD),
            change=kwargs.get(ATTR_CHANGE),
            spread=kwargs.get(ATTR_SPREAD),
            transition=kwargs.get(ATTR_TRANSITION),
            brightness=brightness,
            saturation_max=saturation_max,
            saturation_min=saturation_min,
        )
        await self.effects_conductor.start(effect, bulbs)

    async def _start_effect_sky(
        self,
        bulbs: list[Light],
        coordinators: list[LIFXUpdateCoordinator],
        **kwargs: Any,
    ) -> None:
        """Start the firmware-based Sky effect."""
        palette = kwargs.get(ATTR_PALETTE)
        theme = Theme()
        if palette is not None:
            for hsbk in palette:
                theme.add_hsbk(hsbk[0], hsbk[1], hsbk[2], hsbk[3])

        speed = kwargs.get(ATTR_SPEED, EFFECT_SKY_DEFAULT_SPEED)
        sky_type = kwargs.get(ATTR_SKY_TYPE, EFFECT_SKY_DEFAULT_SKY_TYPE)

        cloud_saturation_min = kwargs.get(
            ATTR_CLOUD_SATURATION_MIN,
            EFFECT_SKY_DEFAULT_CLOUD_SATURATION_MIN,
        )
        cloud_saturation_max = kwargs.get(
            ATTR_CLOUD_SATURATION_MAX,
            EFFECT_SKY_DEFAULT_CLOUD_SATURATION_MAX,
        )

        await asyncio.gather(
            *(
                coordinator.async_set_matrix_effect(
                    effect=EFFECT_SKY,
                    speed=speed,
                    sky_type=sky_type,
                    cloud_saturation_min=cloud_saturation_min,
                    cloud_saturation_max=cloud_saturation_max,
                    palette=theme.colors,
                )
                for coordinator in coordinators
            )
        )

    async def _start_effect_stop(
        self,
        bulbs: list[Light],
        coordinators: list[LIFXUpdateCoordinator],
        **kwargs: Any,
    ) -> None:
        """Stop any running software or firmware effect."""
        await self.effects_conductor.stop(bulbs)

        for coordinator in coordinators:
            await coordinator.async_set_matrix_effect(effect=EFFECT_OFF, power_on=False)
            await coordinator.async_set_multizone_effect(
                effect=EFFECT_OFF, power_on=False
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

    async def start_effect(
        self, entity_ids: set[str], service: str, **kwargs: Any
    ) -> None:
        """Start a light effect on entities."""

        coordinators: list[LIFXUpdateCoordinator] = []
        bulbs: list[Light] = []

        coordinators = [
            coordinator
            for entity_id, coordinator in self.entity_id_to_coordinator.items()
            if entity_id in entity_ids
        ]
        bulbs = [coordinator.device for coordinator in coordinators]
        if start_effect_func := self._effect_dispatch.get(service):
            await start_effect_func(self, bulbs, coordinators, **kwargs)
