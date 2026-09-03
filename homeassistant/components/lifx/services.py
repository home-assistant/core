"""Support for LIFX services."""

from typing import TYPE_CHECKING

from aiolifx_themes.themes import ThemeLibrary
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
    DATA_LIFX_MANAGER,
    DOMAIN,
    SERVICE_EFFECT_COLORLOOP,
    SERVICE_EFFECT_FLAME,
    SERVICE_EFFECT_MORPH,
    SERVICE_EFFECT_MOVE,
    SERVICE_EFFECT_PULSE,
    SERVICE_EFFECT_SKY,
    SERVICE_EFFECT_STOP,
    SERVICE_PAINT_THEME,
)

if TYPE_CHECKING:
    from .manager import LIFXManager

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
        vol.Exclusive(ATTR_THEME, COLOR_GROUP): vol.In(ThemeLibrary().themes),
        vol.Exclusive(ATTR_PALETTE, COLOR_GROUP): vol.All(
            cv.ensure_list, [HSBK_SCHEMA]
        ),
    }
)

LIFX_EFFECT_MOVE_SCHEMA = cv.make_entity_service_schema(
    {
        **LIFX_EFFECT_SCHEMA,
        ATTR_SPEED: vol.All(vol.Coerce(float), vol.Clamp(min=0.1, max=60)),
        ATTR_DIRECTION: vol.In(EFFECT_MOVE_DIRECTIONS),
        vol.Optional(ATTR_THEME): vol.In(ThemeLibrary().themes),
    }
)

LIFX_EFFECT_SKY_SCHEMA = cv.make_entity_service_schema(
    {
        **LIFX_EFFECT_SCHEMA,
        ATTR_SPEED: vol.All(vol.Coerce(int), vol.Clamp(min=1, max=86400)),
        ATTR_SKY_TYPE: vol.In(EFFECT_SKY_SKY_TYPES),
        ATTR_CLOUD_SATURATION_MIN: vol.All(vol.Coerce(int), vol.Clamp(min=0, max=255)),
        ATTR_CLOUD_SATURATION_MAX: vol.All(vol.Coerce(int), vol.Clamp(min=0, max=255)),
        ATTR_PALETTE: vol.All(cv.ensure_list, [HSBK_SCHEMA]),
    }
)

LIFX_PAINT_THEME_SCHEMA = cv.make_entity_service_schema(
    {
        **LIFX_EFFECT_SCHEMA,
        ATTR_TRANSITION: vol.All(vol.Coerce(int), vol.Clamp(min=1, max=3600)),
        vol.Exclusive(ATTR_THEME, COLOR_GROUP): vol.In(ThemeLibrary().themes),
        vol.Exclusive(ATTR_PALETTE, COLOR_GROUP): vol.All(
            cv.ensure_list, [HSBK_SCHEMA]
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


def _get_manager(service: ServiceCall) -> LIFXManager:
    """Return the LIFX manager, raising a user-facing error if unavailable."""
    if (manager := service.hass.data.get(DATA_LIFX_MANAGER)) is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="not_loaded",
        )

    return manager


async def _async_start_effect(service: ServiceCall) -> None:
    """Apply a service, i.e. start an effect."""
    manager = _get_manager(service)
    referenced = async_extract_referenced_entity_ids(
        service.hass, TargetSelection(service.data)
    )
    all_referenced = referenced.referenced | referenced.indirectly_referenced
    if all_referenced:
        await manager.start_effect(all_referenced, service.service, **service.data)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the LIFX effect services."""
    for service, schema in SERVICES_SCHEMA.items():
        hass.services.async_register(
            DOMAIN, service, _async_start_effect, schema=schema
        )
