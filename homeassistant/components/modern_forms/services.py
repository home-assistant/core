"""Services for the Modern Forms integration."""

from enum import StrEnum

import probatio

from homeassistant.components.fan import DOMAIN as FAN_DOMAIN
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import service

from .const import DOMAIN


class ModernFormsService(StrEnum):
    """Store keys for Modern Forms services."""

    SET_LIGHT_SLEEP_TIMER = "set_light_sleep_timer"
    CLEAR_LIGHT_SLEEP_TIMER = "clear_light_sleep_timer"
    SET_FAN_SLEEP_TIMER = "set_fan_sleep_timer"
    CLEAR_FAN_SLEEP_TIMER = "clear_fan_sleep_timer"


class ModernFormsServiceArgument(StrEnum):
    """Store keys for Modern Forms service arguments."""

    SLEEP_TIME = "sleep_time"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up the services for the Modern Forms integration."""

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        ModernFormsService.SET_FAN_SLEEP_TIMER,
        entity_domain=FAN_DOMAIN,
        schema={
            probatio.Required(ModernFormsServiceArgument.SLEEP_TIME): probatio.All(
                probatio.Coerce(int), probatio.Range(min=1, max=1440)
            )
        },
        func="async_set_fan_sleep_timer",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        ModernFormsService.CLEAR_FAN_SLEEP_TIMER,
        entity_domain=FAN_DOMAIN,
        schema=None,
        func="async_clear_fan_sleep_timer",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        ModernFormsService.SET_LIGHT_SLEEP_TIMER,
        entity_domain=LIGHT_DOMAIN,
        schema={
            probatio.Required(ModernFormsServiceArgument.SLEEP_TIME): probatio.All(
                probatio.Coerce(int), probatio.Range(min=1, max=1440)
            )
        },
        func="async_set_light_sleep_timer",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        ModernFormsService.CLEAR_LIGHT_SLEEP_TIMER,
        entity_domain=LIGHT_DOMAIN,
        schema=None,
        func="async_clear_light_sleep_timer",
    )
