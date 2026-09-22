"""Support for LIFX services."""

from typing import TYPE_CHECKING

from aiolifx_themes.themes import ThemeLibrary
import probatio

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
    LIGHT_TURN_ON_SCHEMA,
    VALID_BRIGHTNESS,
    VALID_BRIGHTNESS_PCT,
)
from homeassistant.const import ATTR_MODE, Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_register_platform_entity_service
from homeassistant.helpers.target import (
    TargetSelection,
    async_extract_referenced_entity_ids,
)
from homeassistant.helpers.typing import VolDictType

from .const import (
    ATTR_CHANGE,
    ATTR_CLOUD_SATURATION_MAX,
    ATTR_CLOUD_SATURATION_MIN,
    ATTR_CYCLES,
    ATTR_DIRECTION,
    ATTR_DURATION,
    ATTR_INFRARED,
    ATTR_PALETTE,
    ATTR_PERIOD,
    ATTR_POWER,
    ATTR_POWER_ON,
    ATTR_SATURATION_MAX,
    ATTR_SATURATION_MIN,
    ATTR_SKY_TYPE,
    ATTR_SPEED,
    ATTR_SPREAD,
    ATTR_THEME,
    ATTR_ZONES,
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
    SERVICE_SET_HEV_CYCLE_STATE,
    SERVICE_SET_STATE,
)
from .util import async_entry_is_legacy

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
    probatio.Optional(ATTR_POWER_ON, default=True): cv.boolean,
}

LIFX_EFFECT_PULSE_SCHEMA = cv.make_entity_service_schema(
    {
        **LIFX_EFFECT_SCHEMA,
        probatio.Exclusive(ATTR_BRIGHTNESS, ATTR_BRIGHTNESS): VALID_BRIGHTNESS,
        probatio.Exclusive(ATTR_BRIGHTNESS_PCT, ATTR_BRIGHTNESS): VALID_BRIGHTNESS_PCT,
        probatio.Exclusive(ATTR_COLOR_NAME, COLOR_GROUP): cv.string,
        probatio.Exclusive(ATTR_RGB_COLOR, COLOR_GROUP): probatio.All(
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
                    probatio.All(
                        probatio.Coerce(float), probatio.Range(min=0, max=100)
                    ),
                )
            ),
        ),
        probatio.Exclusive(ATTR_COLOR_TEMP_KELVIN, COLOR_GROUP): probatio.All(
            probatio.Coerce(int), probatio.Range(min=1500, max=9000)
        ),
        ATTR_PERIOD: probatio.All(probatio.Coerce(float), probatio.Range(min=0.05)),
        ATTR_CYCLES: probatio.All(probatio.Coerce(float), probatio.Range(min=1)),
        ATTR_MODE: probatio.In(PULSE_MODES),
    }
)

LIFX_EFFECT_COLORLOOP_SCHEMA = cv.make_entity_service_schema(
    {
        **LIFX_EFFECT_SCHEMA,
        probatio.Exclusive(ATTR_BRIGHTNESS, ATTR_BRIGHTNESS): VALID_BRIGHTNESS,
        probatio.Exclusive(ATTR_BRIGHTNESS_PCT, ATTR_BRIGHTNESS): VALID_BRIGHTNESS_PCT,
        ATTR_SATURATION_MAX: probatio.All(
            probatio.Coerce(int), probatio.Clamp(min=0, max=100)
        ),
        ATTR_SATURATION_MIN: probatio.All(
            probatio.Coerce(int), probatio.Clamp(min=0, max=100)
        ),
        ATTR_PERIOD: probatio.All(probatio.Coerce(float), probatio.Clamp(min=0.05)),
        ATTR_CHANGE: probatio.All(
            probatio.Coerce(float), probatio.Clamp(min=0, max=360)
        ),
        ATTR_SPREAD: probatio.All(
            probatio.Coerce(float), probatio.Clamp(min=0, max=360)
        ),
        ATTR_TRANSITION: cv.positive_float,
    }
)

LIFX_EFFECT_STOP_SCHEMA = cv.make_entity_service_schema({})

LIFX_EFFECT_FLAME_SCHEMA = cv.make_entity_service_schema(
    {
        **LIFX_EFFECT_SCHEMA,
        ATTR_SPEED: probatio.All(probatio.Coerce(int), probatio.Clamp(min=1, max=25)),
    }
)

