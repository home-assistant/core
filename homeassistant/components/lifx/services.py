"""Support for LIFX services."""

from typing import TYPE_CHECKING

from lifx import ThemeLibrary
import probatio

from homeassistant.components.light import (
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    ATTR_XY_COLOR,
    COLOR_GROUP,
    DOMAIN as LIGHT_DOMAIN,
    LIGHT_TURN_ON_SCHEMA,
    VALID_BRIGHTNESS,
    VALID_BRIGHTNESS_PCT,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_register_platform_entity_service
from homeassistant.helpers.target import (
    TargetSelection,
    async_extract_referenced_entity_ids,
)
from homeassistant.helpers.typing import VolDictType

from .const import DATA_LIFX_MANAGER, DOMAIN, LIFXService, LIFXServiceArgument

if TYPE_CHECKING:
    from .manager import LIFXManager

BRIGHTNESS_GROUP = "brightness"

LIFX_SET_STATE_SCHEMA: VolDictType = {
    **LIGHT_TURN_ON_SCHEMA,
    LIFXServiceArgument.INFRARED: probatio.All(
        probatio.Coerce(int), probatio.Clamp(min=0, max=255)
    ),
    LIFXServiceArgument.ZONES: probatio.All(probatio.EnsureList(), [cv.positive_int]),
    LIFXServiceArgument.POWER: cv.boolean,
}

LIFX_SET_HEV_CYCLE_STATE_SCHEMA: VolDictType = {
    probatio.Required(LIFXServiceArgument.POWER): cv.boolean,
    LIFXServiceArgument.DURATION: probatio.All(
        probatio.Coerce(float), probatio.Clamp(min=0, max=86400)
    ),
}


# The firmware effect palette is carried in a fixed sixteen color field
EFFECT_PALETTE_MAX = 16
EFFECT_PALETTE_MIN = 2
# The Sky effect palette maps onto six named slots rather than the full field
EFFECT_SKY_PALETTE_MAX = 6

EFFECT_MOVE_DIRECTION_LEFT = "left"
EFFECT_MOVE_DIRECTION_RIGHT = "right"

EFFECT_MOVE_DIRECTIONS = [EFFECT_MOVE_DIRECTION_LEFT, EFFECT_MOVE_DIRECTION_RIGHT]

EFFECT_SKY_SKY_TYPES = ["Sunrise", "Sunset", "Clouds"]

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
    probatio.Optional(LIFXServiceArgument.POWER_ON, default=True): cv.boolean,
}

LIFX_EFFECT_PULSE_SCHEMA = cv.make_entity_service_schema(
    {
        **LIFX_EFFECT_SCHEMA,
        # A brightness of zero would pulse to black
        probatio.Exclusive(
            LIFXServiceArgument.BRIGHTNESS, BRIGHTNESS_GROUP
        ): probatio.All(VALID_BRIGHTNESS, probatio.Clamp(min=1)),
        probatio.Exclusive(
            LIFXServiceArgument.BRIGHTNESS_PCT, BRIGHTNESS_GROUP
        ): probatio.All(VALID_BRIGHTNESS_PCT, probatio.Clamp(min=1)),
        probatio.Exclusive(LIFXServiceArgument.COLOR_NAME, COLOR_GROUP): cv.string,
        probatio.Exclusive(LIFXServiceArgument.RGB_COLOR, COLOR_GROUP): probatio.All(
            probatio.Coerce(tuple), probatio.ExactSequence((cv.byte, cv.byte, cv.byte))
        ),
        probatio.Exclusive(ATTR_XY_COLOR, COLOR_GROUP): probatio.All(
            probatio.Coerce(tuple),
            probatio.ExactSequence((cv.small_float, cv.small_float)),
        ),
        probatio.Exclusive(ATTR_HS_COLOR, COLOR_GROUP): probatio.All(
            probatio.Coerce(tuple),
            probatio.ExactSequence(
                (
                    probatio.All(
                        probatio.Coerce(float), probatio.Range(min=0, max=360)
                    ),
                    probatio.All(probatio.Coerce(float), probatio.Percentage()),
                )
            ),
        ),
        probatio.Exclusive(ATTR_COLOR_TEMP_KELVIN, COLOR_GROUP): probatio.All(
            probatio.Coerce(int), probatio.Range(min=1500, max=9000)
        ),
        LIFXServiceArgument.PERIOD: probatio.All(
            probatio.Coerce(float), probatio.Range(min=0.05)
        ),
        LIFXServiceArgument.CYCLES: probatio.All(
            probatio.Coerce(float), probatio.Range(min=1)
        ),
        LIFXServiceArgument.MODE: probatio.In(PULSE_MODES),
    }
)

