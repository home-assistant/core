"""Services for the Yeelight integration."""

from enum import StrEnum

import probatio
from yeelight import Flow
from yeelight.enums import PowerMode, SceneClass

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.const import CommonServiceArgument
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.typing import VolDictType

from .const import DOMAIN, YEELIGHT_FLOW_TRANSITION_SCHEMA
from .helpers import transitions_config_parser

_EXAMPLES_URL = "https://yeelight.readthedocs.io/en/stable/flow.html"


class YeelightService(StrEnum):
    """Store keys for Yeelight services."""

    SET_MODE = "set_mode"
    SET_COLOR_SCENE = "set_color_scene"
    SET_HSV_SCENE = "set_hsv_scene"
    SET_COLOR_TEMP_SCENE = "set_color_temp_scene"
    SET_COLOR_FLOW_SCENE = "set_color_flow_scene"
    SET_AUTO_DELAY_OFF_SCENE = "set_auto_delay_off_scene"
    START_FLOW = "start_flow"
    SET_MUSIC_MODE = "set_music_mode"


class YeelightServiceArgument(StrEnum):
    """Store keys for Yeelight service arguments."""

    MODE = "mode"
    RGB_COLOR = "rgb_color"
    BRIGHTNESS = "brightness"
    HS_COLOR = "hs_color"
    KELVIN = "kelvin"
    COUNT = "count"
    ACTION = "action"
    TRANSITIONS = "transitions"
    MINUTES = "minutes"
    MUSIC_MODE = "music_mode"


VALID_BRIGHTNESS = probatio.All(probatio.Coerce(int), probatio.Range(min=1, max=100))

SERVICE_SCHEMA_SET_MODE: VolDictType = {
    probatio.Required(YeelightServiceArgument.MODE): probatio.In(
        [mode.name.lower() for mode in PowerMode]
    )
}

SERVICE_SCHEMA_SET_MUSIC_MODE: VolDictType = {
    probatio.Required(YeelightServiceArgument.MUSIC_MODE): cv.boolean
}

SERVICE_SCHEMA_START_FLOW = YEELIGHT_FLOW_TRANSITION_SCHEMA

SERVICE_SCHEMA_SET_COLOR_SCENE: VolDictType = {
    probatio.Required(YeelightServiceArgument.RGB_COLOR): probatio.All(
        probatio.Coerce(tuple), probatio.ExactSequence((cv.byte, cv.byte, cv.byte))
    ),
    probatio.Required(YeelightServiceArgument.BRIGHTNESS): VALID_BRIGHTNESS,
}

SERVICE_SCHEMA_SET_HSV_SCENE: VolDictType = {
    probatio.Required(YeelightServiceArgument.HS_COLOR): probatio.All(
        probatio.Coerce(tuple),
        probatio.ExactSequence(
            (
                probatio.All(probatio.Coerce(float), probatio.Range(min=0, max=359)),
                probatio.All(probatio.Coerce(float), probatio.Percentage()),
            )
        ),
    ),
    probatio.Required(YeelightServiceArgument.BRIGHTNESS): VALID_BRIGHTNESS,
}

SERVICE_SCHEMA_SET_COLOR_TEMP_SCENE: VolDictType = {
    probatio.Required(YeelightServiceArgument.KELVIN): probatio.All(
        probatio.Coerce(int), probatio.Range(min=1700, max=6500)
    ),
    probatio.Required(YeelightServiceArgument.BRIGHTNESS): VALID_BRIGHTNESS,
}

SERVICE_SCHEMA_SET_COLOR_FLOW_SCENE = YEELIGHT_FLOW_TRANSITION_SCHEMA

SERVICE_SCHEMA_SET_AUTO_DELAY_OFF_SCENE: VolDictType = {
    probatio.Required(YeelightServiceArgument.MINUTES): probatio.All(
        probatio.Coerce(int), probatio.Range(min=1, max=60)
    ),
    probatio.Required(YeelightServiceArgument.BRIGHTNESS): VALID_BRIGHTNESS,
}


async def _async_start_flow(entity, service_call):
    params = {**service_call.data}
    params.pop(CommonServiceArgument.ENTITY_ID)
    params[YeelightServiceArgument.TRANSITIONS] = transitions_config_parser(
        params[YeelightServiceArgument.TRANSITIONS]
    )
    await entity.async_start_flow(**params)


async def _async_set_color_scene(entity, service_call):
    await entity.async_set_scene(
        SceneClass.COLOR,
        *service_call.data[YeelightServiceArgument.RGB_COLOR],
        service_call.data[YeelightServiceArgument.BRIGHTNESS],
    )


async def _async_set_hsv_scene(entity, service_call):
    await entity.async_set_scene(
        SceneClass.HSV,
        *service_call.data[YeelightServiceArgument.HS_COLOR],
        service_call.data[YeelightServiceArgument.BRIGHTNESS],
    )


async def _async_set_color_temp_scene(entity, service_call):
    await entity.async_set_scene(
        SceneClass.CT,
        service_call.data[YeelightServiceArgument.KELVIN],
        service_call.data[YeelightServiceArgument.BRIGHTNESS],
    )


async def _async_set_color_flow_scene(entity, service_call):
    flow = Flow(
        count=service_call.data[YeelightServiceArgument.COUNT],
        action=Flow.actions[service_call.data[YeelightServiceArgument.ACTION]],
        transitions=transitions_config_parser(
            service_call.data[YeelightServiceArgument.TRANSITIONS]
        ),
    )
    await entity.async_set_scene(SceneClass.CF, flow)


async def _async_set_auto_delay_off_scene(entity, service_call):
    await entity.async_set_scene(
        SceneClass.AUTO_DELAY_OFF,
        service_call.data[YeelightServiceArgument.BRIGHTNESS],
        service_call.data[YeelightServiceArgument.MINUTES],
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up custom services."""
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        YeelightService.SET_MODE,
        entity_domain=LIGHT_DOMAIN,
        schema=SERVICE_SCHEMA_SET_MODE,
        func="async_set_mode",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        YeelightService.START_FLOW,
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
        YeelightService.SET_COLOR_SCENE,
        entity_domain=LIGHT_DOMAIN,
        schema=SERVICE_SCHEMA_SET_COLOR_SCENE,
        func=_async_set_color_scene,
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        YeelightService.SET_HSV_SCENE,
        entity_domain=LIGHT_DOMAIN,
        schema=SERVICE_SCHEMA_SET_HSV_SCENE,
        func=_async_set_hsv_scene,
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        YeelightService.SET_COLOR_TEMP_SCENE,
        entity_domain=LIGHT_DOMAIN,
        schema=SERVICE_SCHEMA_SET_COLOR_TEMP_SCENE,
        func=_async_set_color_temp_scene,
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        YeelightService.SET_COLOR_FLOW_SCENE,
        entity_domain=LIGHT_DOMAIN,
        schema=SERVICE_SCHEMA_SET_COLOR_FLOW_SCENE,
        func=_async_set_color_flow_scene,
        description_placeholders={"examples_url": _EXAMPLES_URL},
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        YeelightService.SET_AUTO_DELAY_OFF_SCENE,
        entity_domain=LIGHT_DOMAIN,
        schema=SERVICE_SCHEMA_SET_AUTO_DELAY_OFF_SCENE,
        func=_async_set_auto_delay_off_scene,
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        YeelightService.SET_MUSIC_MODE,
        entity_domain=LIGHT_DOMAIN,
        schema=SERVICE_SCHEMA_SET_MUSIC_MODE,
        func="async_set_music_mode",
    )
