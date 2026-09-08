"""Xiaomi services."""

import asyncio
import logging

import voluptuous as vol

from homeassistant.components.vacuum import DOMAIN as VACUUM_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, ATTR_MODE
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv, service

from .const import (
    ATTR_SCENE,
    DOMAIN,
    FAN_DATA_KEY,
    LIGHT_DATA_KEY,
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
    SWITCH_DATA_KEY,
)
from .typing import ServiceMethodDetails

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
XIAOMI_MIIO_SERVICE_SCHEMA = vol.Schema({vol.Optional(ATTR_ENTITY_ID): cv.entity_ids})
SERVICE_SCHEMA_SET_SCENE = XIAOMI_MIIO_SERVICE_SCHEMA.extend(
    {vol.Required(ATTR_SCENE): vol.All(vol.Coerce(int), vol.Clamp(min=1, max=6))}
)
SERVICE_SCHEMA_SET_DELAYED_TURN_OFF = XIAOMI_MIIO_SERVICE_SCHEMA.extend(
    {vol.Required(ATTR_TIME_PERIOD): cv.positive_time_period}
)
LIGHT_SERVICE_TO_METHOD = {
    SERVICE_SET_DELAYED_TURN_OFF: ServiceMethodDetails(
        method="async_set_delayed_turn_off",
        schema=SERVICE_SCHEMA_SET_DELAYED_TURN_OFF,
    ),
    SERVICE_SET_SCENE: ServiceMethodDetails(
        method="async_set_scene",
        schema=SERVICE_SCHEMA_SET_SCENE,
    ),
    SERVICE_REMINDER_ON: ServiceMethodDetails(method="async_reminder_on"),
    SERVICE_REMINDER_OFF: ServiceMethodDetails(method="async_reminder_off"),
    SERVICE_NIGHT_LIGHT_MODE_ON: ServiceMethodDetails(
        method="async_night_light_mode_on"
    ),
    SERVICE_NIGHT_LIGHT_MODE_OFF: ServiceMethodDetails(
        method="async_night_light_mode_off"
    ),
    SERVICE_EYECARE_MODE_ON: ServiceMethodDetails(method="async_eyecare_mode_on"),
    SERVICE_EYECARE_MODE_OFF: ServiceMethodDetails(method="async_eyecare_mode_off"),
}

# Switch Services
ATTR_PRICE = "price"
SWITCH_SERVICE_SCHEMA = vol.Schema({vol.Optional(ATTR_ENTITY_ID): cv.entity_ids})
SWITCH_SERVICE_SCHEMA_POWER_MODE = SWITCH_SERVICE_SCHEMA.extend(
    {vol.Required(ATTR_MODE): vol.All(vol.In(["green", "normal"]))}
)
SWITCH_SERVICE_SCHEMA_POWER_PRICE = SWITCH_SERVICE_SCHEMA.extend(
    {vol.Required(ATTR_PRICE): cv.positive_float}
)
SWITCH_SERVICE_TO_METHOD = {
    SERVICE_SET_WIFI_LED_ON: ServiceMethodDetails(method="async_set_wifi_led_on"),
    SERVICE_SET_WIFI_LED_OFF: ServiceMethodDetails(method="async_set_wifi_led_off"),
    SERVICE_SET_POWER_MODE: ServiceMethodDetails(
        method="async_set_power_mode",
        schema=SWITCH_SERVICE_SCHEMA_POWER_MODE,
    ),
    SERVICE_SET_POWER_PRICE: ServiceMethodDetails(
        method="async_set_power_price",
        schema=SWITCH_SERVICE_SCHEMA_POWER_PRICE,
    ),
}

