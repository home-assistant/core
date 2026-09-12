"""Xiaomi services."""

from collections.abc import Callable, Coroutine
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.fan import DOMAIN as FAN_DOMAIN
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.vacuum import DOMAIN as VACUUM_DOMAIN
from homeassistant.const import ATTR_MODE
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.entity import Entity

from .const import (
    ATTR_SCENE,
    DOMAIN,
    SERVICE_EYECARE_MODE_OFF,
    SERVICE_EYECARE_MODE_ON,
    SERVICE_NIGHT_LIGHT_MODE_OFF,
    SERVICE_NIGHT_LIGHT_MODE_ON,
    SERVICE_REMINDER_OFF,
    SERVICE_REMINDER_ON,
    SERVICE_RESET_FILTER,
    SERVICE_SET_DELAYED_TURN_OFF,
    SERVICE_SET_EXTRA_FEATURES,
    SERVICE_SET_POWER_MODE,
    SERVICE_SET_POWER_PRICE,
    SERVICE_SET_SCENE,
    SERVICE_SET_WIFI_LED_OFF,
    SERVICE_SET_WIFI_LED_ON,
)

_LOGGER = logging.getLogger(__name__)

ATTR_RC_DURATION = "duration"
ATTR_RC_ROTATION = "rotation"
ATTR_RC_VELOCITY = "velocity"
ATTR_ZONE_ARRAY = "zone"
ATTR_ZONE_REPEATER = "repeats"

# Vacuum Services
SERVICE_MOVE_REMOTE_CONTROL = "vacuum_remote_control_move"
SERVICE_MOVE_REMOTE_CONTROL_STEP = "vacuum_remote_control_move_step"
SERVICE_START_REMOTE_CONTROL = "vacuum_remote_control_start"
SERVICE_STOP_REMOTE_CONTROL = "vacuum_remote_control_stop"
SERVICE_CLEAN_SEGMENT = "vacuum_clean_segment"
SERVICE_CLEAN_ZONE = "vacuum_clean_zone"
SERVICE_GOTO = "vacuum_goto"

# Light Services
ATTR_TIME_PERIOD = "time_period"

# Switch Services
ATTR_PRICE = "price"

# Fan Services
ATTR_FEATURES = "features"


