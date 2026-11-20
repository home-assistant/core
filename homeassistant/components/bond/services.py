"""Support for Bond services."""

from enum import StrEnum

import probatio

from homeassistant.components.fan import DOMAIN as FAN_DOMAIN
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN


class BondService(StrEnum):
    """Store keys for Bond services."""

    SET_FAN_SPEED_TRACKED_STATE = "set_fan_speed_tracked_state"
    SET_SWITCH_POWER_TRACKED_STATE = "set_switch_power_tracked_state"
    SET_LIGHT_POWER_TRACKED_STATE = "set_light_power_tracked_state"
    SET_LIGHT_BRIGHTNESS_TRACKED_STATE = "set_light_brightness_tracked_state"
    START_INCREASING_BRIGHTNESS = "start_increasing_brightness"
    START_DECREASING_BRIGHTNESS = "start_decreasing_brightness"
    STOP = "stop"


class BondServiceArgument(StrEnum):
    """Store keys for Bond service arguments."""

    SPEED = "speed"
    POWER_STATE = "power_state"
    BRIGHTNESS = "brightness"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Home Assistant services."""

    # Fan entity services
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        BondService.SET_FAN_SPEED_TRACKED_STATE,
        entity_domain=FAN_DOMAIN,
        schema={
            probatio.Required(BondServiceArgument.SPEED): probatio.All(
                probatio.Number(scale=0), probatio.Range(0, 100)
            )
        },
        func="async_set_speed_belief",
    )

    # Light entity services
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        BondService.START_INCREASING_BRIGHTNESS,
        entity_domain=LIGHT_DOMAIN,
        schema=None,
        func="async_start_increasing_brightness",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        BondService.START_DECREASING_BRIGHTNESS,
        entity_domain=LIGHT_DOMAIN,
        schema=None,
        func="async_start_decreasing_brightness",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        BondService.STOP,
        entity_domain=LIGHT_DOMAIN,
        schema=None,
        func="async_stop",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        BondService.SET_LIGHT_BRIGHTNESS_TRACKED_STATE,
        entity_domain=LIGHT_DOMAIN,
        schema={
            probatio.Required(BondServiceArgument.BRIGHTNESS): probatio.All(
                probatio.Number(scale=0), probatio.Range(0, 255)
            )
        },
        func="async_set_brightness_belief",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        BondService.SET_LIGHT_POWER_TRACKED_STATE,
        entity_domain=LIGHT_DOMAIN,
        schema={
            probatio.Required(BondServiceArgument.POWER_STATE): probatio.All(cv.boolean)
        },
        func="async_set_power_belief",
    )

    # Switch entity services
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        BondService.SET_SWITCH_POWER_TRACKED_STATE,
        entity_domain=SWITCH_DOMAIN,
        schema={probatio.Required(BondServiceArgument.POWER_STATE): cv.boolean},
        func="async_set_power_belief",
    )
