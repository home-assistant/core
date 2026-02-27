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


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Home Assistant services."""

    # Fan entity services
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "set_fan_speed_tracked_state",
        entity_domain=FAN_DOMAIN,
        schema={vol.Required("speed"): vol.All(vol.Number(scale=0), vol.Range(0, 100))},
        func="async_set_speed_belief",
    )

    # Light entity services
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "start_increasing_brightness",
        entity_domain=LIGHT_DOMAIN,
        schema=None,
        func="async_start_increasing_brightness",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "start_decreasing_brightness",
        entity_domain=LIGHT_DOMAIN,
        schema=None,
        func="async_start_decreasing_brightness",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "stop",
        entity_domain=LIGHT_DOMAIN,
        schema=None,
        func="async_stop",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "set_light_brightness_tracked_state",
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
        "set_light_power_tracked_state",
        entity_domain=LIGHT_DOMAIN,
        schema={vol.Required(ATTR_POWER_STATE): vol.All(cv.boolean)},
        func="async_set_power_belief",
    )

    # Switch entity services
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        "set_switch_power_tracked_state",
        entity_domain=SWITCH_DOMAIN,
        schema={vol.Required(ATTR_POWER_STATE): cv.boolean},
        func="async_set_power_belief",
    )