def _async_service_method(
    method_name: str, *fields: str
) -> Callable[[Entity, ServiceCall], Coroutine[Any, Any, None]]:
    """Return a handler calling the method on entities implementing it.

    The entities of a platform only partially implement these methods, so
    entities without it are skipped instead of raising.
    """

    async def _async_call_method(entity: Entity, call: ServiceCall) -> None:
        """Call the method on the entity."""
        if (method := getattr(entity, method_name, None)) is None:
            return
        await method(**{field: call.data[field] for field in fields})

    return _async_call_method


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services."""

    # Light Services
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_SCENE,
        entity_domain=LIGHT_DOMAIN,
        schema={
            vol.Required(ATTR_SCENE): vol.All(vol.Coerce(int), vol.Clamp(min=1, max=6))
        },
        func=_async_service_method("async_set_scene", ATTR_SCENE),
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_DELAYED_TURN_OFF,
        entity_domain=LIGHT_DOMAIN,
        schema={vol.Required(ATTR_TIME_PERIOD): cv.positive_time_period},
        func=_async_service_method("async_set_delayed_turn_off", ATTR_TIME_PERIOD),
    )

    for light_service, light_method in (
        (SERVICE_REMINDER_ON, "async_reminder_on"),
        (SERVICE_REMINDER_OFF, "async_reminder_off"),
        (SERVICE_NIGHT_LIGHT_MODE_ON, "async_night_light_mode_on"),
        (SERVICE_NIGHT_LIGHT_MODE_OFF, "async_night_light_mode_off"),
        (SERVICE_EYECARE_MODE_ON, "async_eyecare_mode_on"),
        (SERVICE_EYECARE_MODE_OFF, "async_eyecare_mode_off"),
    ):
        service.async_register_platform_entity_service(
            hass,
            DOMAIN,
            light_service,
            entity_domain=LIGHT_DOMAIN,
            schema=None,
            func=_async_service_method(light_method),
        )

    # Switch Services
    for switch_service, switch_method in (
        (SERVICE_SET_WIFI_LED_ON, "async_set_wifi_led_on"),
        (SERVICE_SET_WIFI_LED_OFF, "async_set_wifi_led_off"),
    ):
        service.async_register_platform_entity_service(
            hass,
            DOMAIN,
            switch_service,
            entity_domain=SWITCH_DOMAIN,
            schema=None,
            func=_async_service_method(switch_method),
        )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_POWER_MODE,
        entity_domain=SWITCH_DOMAIN,
        schema={vol.Required(ATTR_MODE): vol.All(vol.In(["green", "normal"]))},
        func=_async_service_method("async_set_power_mode", ATTR_MODE),
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_POWER_PRICE,
        entity_domain=SWITCH_DOMAIN,
        schema={vol.Required(ATTR_PRICE): cv.positive_float},
        func=_async_service_method("async_set_power_price", ATTR_PRICE),
    )

    # Fan Services
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_RESET_FILTER,
        entity_domain=FAN_DOMAIN,
        schema=None,
        func=_async_service_method("async_reset_filter"),
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_EXTRA_FEATURES,
        entity_domain=FAN_DOMAIN,
        schema={vol.Required(ATTR_FEATURES): cv.positive_int},
        func=_async_service_method("async_set_extra_features", ATTR_FEATURES),
    )

    # Vacuum Services
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_START_REMOTE_CONTROL,
        entity_domain=VACUUM_DOMAIN,
        schema=None,
        func="async_remote_control_start",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_STOP_REMOTE_CONTROL,
        entity_domain=VACUUM_DOMAIN,
        schema=None,
        func="async_remote_control_stop",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_MOVE_REMOTE_CONTROL,
        entity_domain=VACUUM_DOMAIN,
        schema={
            vol.Optional(ATTR_RC_VELOCITY): vol.All(
                vol.Coerce(float), vol.Clamp(min=-0.29, max=0.29)
            ),
            vol.Optional(ATTR_RC_ROTATION): vol.All(
                vol.Coerce(int), vol.Clamp(min=-179, max=179)
            ),
            vol.Optional(ATTR_RC_DURATION): cv.positive_int,
        },
        func="async_remote_control_move",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_MOVE_REMOTE_CONTROL_STEP,
        entity_domain=VACUUM_DOMAIN,
        schema={
            vol.Optional(ATTR_RC_VELOCITY): vol.All(
                vol.Coerce(float), vol.Clamp(min=-0.29, max=0.29)
            ),
            vol.Optional(ATTR_RC_ROTATION): vol.All(
                vol.Coerce(int), vol.Clamp(min=-179, max=179)
            ),
            vol.Optional(ATTR_RC_DURATION): cv.positive_int,
        },
        func="async_remote_control_move_step",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_CLEAN_ZONE,
        entity_domain=VACUUM_DOMAIN,
        schema={
            vol.Required(ATTR_ZONE_ARRAY): vol.All(
                list,
                [
                    vol.ExactSequence(
                        [
                            vol.Coerce(int),
                            vol.Coerce(int),
                            vol.Coerce(int),
                            vol.Coerce(int),
                        ]
                    )
                ],
            ),
            vol.Required(ATTR_ZONE_REPEATER): vol.All(
                vol.Coerce(int), vol.Clamp(min=1, max=3)
            ),
        },
        func="async_clean_zone",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_GOTO,
        entity_domain=VACUUM_DOMAIN,
        schema={
            vol.Required("x_coord"): vol.Coerce(int),
            vol.Required("y_coord"): vol.Coerce(int),
        },
        func="async_goto",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_CLEAN_SEGMENT,
        entity_domain=VACUUM_DOMAIN,
        schema={vol.Required("segments"): vol.Any(vol.Coerce(int), [vol.Coerce(int)])},
        func="async_clean_segment",
    )