# Fan Services
ATTR_FEATURES = "features"
FAN_SERVICE_SCHEMA = vol.Schema({vol.Optional(ATTR_ENTITY_ID): cv.entity_ids})
FAN_SERVICE_SCHEMA_EXTRA_FEATURES = FAN_SERVICE_SCHEMA.extend(
    {vol.Required(ATTR_FEATURES): cv.positive_int}
)
FAN_SERVICE_TO_METHOD = {
    SERVICE_RESET_FILTER: ServiceMethodDetails(method="async_reset_filter"),
    SERVICE_SET_EXTRA_FEATURES: ServiceMethodDetails(
        method="async_set_extra_features",
        schema=FAN_SERVICE_SCHEMA_EXTRA_FEATURES,
    ),
}


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services."""

    _async_setup_fan_services(hass)
    _async_setup_light_services(hass)
    _async_setup_switch_services(hass)

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


def _async_setup_light_services(hass: HomeAssistant) -> None:
    """Set up Xiaomi Miio light services."""
    hass.data.setdefault(LIGHT_DATA_KEY, {})

    async def async_service_handler(call: ServiceCall) -> None:
        """Map services to methods on Xiaomi Philips Lights."""
        method = LIGHT_SERVICE_TO_METHOD[call.service]
        params = {
            key: value for key, value in call.data.items() if key != ATTR_ENTITY_ID
        }
        if entity_ids := call.data.get(ATTR_ENTITY_ID):
            target_devices = [
                dev
                for dev in hass.data[LIGHT_DATA_KEY].values()
                if dev.entity_id in entity_ids
            ]
        else:
            target_devices = hass.data[LIGHT_DATA_KEY].values()

        update_tasks = []
        for target_device in target_devices:
            if not hasattr(target_device, method.method):
                continue
            await getattr(target_device, method.method)(**params)
            update_tasks.append(
                asyncio.create_task(target_device.async_update_ha_state(True))
            )

        if update_tasks:
            await asyncio.wait(update_tasks)

    for xiaomi_miio_service, method in LIGHT_SERVICE_TO_METHOD.items():
        schema = method.schema or XIAOMI_MIIO_SERVICE_SCHEMA
        hass.services.async_register(
            DOMAIN, xiaomi_miio_service, async_service_handler, schema=schema
        )


def _async_setup_switch_services(hass: HomeAssistant) -> None:
    """Set up Xiaomi Miio switch services."""
    hass.data.setdefault(SWITCH_DATA_KEY, {})

    async def async_service_handler(call: ServiceCall) -> None:
        """Map services to methods on XiaomiPlugGenericSwitch."""
        method = SWITCH_SERVICE_TO_METHOD[call.service]
        params = {
            key: value for key, value in call.data.items() if key != ATTR_ENTITY_ID
        }
        if entity_ids := call.data.get(ATTR_ENTITY_ID):
            devices = [
                device
                for device in hass.data[SWITCH_DATA_KEY].values()
                if device.entity_id in entity_ids
            ]
        else:
            devices = hass.data[SWITCH_DATA_KEY].values()

        update_tasks = []
        for device in devices:
            if not hasattr(device, method.method):
                continue
            await getattr(device, method.method)(**params)
            update_tasks.append(asyncio.create_task(device.async_update_ha_state(True)))

        if update_tasks:
            await asyncio.wait(update_tasks)

    for plug_service, method in SWITCH_SERVICE_TO_METHOD.items():
        schema = method.schema or SWITCH_SERVICE_SCHEMA
        hass.services.async_register(
            DOMAIN, plug_service, async_service_handler, schema=schema
        )


def _async_setup_fan_services(hass: HomeAssistant) -> None:
    """Set up Xiaomi Miio fan services."""
    hass.data.setdefault(FAN_DATA_KEY, {})

    async def async_service_handler(call: ServiceCall) -> None:
        """Map services to methods on XiaomiAirPurifier."""
        method = FAN_SERVICE_TO_METHOD[call.service]
        params = {
            key: value for key, value in call.data.items() if key != ATTR_ENTITY_ID
        }
        if entity_ids := call.data.get(ATTR_ENTITY_ID):
            filtered_entities = [
                entity
                for entity in hass.data[FAN_DATA_KEY].values()
                if entity.entity_id in entity_ids
            ]
        else:
            filtered_entities = hass.data[FAN_DATA_KEY].values()

        update_tasks = []

        for entity in filtered_entities:
            entity_method = getattr(entity, method.method, None)
            if not entity_method:
                continue
            await entity_method(**params)
            update_tasks.append(asyncio.create_task(entity.async_update_ha_state(True)))

        if update_tasks:
            await asyncio.wait(update_tasks)

    for air_purifier_service, method in FAN_SERVICE_TO_METHOD.items():
        schema = method.schema or FAN_SERVICE_SCHEMA
        hass.services.async_register(
            DOMAIN, air_purifier_service, async_service_handler, schema=schema
        )