HSBK_SCHEMA = probatio.All(
    probatio.Coerce(tuple),
    probatio.ExactSequence(
        (
            probatio.All(probatio.Coerce(float), probatio.Range(min=0, max=360)),
            probatio.All(probatio.Coerce(float), probatio.Range(min=0, max=100)),
            probatio.All(probatio.Coerce(float), probatio.Clamp(min=0, max=100)),
            probatio.All(probatio.Coerce(int), probatio.Clamp(min=1500, max=9000)),
        )
    ),
)

LIFX_EFFECT_MORPH_SCHEMA = cv.make_entity_service_schema(
    {
        **LIFX_EFFECT_SCHEMA,
        ATTR_SPEED: probatio.All(probatio.Coerce(int), probatio.Clamp(min=1, max=25)),
        probatio.Exclusive(ATTR_THEME, COLOR_GROUP): probatio.In(ThemeLibrary().themes),
        probatio.Exclusive(ATTR_PALETTE, COLOR_GROUP): probatio.All(
            cv.ensure_list, [HSBK_SCHEMA]
        ),
    }
)

LIFX_EFFECT_MOVE_SCHEMA = cv.make_entity_service_schema(
    {
        **LIFX_EFFECT_SCHEMA,
        ATTR_SPEED: probatio.All(
            probatio.Coerce(float), probatio.Clamp(min=0.1, max=60)
        ),
        ATTR_DIRECTION: probatio.In(EFFECT_MOVE_DIRECTIONS),
        probatio.Optional(ATTR_THEME): probatio.In(ThemeLibrary().themes),
    }
)

LIFX_EFFECT_SKY_SCHEMA = cv.make_entity_service_schema(
    {
        **LIFX_EFFECT_SCHEMA,
        ATTR_SPEED: probatio.All(
            probatio.Coerce(int), probatio.Clamp(min=1, max=86400)
        ),
        ATTR_SKY_TYPE: probatio.In(EFFECT_SKY_SKY_TYPES),
        ATTR_CLOUD_SATURATION_MIN: probatio.All(
            probatio.Coerce(int), probatio.Clamp(min=0, max=255)
        ),
        ATTR_CLOUD_SATURATION_MAX: probatio.All(
            probatio.Coerce(int), probatio.Clamp(min=0, max=255)
        ),
        ATTR_PALETTE: probatio.All(cv.ensure_list, [HSBK_SCHEMA]),
    }
)

LIFX_PAINT_THEME_SCHEMA = cv.make_entity_service_schema(
    {
        **LIFX_EFFECT_SCHEMA,
        ATTR_TRANSITION: probatio.All(
            probatio.Coerce(int), probatio.Clamp(min=1, max=3600)
        ),
        probatio.Exclusive(ATTR_THEME, COLOR_GROUP): probatio.In(ThemeLibrary().themes),
        probatio.Exclusive(ATTR_PALETTE, COLOR_GROUP): probatio.All(
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


LIFX_SET_STATE_SCHEMA: VolDictType = {
    **LIGHT_TURN_ON_SCHEMA,
    ATTR_INFRARED: probatio.All(probatio.Coerce(int), probatio.Clamp(min=0, max=255)),
    ATTR_ZONES: probatio.All(cv.ensure_list, [cv.positive_int]),
    ATTR_POWER: cv.boolean,
}

LIFX_SET_HEV_CYCLE_STATE_SCHEMA: VolDictType = {
    probatio.Required(ATTR_POWER): cv.boolean,
    ATTR_DURATION: probatio.All(
        probatio.Coerce(float), probatio.Clamp(min=0, max=86400)
    ),
}


def _get_manager(service: ServiceCall) -> LIFXManager:
    """Return the LIFX manager, raising a user-facing error if unavailable."""
    hass = service.hass
    # The manager is stored before the connection and first refresh are awaited,
    # so its presence alone does not mean a device is usable.
    if (manager := hass.data.get(DATA_LIFX_MANAGER)) is None or all(
        async_entry_is_legacy(entry)
        for entry in hass.config_entries.async_loaded_entries(DOMAIN)
    ):
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
    """Register the LIFX services."""
    for service, schema in SERVICES_SCHEMA.items():
        hass.services.async_register(
            DOMAIN, service, _async_start_effect, schema=schema
        )

    async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_STATE,
        entity_domain=Platform.LIGHT,
        schema=LIFX_SET_STATE_SCHEMA,
        func="set_state",
    )
    async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_HEV_CYCLE_STATE,
        entity_domain=Platform.LIGHT,
        schema=LIFX_SET_HEV_CYCLE_STATE_SCHEMA,
        func="set_hev_cycle_state",
    )
