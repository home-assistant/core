"""Xiaomi services."""

import asyncio
from collections.abc import Callable, Coroutine
from datetime import timedelta
from enum import StrEnum
import logging
from typing import Any

import probatio

from homeassistant.components import persistent_notification
from homeassistant.components.fan import DOMAIN as FAN_DOMAIN
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.remote import DOMAIN as REMOTE_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.vacuum import DOMAIN as VACUUM_DOMAIN
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv, service
from homeassistant.helpers.entity import Entity
from homeassistant.util.dt import utcnow

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class XiaomiMiioService(StrEnum):
    """Store keys for Xiaomi Miio services."""

    FAN_RESET_FILTER = "fan_reset_filter"
    FAN_SET_EXTRA_FEATURES = "fan_set_extra_features"
    LIGHT_SET_SCENE = "light_set_scene"
    LIGHT_SET_DELAYED_TURN_OFF = "light_set_delayed_turn_off"
    LIGHT_REMINDER_ON = "light_reminder_on"
    LIGHT_REMINDER_OFF = "light_reminder_off"
    LIGHT_NIGHT_LIGHT_MODE_ON = "light_night_light_mode_on"
    LIGHT_NIGHT_LIGHT_MODE_OFF = "light_night_light_mode_off"
    LIGHT_EYECARE_MODE_ON = "light_eyecare_mode_on"
    LIGHT_EYECARE_MODE_OFF = "light_eyecare_mode_off"
    REMOTE_LEARN_COMMAND = "remote_learn_command"
    REMOTE_SET_LED_ON = "remote_set_led_on"
    REMOTE_SET_LED_OFF = "remote_set_led_off"
    SWITCH_SET_WIFI_LED_ON = "switch_set_wifi_led_on"
    SWITCH_SET_WIFI_LED_OFF = "switch_set_wifi_led_off"
    SWITCH_SET_POWER_PRICE = "switch_set_power_price"
    SWITCH_SET_POWER_MODE = "switch_set_power_mode"
    VACUUM_REMOTE_CONTROL_START = "vacuum_remote_control_start"
    VACUUM_REMOTE_CONTROL_STOP = "vacuum_remote_control_stop"
    VACUUM_REMOTE_CONTROL_MOVE = "vacuum_remote_control_move"
    VACUUM_REMOTE_CONTROL_MOVE_STEP = "vacuum_remote_control_move_step"
    VACUUM_CLEAN_ZONE = "vacuum_clean_zone"
    VACUUM_GOTO = "vacuum_goto"
    VACUUM_CLEAN_SEGMENT = "vacuum_clean_segment"


