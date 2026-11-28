"""Services for the Modern Forms integration."""

import probatio

from homeassistant.components.fan import DOMAIN as FAN_DOMAIN
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import service

from .const import (
    ATTR_SLEEP_TIME,
    DOMAIN,
    SERVICE_CLEAR_FAN_SLEEP_TIMER,
    SERVICE_CLEAR_LIGHT_SLEEP_TIMER,
    SERVICE_SET_FAN_SLEEP_TIMER,
    SERVICE_SET_LIGHT_SLEEP_TIMER,
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Modern Forms integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_FAN_SLEEP_TIMER,
        entity_domain=FAN_DOMAIN,
        schema={
            probatio.Required(ATTR_SLEEP_TIME): probatio.All(
                probatio.Coerce(int), probatio.Range(min=1, max=1440)
            )
        },
        func="async_set_fan_sleep_timer",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_CLEAR_FAN_SLEEP_TIMER,
        entity_domain=FAN_DOMAIN,
        schema=None,
        func="async_clear_fan_sleep_timer",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_LIGHT_SLEEP_TIMER,
        entity_domain=LIGHT_DOMAIN,
        schema={
            probatio.Required(ATTR_SLEEP_TIME): probatio.All(
                probatio.Coerce(int), probatio.Range(min=1, max=1440)
            )
        },
        func="async_set_light_sleep_timer",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_CLEAR_LIGHT_SLEEP_TIMER,
        entity_domain=LIGHT_DOMAIN,
        schema=None,
        func="async_clear_light_sleep_timer",
    )