LIFX_EFFECT_COLORLOOP_SCHEMA = cv.make_entity_service_schema(
    {
        **LIFX_EFFECT_SCHEMA,
        probatio.Exclusive(
            LIFXServiceArgument.BRIGHTNESS, BRIGHTNESS_GROUP
        ): VALID_BRIGHTNESS,
        probatio.Exclusive(
            LIFXServiceArgument.BRIGHTNESS_PCT, BRIGHTNESS_GROUP
        ): VALID_BRIGHTNESS_PCT,
        # A saturation of zero switches the bulb to color temperature mode
        LIFXServiceArgument.SATURATION_MAX: probatio.All(
            probatio.Coerce(int), probatio.Clamp(min=1, max=100)
        ),
        LIFXServiceArgument.SATURATION_MIN: probatio.All(
            probatio.Coerce(int), probatio.Clamp(min=1, max=100)
        ),
        LIFXServiceArgument.PERIOD: probatio.All(
            probatio.Coerce(float), probatio.Clamp(min=0.05)
        ),
        # The library refuses a change of 0 or of 180 degrees and more
        LIFXServiceArgument.CHANGE: probatio.All(
            probatio.Coerce(float), probatio.Clamp(min=1, max=179)
        ),
        LIFXServiceArgument.SPREAD: probatio.All(
            probatio.Coerce(float), probatio.Clamp(min=0, max=360)
        ),
        LIFXServiceArgument.TRANSITION: cv.positive_float,
    }
)

LIFX_EFFECT_STOP_SCHEMA = cv.make_entity_service_schema({})

LIFX_EFFECT_FLAME_SCHEMA = cv.make_entity_service_schema(
    {
        **LIFX_EFFECT_SCHEMA,
        LIFXServiceArgument.SPEED: probatio.All(
            probatio.Coerce(int), probatio.Clamp(min=1, max=25)
        ),
    }
)

HSBK_SCHEMA = probatio.All(
    probatio.Coerce(tuple),
    probatio.ExactSequence(
        (
            probatio.All(probatio.Coerce(float), probatio.Range(min=0, max=360)),
            probatio.All(probatio.Coerce(float), probatio.Percentage()),
            probatio.All(probatio.Coerce(float), probatio.Clamp(min=0, max=100)),
            probatio.All(probatio.Coerce(int), probatio.Clamp(min=1500, max=9000)),
        )
    ),
)

LIFX_EFFECT_MORPH_SCHEMA = cv.make_entity_service_schema(
    {
        **LIFX_EFFECT_SCHEMA,
        LIFXServiceArgument.SPEED: probatio.All(
            probatio.Coerce(int), probatio.Clamp(min=1, max=25)
        ),
        probatio.Exclusive(LIFXServiceArgument.THEME, COLOR_GROUP): probatio.In(
            ThemeLibrary.get_available_themes()
        ),
        probatio.Exclusive(LIFXServiceArgument.PALETTE, COLOR_GROUP): probatio.All(
            probatio.EnsureList(),
            [HSBK_SCHEMA],
            probatio.Length(min=EFFECT_PALETTE_MIN, max=EFFECT_PALETTE_MAX),
        ),
    }
)

LIFX_EFFECT_MOVE_SCHEMA = cv.make_entity_service_schema(
    {
        **LIFX_EFFECT_SCHEMA,
        LIFXServiceArgument.SPEED: probatio.All(
            probatio.Coerce(float), probatio.Clamp(min=0.1, max=60)
        ),
        LIFXServiceArgument.DIRECTION: probatio.In(EFFECT_MOVE_DIRECTIONS),
        probatio.Optional(LIFXServiceArgument.THEME): probatio.In(
            ThemeLibrary.get_available_themes()
        ),
    }
)

LIFX_EFFECT_COLORSWEEP_SCHEMA = cv.make_entity_service_schema(
    {
        **LIFX_EFFECT_SCHEMA,
        LIFXServiceArgument.SPEED: probatio.All(
            probatio.Coerce(int), probatio.Clamp(min=0, max=25)
        ),
        LIFXServiceArgument.DURATION: probatio.All(
            probatio.Coerce(int), probatio.Clamp(min=0, max=3600)
        ),
        LIFXServiceArgument.PALETTE: probatio.All(
            probatio.EnsureList(),
            [HSBK_SCHEMA],
            probatio.Length(min=EFFECT_PALETTE_MIN, max=EFFECT_PALETTE_MAX),
        ),
    }
)