class XiaomiMiioServiceArgument(StrEnum):
    """Store keys for Xiaomi Miio service arguments."""

    FEATURES = "features"
    SCENE = "scene"
    TIME_PERIOD = "time_period"
    SLOT = "slot"
    TIMEOUT = "timeout"
    MODE = "mode"
    PRICE = "price"
    VELOCITY = "velocity"
    ROTATION = "rotation"
    DURATION = "duration"
    ZONE = "zone"
    REPEATS = "repeats"
    X_COORD = "x_coord"
    Y_COORD = "y_coord"
    SEGMENTS = "segments"


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

    slot = service_call.data.get(XiaomiMiioServiceArgument.SLOT, entity.slot)

    await hass.async_add_executor_job(device.learn, slot)

    timeout = service_call.data.get(XiaomiMiioServiceArgument.TIMEOUT, entity.timeout)

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
        XiaomiMiioService.LIGHT_SET_SCENE,
        entity_domain=LIGHT_DOMAIN,
        schema={
            probatio.Required(XiaomiMiioServiceArgument.SCENE): probatio.All(
                probatio.Coerce(int), probatio.Clamp(min=1, max=6)
            )
        },
        func=_async_service_method("async_set_scene", XiaomiMiioServiceArgument.SCENE),
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        XiaomiMiioService.LIGHT_SET_DELAYED_TURN_OFF,
        entity_domain=LIGHT_DOMAIN,
        schema={
            probatio.Required(
                XiaomiMiioServiceArgument.TIME_PERIOD
            ): cv.positive_time_period
        },
        func=_async_service_method(
            "async_set_delayed_turn_off", XiaomiMiioServiceArgument.TIME_PERIOD
        ),
    )

    for light_service, light_method in (
        (XiaomiMiioService.LIGHT_REMINDER_ON, "async_reminder_on"),
        (XiaomiMiioService.LIGHT_REMINDER_OFF, "async_reminder_off"),
        (XiaomiMiioService.LIGHT_NIGHT_LIGHT_MODE_ON, "async_night_light_mode_on"),
        (XiaomiMiioService.LIGHT_NIGHT_LIGHT_MODE_OFF, "async_night_light_mode_off"),
        (XiaomiMiioService.LIGHT_EYECARE_MODE_ON, "async_eyecare_mode_on"),
        (XiaomiMiioService.LIGHT_EYECARE_MODE_OFF, "async_eyecare_mode_off"),
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
        (XiaomiMiioService.SWITCH_SET_WIFI_LED_ON, "async_set_wifi_led_on"),
        (XiaomiMiioService.SWITCH_SET_WIFI_LED_OFF, "async_set_wifi_led_off"),
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
        XiaomiMiioService.SWITCH_SET_POWER_MODE,
        entity_domain=SWITCH_DOMAIN,
        schema={
            probatio.Required(XiaomiMiioServiceArgument.MODE): probatio.All(
                probatio.In(["green", "normal"])
            )
        },
        func=_async_service_method(
            "async_set_power_mode", XiaomiMiioServiceArgument.MODE
        ),
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        XiaomiMiioService.SWITCH_SET_POWER_PRICE,
        entity_domain=SWITCH_DOMAIN,
        schema={probatio.Required(XiaomiMiioServiceArgument.PRICE): cv.positive_float},
        func=_async_service_method(
            "async_set_power_price", XiaomiMiioServiceArgument.PRICE
        ),
    )

    # Fan Services
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        XiaomiMiioService.FAN_RESET_FILTER,
        entity_domain=FAN_DOMAIN,
        schema=None,
        func=_async_service_method("async_reset_filter"),
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        XiaomiMiioService.FAN_SET_EXTRA_FEATURES,
        entity_domain=FAN_DOMAIN,
        schema={probatio.Required(XiaomiMiioServiceArgument.FEATURES): cv.positive_int},
        func=_async_service_method(
            "async_set_extra_features", XiaomiMiioServiceArgument.FEATURES
        ),
    )

    # Remote Services
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        XiaomiMiioService.REMOTE_LEARN_COMMAND,
        entity_domain=REMOTE_DOMAIN,
        func=_async_remote_learn,
        schema={
            probatio.Optional(
                XiaomiMiioServiceArgument.TIMEOUT, default=10
            ): cv.positive_int,
            probatio.Optional(XiaomiMiioServiceArgument.SLOT, default=1): probatio.All(
                int, probatio.Range(min=1, max=1000000)
            ),
        },
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        XiaomiMiioService.REMOTE_SET_LED_ON,
        entity_domain=REMOTE_DOMAIN,
        func=_async_remote_led_on,
        schema=None,
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        XiaomiMiioService.REMOTE_SET_LED_OFF,
        entity_domain=REMOTE_DOMAIN,
        func=_async_remote_led_off,
        schema=None,
    )

    # Vacuum Services
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        XiaomiMiioService.VACUUM_REMOTE_CONTROL_START,
        entity_domain=VACUUM_DOMAIN,
        schema=None,
        func="async_remote_control_start",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        XiaomiMiioService.VACUUM_REMOTE_CONTROL_STOP,
        entity_domain=VACUUM_DOMAIN,
        schema=None,
        func="async_remote_control_stop",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        XiaomiMiioService.VACUUM_REMOTE_CONTROL_MOVE,
        entity_domain=VACUUM_DOMAIN,
        schema={
            probatio.Optional(XiaomiMiioServiceArgument.VELOCITY): probatio.All(
                probatio.Coerce(float), probatio.Clamp(min=-0.29, max=0.29)
            ),
            probatio.Optional(XiaomiMiioServiceArgument.ROTATION): probatio.All(
                probatio.Coerce(int), probatio.Clamp(min=-179, max=179)
            ),
            probatio.Optional(XiaomiMiioServiceArgument.DURATION): cv.positive_int,
        },
        func="async_remote_control_move",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        XiaomiMiioService.VACUUM_REMOTE_CONTROL_MOVE_STEP,
        entity_domain=VACUUM_DOMAIN,
        schema={
            probatio.Optional(XiaomiMiioServiceArgument.VELOCITY): probatio.All(
                probatio.Coerce(float), probatio.Clamp(min=-0.29, max=0.29)
            ),
            probatio.Optional(XiaomiMiioServiceArgument.ROTATION): probatio.All(
                probatio.Coerce(int), probatio.Clamp(min=-179, max=179)
            ),
            probatio.Optional(XiaomiMiioServiceArgument.DURATION): cv.positive_int,
        },
        func="async_remote_control_move_step",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        XiaomiMiioService.VACUUM_CLEAN_ZONE,
        entity_domain=VACUUM_DOMAIN,
        schema={
            probatio.Required(XiaomiMiioServiceArgument.ZONE): probatio.All(
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
            probatio.Required(XiaomiMiioServiceArgument.REPEATS): probatio.All(
                probatio.Coerce(int), probatio.Clamp(min=1, max=3)
            ),
        },
        func="async_clean_zone",
    )

    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        XiaomiMiioService.VACUUM_GOTO,
        entity_domain=VACUUM_DOMAIN,
        schema={
            probatio.Required(XiaomiMiioServiceArgument.X_COORD): probatio.Coerce(int),
            probatio.Required(XiaomiMiioServiceArgument.Y_COORD): probatio.Coerce(int),
        },
        func="async_goto",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        XiaomiMiioService.VACUUM_CLEAN_SEGMENT,
        entity_domain=VACUUM_DOMAIN,
        schema={
            probatio.Required(XiaomiMiioServiceArgument.SEGMENTS): probatio.Any(
                probatio.Coerce(int), [probatio.Coerce(int)]
            )
        },
        func="async_clean_segment",
    )
