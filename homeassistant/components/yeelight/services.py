"""Services for the Yeelight integration."""

import probatio
from yeelight import Flow
from yeelight.enums import PowerMode, SceneClass

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    ATTR_RGB_COLOR,
    DOMAIN as LIGHT_DOMAIN,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_MODE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.typing import VolDictType

from .const import (
    ATTR_ACTION,
    ATTR_COUNT,
    ATTR_MODE_MUSIC,
    ATTR_TRANSITIONS,
    DOMAIN,
    YEELIGHT_FLOW_TRANSITION_SCHEMA,
)
from .helpers import transitions_config_parser

_EXAMPLES_URL = "https://yeelight.readthedocs.io/en/stable/flow.html"

ATTR_MINUTES = "minutes"
ATTR_KELVIN = "kelvin"

SERVICE_SET_MODE = "set_mode"
SERVICE_SET_MUSIC_MODE = "set_music_mode"
SERVICE_START_FLOW = "start_flow"
SERVICE_SET_COLOR_SCENE = "set_color_scene"
SERVICE_SET_HSV_SCENE = "set_hsv_scene"
SERVICE_SET_COLOR_TEMP_SCENE = "set_color_temp_scene"
SERVICE_SET_COLOR_FLOW_SCENE = "set_color_flow_scene"
SERVICE_SET_AUTO_DELAY_OFF_SCENE = "set_auto_delay_off_scene"

VALID_BRIGHTNESS = probatio.All(probatio.Coerce(int), probatio.Range(min=1, max=100))

SERVICE_SCHEMA_SET_MODE: VolDictType = {
    probatio.Required(ATTR_MODE): probatio.In([mode.name.lower() for mode in PowerMode])
}

SERVICE_SCHEMA_SET_MUSIC_MODE: VolDictType = {
    probatio.Required(ATTR_MODE_MUSIC): cv.boolean
}

SERVICE_SCHEMA_START_FLOW = YEELIGHT_FLOW_TRANSITION_SCHEMA

SERVICE_SCHEMA_SET_COLOR_SCENE: VolDictType = {
    probatio.Required(ATTR_RGB_COLOR): probatio.All(
        probatio.Coerce(tuple), probatio.ExactSequence((cv.byte, cv.byte, cv.byte))
    ),
    probatio.Required(ATTR_BRIGHTNESS): VALID_BRIGHTNESS,
}

SERVICE_SCHEMA_SET_HSV_SCENE: VolDictType = {
    probatio.Required(ATTR_HS_COLOR): probatio.All(
        probatio.Coerce(tuple),
        probatio.ExactSequence(
            (
                probatio.All(probatio.Coerce(float), probatio.Range(min=0, max=359)),
                probatio.All(probatio.Coerce(float), probatio.Percentage()),
            )
        ),
    ),
    probatio.Required(ATTR_BRIGHTNESS): VALID_BRIGHTNESS,
}

SERVICE_SCHEMA_SET_COLOR_TEMP_SCENE: VolDictType = {
    probatio.Required(ATTR_KELVIN): probatio.All(
        probatio.Coerce(int), probatio.Range(min=1700, max=6500)
    ),
    probatio.Required(ATTR_BRIGHTNESS): VALID_BRIGHTNESS,
}

SERVICE_SCHEMA_SET_COLOR_FLOW_SCENE = YEELIGHT_FLOW_TRANSITION_SCHEMA

SERVICE_SCHEMA_SET_AUTO_DELAY_OFF_SCENE: VolDictType = {
    probatio.Required(ATTR_MINUTES): probatio.All(
        probatio.Coerce(int), probatio.Range(min=1, max=60)
    ),
    probatio.Required(ATTR_BRIGHTNESS): VALID_BRIGHTNESS,
}


async def _async_start_flow(entity, service_call):
    params = {**service_call.data}
    params.pop(ATTR_ENTITY_ID)
    params[ATTR_TRANSITIONS] = transitions_config_parser(params[ATTR_TRANSITIONS])
    await entity.async_start_flow(**params)


async def _async_set_color_scene(entity, service_call):
    await entity.async_set_scene(
        SceneClass.COLOR,
        *service_call.data[ATTR_RGB_COLOR],
        service_call.data[ATTR_BRIGHTNESS],
    )


async def _async_set_hsv_scene(entity, service_call):
    await entity.async_set_scene(
        SceneClass.HSV,
        *service_call.data[ATTR_HS_COLOR],
        service_call.data[ATTR_BRIGHTNESS],
    )


async def _async_set_color_temp_scene(entity, service_call):
    await entity.async_set_scene(
        SceneClass.CT,
        service_call.data[ATTR_KELVIN],
        service_call.data[ATTR_BRIGHTNESS],
    )


async def _async_set_color_flow_scene(entity, service_call):
    flow = Flow(
        count=service_call.data[ATTR_COUNT],
        action=Flow.actions[service_call.data[ATTR_ACTION]],
        transitions=transitions_config_parser(service_call.data[ATTR_TRANSITIONS]),
    )
    await entity.async_set_scene(SceneClass.CF, flow)


async def _async_set_auto_delay_off_scene(entity, service_call):
    await entity.async_set_scene(
        SceneClass.AUTO_DELAY_OFF,
        service_call.data[ATTR_BRIGHTNESS],
        service_call.data[ATTR_MINUTES],
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up custom services."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_MODE,
        entity_domain=LIGHT_DOMAIN,
        schema=SERVICE_SCHEMA_SET_MODE,
        func="async_set_mode",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_START_FLOW,
        entity_domain=LIGHT_DOMAIN,
        schema=SERVICE_SCHEMA_START_FLOW,
        func=_async_start_flow,
        description_placeholders={
            "examples_url": _EXAMPLES_URL,
            "flow_objects_urls": "https://yeelight.readthedocs.io/en/stable/yeelight.html#flow-objects",
        },
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_COLOR_SCENE,
        entity_domain=LIGHT_DOMAIN,
        schema=SERVICE_SCHEMA_SET_COLOR_SCENE,
        func=_async_set_color_scene,
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_HSV_SCENE,
        entity_domain=LIGHT_DOMAIN,
        schema=SERVICE_SCHEMA_SET_HSV_SCENE,
        func=_async_set_hsv_scene,
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_COLOR_TEMP_SCENE,
        entity_domain=LIGHT_DOMAIN,
        schema=SERVICE_SCHEMA_SET_COLOR_TEMP_SCENE,
        func=_async_set_color_temp_scene,
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_COLOR_FLOW_SCENE,
        entity_domain=LIGHT_DOMAIN,
        schema=SERVICE_SCHEMA_SET_COLOR_FLOW_SCENE,
        func=_async_set_color_flow_scene,
        description_placeholders={"examples_url": _EXAMPLES_URL},
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_AUTO_DELAY_OFF_SCENE,
        entity_domain=LIGHT_DOMAIN,
        schema=SERVICE_SCHEMA_SET_AUTO_DELAY_OFF_SCENE,
        func=_async_set_auto_delay_off_scene,
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_MUSIC_MODE,
        entity_domain=LIGHT_DOMAIN,
        schema=SERVICE_SCHEMA_SET_MUSIC_MODE,
        func="async_set_music_mode",
    )
