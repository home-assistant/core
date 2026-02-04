"""Support for Bond services."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.fan import DOMAIN as FAN_DOMAIN
from homeassistant.components.light import ATTR_BRIGHTNESS, DOMAIN as LIGHT_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN

ATTR_POWER_STATE = "power_state"

# Fan
SERVICE_SET_FAN_SPEED_TRACKED_STATE = "set_fan_speed_tracked_state"

# Switch
SERVICE_SET_POWER_TRACKED_STATE = "set_switch_power_tracked_state"

# Light
SERVICE_SET_LIGHT_POWER_TRACKED_STATE = "set_light_power_tracked_state"
SERVICE_SET_LIGHT_BRIGHTNESS_TRACKED_STATE = "set_light_brightness_tracked_state"
SERVICE_START_INCREASING_BRIGHTNESS = "start_increasing_brightness"
SERVICE_START_DECREASING_BRIGHTNESS = "start_decreasing_brightness"
SERVICE_STOP = "stop"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Home Assistant services."""

    # Fan entity services
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_FAN_SPEED_TRACKED_STATE,
        entity_domain=FAN_DOMAIN,
        schema={vol.Required("speed"): vol.All(vol.Number(scale=0), vol.Range(0, 100))},
        func="async_set_speed_belief",
    )

    # Light entity services
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_START_INCREASING_BRIGHTNESS,
        entity_domain=LIGHT_DOMAIN,
        schema=None,
        func="async_start_increasing_brightness",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_START_DECREASING_BRIGHTNESS,
        entity_domain=LIGHT_DOMAIN,
        schema=None,
        func="async_start_decreasing_brightness",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_STOP,
        entity_domain=LIGHT_DOMAIN,
        schema=None,
        func="async_stop",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_LIGHT_BRIGHTNESS_TRACKED_STATE,
        entity_domain=LIGHT_DOMAIN,
        schema={
            vol.Required(ATTR_BRIGHTNESS): vol.All(
                vol.Number(scale=0), vol.Range(0, 255)
            )
        },
        func="async_set_brightness_belief",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_LIGHT_POWER_TRACKED_STATE,
        entity_domain=LIGHT_DOMAIN,
        schema={vol.Required(ATTR_POWER_STATE): vol.All(cv.boolean)},
        func="async_set_power_belief",
    )

    # Switch entity services
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_POWER_TRACKED_STATE,
        entity_domain=SWITCH_DOMAIN,
        schema={vol.Required(ATTR_POWER_STATE): cv.boolean},
        func="async_set_power_belief",
    )