LIFX_EFFECT_SKY_SCHEMA = cv.make_entity_service_schema(
    {
        **LIFX_EFFECT_SCHEMA,
        LIFXServiceArgument.SPEED: probatio.All(
            probatio.Coerce(int), probatio.Clamp(min=0, max=86400)
        ),
        LIFXServiceArgument.DURATION: probatio.All(
            probatio.Coerce(int), probatio.Clamp(min=0, max=86400)
        ),
        LIFXServiceArgument.SKY_TYPE: probatio.In(EFFECT_SKY_SKY_TYPES),
        LIFXServiceArgument.CLOUD_SATURATION_MIN: probatio.All(
            probatio.Coerce(int), probatio.Clamp(min=0, max=255)
        ),
        LIFXServiceArgument.CLOUD_SATURATION_MAX: probatio.All(
            probatio.Coerce(int), probatio.Clamp(min=0, max=255)
        ),
        LIFXServiceArgument.PALETTE: probatio.All(
            probatio.EnsureList(),
            [HSBK_SCHEMA],
            probatio.Length(min=1, max=EFFECT_SKY_PALETTE_MAX),
        ),
    }
)

LIFX_PAINT_THEME_SCHEMA = cv.make_entity_service_schema(
    {
        **LIFX_EFFECT_SCHEMA,
        LIFXServiceArgument.TRANSITION: probatio.All(
            probatio.Coerce(int), probatio.Clamp(min=0, max=3600)
        ),
        probatio.Exclusive(LIFXServiceArgument.THEME, COLOR_GROUP): probatio.In(
            ThemeLibrary.get_available_themes()
        ),
        probatio.Exclusive(LIFXServiceArgument.PALETTE, COLOR_GROUP): probatio.All(
            probatio.EnsureList(),
            [HSBK_SCHEMA],
            probatio.Length(min=EFFECT_PALETTE_MIN, max=EFFECT_PALETTE_MAX),
        ),
    }
)

SERVICES_SCHEMA = {
    LIFXService.EFFECT_COLORSWEEP: LIFX_EFFECT_COLORSWEEP_SCHEMA,
    LIFXService.EFFECT_COLORLOOP: LIFX_EFFECT_COLORLOOP_SCHEMA,
    LIFXService.EFFECT_FLAME: LIFX_EFFECT_FLAME_SCHEMA,
    LIFXService.EFFECT_MORPH: LIFX_EFFECT_MORPH_SCHEMA,
    LIFXService.EFFECT_MOVE: LIFX_EFFECT_MOVE_SCHEMA,
    LIFXService.EFFECT_PULSE: LIFX_EFFECT_PULSE_SCHEMA,
    LIFXService.EFFECT_SKY: LIFX_EFFECT_SKY_SCHEMA,
    LIFXService.EFFECT_STOP: LIFX_EFFECT_STOP_SCHEMA,
    LIFXService.PAINT_THEME: LIFX_PAINT_THEME_SCHEMA,
}


def _get_manager(service: ServiceCall) -> LIFXManager:
    """Return the LIFX manager, raising a user-facing error if no entry is loaded."""
    hass = service.hass
    if not hass.config_entries.async_loaded_entries(DOMAIN):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="not_loaded",
        )
    return hass.data[DATA_LIFX_MANAGER]


async def _async_start_effect(service: ServiceCall) -> None:
    """Apply a service, i.e. start an effect."""
    manager = _get_manager(service)
    referenced = async_extract_referenced_entity_ids(
        service.hass, TargetSelection(service.data)
    )
    all_referenced = referenced.referenced | referenced.indirectly_referenced
    await manager.start_effect(
        all_referenced,
        service,
        # An area or label that holds no usable LIFX light is a sweep that
        # caught nothing, not the mistake naming one directly is
        strict=bool(referenced.referenced),
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the LIFX actions."""
    async_register_platform_entity_service(
        hass,
        DOMAIN,
        LIFXService.SET_STATE,
        entity_domain=LIGHT_DOMAIN,
        schema=LIFX_SET_STATE_SCHEMA,
        func="set_state",
    )
    async_register_platform_entity_service(
        hass,
        DOMAIN,
        LIFXService.SET_HEV_CYCLE_STATE,
        entity_domain=LIGHT_DOMAIN,
        schema=LIFX_SET_HEV_CYCLE_STATE_SCHEMA,
        func="set_hev_cycle_state",
    )
    for service, schema in SERVICES_SCHEMA.items():
        hass.services.async_register(
            DOMAIN, service, _async_start_effect, schema=schema
        )
