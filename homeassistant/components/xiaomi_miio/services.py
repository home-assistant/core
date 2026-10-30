"""Xiaomi services."""

import asyncio
from collections.abc import Callable, Coroutine
from datetime import timedelta
import logging
from typing import Any

import probatio

from homeassistant.components import persistent_notification
from homeassistant.components.fan import DOMAIN as FAN_DOMAIN
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.remote import DOMAIN as REMOTE_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.vacuum import DOMAIN as VACUUM_DOMAIN
from homeassistant.const import ATTR_MODE, CONF_TIMEOUT
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.entity import Entity
from homeassistant.util.dt import utcnow

from .const import (
    ATTR_SCENE,
    CONF_SLOT,
    DOMAIN,
    SERVICE_EYECARE_MODE_OFF,
    SERVICE_EYECARE_MODE_ON,
    SERVICE_LEARN,
    SERVICE_NIGHT_LIGHT_MODE_OFF,
    SERVICE_NIGHT_LIGHT_MODE_ON,
    SERVICE_REMINDER_OFF,
    SERVICE_REMINDER_ON,
    SERVICE_RESET_FILTER,
    SERVICE_SET_DELAYED_TURN_OFF,
    SERVICE_SET_EXTRA_FEATURES,
    SERVICE_SET_POWER_MODE,
    SERVICE_SET_POWER_PRICE,
    SERVICE_SET_REMOTE_LED_OFF,
    SERVICE_SET_REMOTE_LED_ON,
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


async def _async_remote_led_off(entity, service_call: ServiceCall) -> None:
    """Handle set_led_off command."""
    await service_call.hass.async_add_executor_job(
        entity.device.set_indicator_led, False
    )


async def _async_remote_led_on(entity, service_call: ServiceCall) -> None:
    """Handle set_led_on command."""
    await service_call.hass.async_add_executor_job(
        entity.device.set_indicator_led, True
    )


async def _async_remote_learn(entity, service_call: ServiceCall) -> None:
    """Handle a learn command."""
    hass = service_call.hass
    device = entity.device

    slot = service_call.data.get(CONF_SLOT, entity.slot)

    await hass.async_add_executor_job(device.learn, slot)

    timeout = service_call.data.get(CONF_TIMEOUT, entity.timeout)

    _LOGGER.info("Press the key you want Home Assistant to learn")
    start_time = utcnow()
    while (utcnow() - start_time) < timedelta(seconds=timeout):
        message = await hass.async_add_executor_job(device.read, slot)
        _LOGGER.debug("Message received from device: '%s'", message)

        if code := message.get("code"):
            log_msg = f"Received command is: {code}"
            _LOGGER.info(log_msg)
            persistent_notification.async_create(
                hass, log_msg, title="Xiaomi Miio Remote"
            )
            return

        if "error" in message and message["error"]["message"] == "learn timeout":
            await hass.async_add_executor_job(device.learn, slot)

        await asyncio.sleep(1)

    _LOGGER.error("Timeout. No infrared command captured")
    persistent_notification.async_create(
        hass, "Timeout. No infrared command captured", title="Xiaomi Miio Remote"
    )


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
            probatio.Required(ATTR_SCENE): probatio.All(
                probatio.Coerce(int), probatio.Clamp(min=1, max=6)
            )
        },
        func=_async_service_method("async_set_scene", ATTR_SCENE),
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_DELAYED_TURN_OFF,
        entity_domain=LIGHT_DOMAIN,
        schema={probatio.Required(ATTR_TIME_PERIOD): cv.positive_time_period},
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
        schema={
            probatio.Required(ATTR_MODE): probatio.All(probatio.In(["green", "normal"]))
        },
        func=_async_service_method("async_set_power_mode", ATTR_MODE),
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_POWER_PRICE,
        entity_domain=SWITCH_DOMAIN,
        schema={probatio.Required(ATTR_PRICE): cv.positive_float},
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
        schema={probatio.Required(ATTR_FEATURES): cv.positive_int},
        func=_async_service_method("async_set_extra_features", ATTR_FEATURES),
    )

    # Remote Services
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_LEARN,
        entity_domain=REMOTE_DOMAIN,
        func=_async_remote_learn,
        schema={
            probatio.Optional(CONF_TIMEOUT, default=10): cv.positive_int,
            probatio.Optional(CONF_SLOT, default=1): probatio.All(
                int, probatio.Range(min=1, max=1000000)
            ),
        },
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_REMOTE_LED_ON,
        entity_domain=REMOTE_DOMAIN,
        func=_async_remote_led_on,
        schema=None,
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_SET_REMOTE_LED_OFF,
        entity_domain=REMOTE_DOMAIN,
        func=_async_remote_led_off,
        schema=None,
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
            probatio.Optional(ATTR_RC_VELOCITY): probatio.All(
                probatio.Coerce(float), probatio.Clamp(min=-0.29, max=0.29)
            ),
            probatio.Optional(ATTR_RC_ROTATION): probatio.All(
                probatio.Coerce(int), probatio.Clamp(min=-179, max=179)
            ),
            probatio.Optional(ATTR_RC_DURATION): cv.positive_int,
        },
        func="async_remote_control_move",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_MOVE_REMOTE_CONTROL_STEP,
        entity_domain=VACUUM_DOMAIN,
        schema={
            probatio.Optional(ATTR_RC_VELOCITY): probatio.All(
                probatio.Coerce(float), probatio.Clamp(min=-0.29, max=0.29)
            ),
            probatio.Optional(ATTR_RC_ROTATION): probatio.All(
                probatio.Coerce(int), probatio.Clamp(min=-179, max=179)
            ),
            probatio.Optional(ATTR_RC_DURATION): cv.positive_int,
        },
        func="async_remote_control_move_step",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_CLEAN_ZONE,
        entity_domain=VACUUM_DOMAIN,
        schema={
            probatio.Required(ATTR_ZONE_ARRAY): probatio.All(
                list,
                [
                    probatio.ExactSequence(
                        [
                            probatio.Coerce(int),
                            probatio.Coerce(int),
                            probatio.Coerce(int),
                            probatio.Coerce(int),
                        ]
                    )
                ],
            ),
            probatio.Required(ATTR_ZONE_REPEATER): probatio.All(
                probatio.Coerce(int), probatio.Clamp(min=1, max=3)
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
            probatio.Required("x_coord"): probatio.Coerce(int),
            probatio.Required("y_coord"): probatio.Coerce(int),
        },
        func="async_goto",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_CLEAN_SEGMENT,
        entity_domain=VACUUM_DOMAIN,
        schema={
            probatio.Required("segments"): probatio.Any(
                probatio.Coerce(int), [probatio.Coerce(int)]
            )
        },
        func="async_clean_segment",
    )
