"""Provides device actions for Mobile App."""
from __future__ import annotations

import logging
import typing

import voluptuous as vol

from homeassistant.components import notify
from homeassistant.components.device_automation import InvalidDeviceAutomationConfig
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_TYPE
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import config_validation as cv, selector, template
from homeassistant.helpers.typing import ConfigType, TemplateVarsType

from .const import (
    ATTR_COMMAND,
    ATTR_INTENT_ACTION,
    ATTR_INTENT_CLASS_NAME,
    ATTR_INTENT_EXTRAS,
    ATTR_INTENT_PACKAGE_NAME,
    ATTR_INTENT_TYPE,
    ATTR_INTENT_URI,
    ATTR_OS_NAME,
    DATA_CONFIG_ENTRIES,
    DOMAIN,
)
from .util import get_notify_service, supports_push, webhook_id_from_device_id

_LOGGER = logging.getLogger(__name__)

NOTIFY_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): "notify",
        vol.Required(notify.ATTR_MESSAGE): cv.template,
        vol.Optional(notify.ATTR_TITLE): cv.template,
        vol.Optional(notify.ATTR_DATA): cv.template_complex,
    }
)

COMMAND_NO_DATA_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.Any(
            [
                "command_stop_tts",
                "command_update_sensors",
                "request_location_update",
                "clear_badge",
                "update_complications",
            ]
        ),
    }
)

COMMAND_ONOFF_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.Any(
            [
                "command_auto_screen_brightness",
                "command_bluetooth",
                "command_ble_transmitter",
                "command_beacon_monitor",
            ]
        ),
        vol.Required(ATTR_COMMAND): vol.Any("turn_off", "turn_on"),
    }
)

COMMAND_ACTIVITY_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): "command_activity",
        vol.Required(ATTR_INTENT_ACTION): cv.template,
        vol.Optional(ATTR_INTENT_URI): cv.template,
        vol.Optional(ATTR_INTENT_TYPE): cv.template,
        vol.Optional(ATTR_INTENT_PACKAGE_NAME): cv.template,
        vol.Optional(ATTR_INTENT_CLASS_NAME): cv.template,
        vol.Optional(ATTR_INTENT_EXTRAS): cv.template,
    }
)

COMMAND_CLEAR_NOTIFICATIONS_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): "clear_notification",
        vol.Required("tag"): cv.template,
    }
)

COMMAND_APP_LOCK_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): "command_app_lock",
        vol.Optional("app_lock_enabled"): cv.boolean,
        vol.Optional("app_lock_timeout"): cv.positive_int,
        vol.Optional("home_bypass_enabled"): cv.boolean,
    }
)

COMMAND_BROADCAST_INTENT_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): "command_broadcast_intent",
        vol.Required(ATTR_INTENT_ACTION): cv.template,
        vol.Required(ATTR_INTENT_PACKAGE_NAME): cv.template,
        vol.Optional(ATTR_INTENT_CLASS_NAME): cv.template,
        vol.Optional(ATTR_INTENT_EXTRAS): cv.template,
    }
)

COMMAND_DND_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): "command_dnd",
        vol.Required(ATTR_COMMAND): vol.Any(
            "alarms_only", "off", "priority_only", "total_silence"
        ),
    }
)

COMMAND_HIGH_ACCURACY_MODE_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): "command_high_accuracy_mode",
        vol.Required(ATTR_COMMAND): vol.Any(
            "turn_off",
            "turn_on",
            "force_off",
            "force_on",
            "high_accuracy_set_update_interval",
        ),
        vol.Optional("high_accuracy_update_interval"): vol.All(
            vol.Coerce(int), vol.Range(min=5)
        ),
    }
)

COMMAND_LAUNCH_APP_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): "command_launch_app",
        vol.Required("package_name"): cv.template,
    }
)

COMMAND_MEDIA_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): "command_media",
        vol.Required("media_command"): vol.Any(
            "fast_forward",
            "next",
            "pause",
            "play",
            "play_pause",
            "previous",
            "rewind",
            "stop",
        ),
        vol.Required("media_package_name"): cv.template,
    }
)

COMMAND_RINGER_MODE_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): "command_ringer_mode",
        vol.Required(ATTR_COMMAND): vol.Any("normal", "silent", "vibrate"),
    }
)

COMMAND_SCREEN_BRIGHTNESS_LEVEL_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): "command_screen_brightness_level",
        vol.Required(ATTR_COMMAND): vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
    }
)

COMMAND_SCREEN_OFF_TIMEOUT_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): "command_screen_off_timeout",
        vol.Required(ATTR_COMMAND): cv.positive_int,
    }
)

COMMAND_SCREEN_ON_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): "command_screen_on",
        vol.Optional(ATTR_COMMAND): str,
    }
)

COMMAND_PERSISTENT_CONNECTION_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): "command_persistent_connection",
        vol.Required("persistent"): vol.Any(
            "always", "home_wifi", "screen_on", "never"
        ),
    }
)

COMMAND_VOLUME_LEVEL_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): "command_volume_level",
        vol.Required(ATTR_COMMAND): cv.positive_int,
        vol.Required("media_stream"): vol.Any(
            "alarm_stream",
            "call_stream",
            "dtmf_stream",
            "music_stream",
            "notification_stream",
            "ring_stream",
            "system_stream",
        ),
    }
)

COMMAND_WEBVIEW_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): "command_webview",
        vol.Required(ATTR_COMMAND): cv.template,
    }
)

COMMAND_REMOVE_CHANNEL_SCHEMA = cv.DEVICE_ACTION_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): "remove_channel",
        vol.Required("channel"): cv.template,
    }
)

ACTION_SCHEMA = vol.Any(
    NOTIFY_SCHEMA,
    COMMAND_NO_DATA_SCHEMA,
    COMMAND_ONOFF_SCHEMA,
    COMMAND_ACTIVITY_SCHEMA,
    COMMAND_CLEAR_NOTIFICATIONS_SCHEMA,
    COMMAND_APP_LOCK_SCHEMA,
    COMMAND_BROADCAST_INTENT_SCHEMA,
    COMMAND_DND_SCHEMA,
    COMMAND_HIGH_ACCURACY_MODE_SCHEMA,
    COMMAND_LAUNCH_APP_SCHEMA,
    COMMAND_MEDIA_SCHEMA,
    COMMAND_RINGER_MODE_SCHEMA,
    COMMAND_SCREEN_BRIGHTNESS_LEVEL_SCHEMA,
    COMMAND_SCREEN_OFF_TIMEOUT_SCHEMA,
    COMMAND_SCREEN_ON_SCHEMA,
    COMMAND_PERSISTENT_CONNECTION_SCHEMA,
    COMMAND_VOLUME_LEVEL_SCHEMA,
    COMMAND_WEBVIEW_SCHEMA,
    COMMAND_REMOVE_CHANNEL_SCHEMA,
)


async def async_get_actions(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device actions for Mobile App devices."""
    webhook_id = webhook_id_from_device_id(hass, device_id)

    if webhook_id is None or not supports_push(hass, webhook_id):
        return []

    actions = [{CONF_DEVICE_ID: device_id, CONF_DOMAIN: DOMAIN, CONF_TYPE: "notify"}]

    config = hass.data[DOMAIN][DATA_CONFIG_ENTRIES][webhook_id]
    os_name = config.data[ATTR_OS_NAME]

    if os_name == "Android":
        actions += [
            {
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: DOMAIN,
                CONF_TYPE: action,
            }
            for action in (
                "command_stop_tts",
                "command_update_sensors",
                "request_location_update",
                "command_auto_screen_brightness",
                "command_bluetooth",
                "command_ble_transmitter",
                "command_beacon_monitor",
                "command_activity",
                "clear_notification",
                "command_app_lock",
                "command_broadcast_intent",
                "command_dnd",
                "command_high_accuracy_mode",
                "command_launch_app",
                "command_media",
                "command_ringer_mode",
                "command_screen_brightness_level",
                "command_screen_off_timeout",
                "command_screen_on",
                "command_persistent_connection",
                "command_volume_level",
                "command_webview",
                "remove_channel",
            )
        ]
    elif os_name == "iOS":
        actions += [
            {
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: DOMAIN,
                CONF_TYPE: action,
            }
            for action in (
                "request_location_update",
                "clear_notification",
                "clear_badge",
                "update_complications",
            )
        ]

    return actions


async def async_call_action_from_config(
    hass: HomeAssistant,
    config: ConfigType,
    variables: TemplateVarsType,
    context: Context | None,
) -> None:
    """Execute a device action."""
    webhook_id = webhook_id_from_device_id(hass, config[CONF_DEVICE_ID])

    if webhook_id is None:
        raise InvalidDeviceAutomationConfig(
            "Unable to resolve webhook ID from the device ID"
        )

    if (service_name := get_notify_service(hass, webhook_id)) is None:
        raise InvalidDeviceAutomationConfig(
            "Unable to find notify service for webhook ID"
        )

    service_data: dict[str, typing.Any] = {notify.ATTR_TARGET: webhook_id}
    service_data[notify.ATTR_DATA] = {}

    if config[CONF_TYPE] == "notify":
        # Render it here because we have access to variables here.
        for key in (notify.ATTR_MESSAGE, notify.ATTR_TITLE, notify.ATTR_DATA):
            if key not in config:
                continue

            value_template = config[key]
            template.attach(hass, value_template)

            try:
                service_data[key] = template.render_complex(value_template, variables)
            except TemplateError as err:
                raise InvalidDeviceAutomationConfig(
                    f"Error rendering {key}: {err}"
                ) from err
    else:
        service_data[notify.ATTR_MESSAGE] = config[CONF_TYPE]

        for key, value_template in config.items():
            if key in (CONF_DEVICE_ID, CONF_DOMAIN, CONF_TYPE):
                continue

            template.attach(hass, value_template)

            try:
                service_data[notify.ATTR_DATA][key] = template.render_complex(
                    value_template, variables
                )
            except TemplateError as err:
                raise InvalidDeviceAutomationConfig(
                    f"Error rendering {key}: {err}"
                ) from err

    _LOGGER.debug(service_data)
    await hass.services.async_call(
        notify.DOMAIN, service_name, service_data, blocking=True, context=context
    )


async def async_get_action_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, vol.Schema]:
    """List action capabilities."""

    cmd = config[CONF_TYPE]

    if cmd in [
        "command_auto_screen_brightness",
        "command_bluetooth",
        "command_ble_transmitter",
        "command_beacon_monitor",
    ]:
        return {
            "extra_fields": vol.Schema(
                {
                    vol.Required(ATTR_COMMAND): selector.SelectSelector(
                        {"options": ["turn_off", "turn_on"]}
                    ),
                }
            )
        }
    if cmd == "command_activity":
        return {
            "extra_fields": vol.Schema(
                {
                    vol.Required("intent_action"): str,
                    vol.Optional("intent_uri"): str,
                    vol.Optional("intent_type"): str,
                    vol.Optional("intent_package_name"): str,
                    vol.Optional("intent_class_name"): str,
                    vol.Optional("intent_extras"): str,
                }
            )
        }
    if cmd == "clear_notification":
        return {
            "extra_fields": vol.Schema(
                {
                    vol.Required("tag"): str,
                }
            )
        }
    if cmd == "command_app_lock":
        return {
            "extra_fields": vol.Schema(
                {
                    vol.Optional("app_lock_enabled"): bool,
                    vol.Optional("app_lock_timeout"): selector.NumberSelector(
                        {"min": 0, "mode": selector.NumberSelectorMode.BOX}
                    ),
                    vol.Optional("home_bypass_enabled"): bool,
                }
            )
        }
    if cmd == "command_broadcast_intent":
        return {
            "extra_fields": vol.Schema(
                {
                    vol.Required(ATTR_INTENT_ACTION): str,
                    vol.Required(ATTR_INTENT_PACKAGE_NAME): str,
                    vol.Optional(ATTR_INTENT_CLASS_NAME): str,
                    vol.Optional(ATTR_INTENT_EXTRAS): str,
                }
            )
        }
    if cmd == "command_dnd":
        return {
            "extra_fields": vol.Schema(
                {
                    vol.Required(ATTR_COMMAND): selector.SelectSelector(
                        {
                            "options": [
                                "alarms_only",
                                "off",
                                "priority_only",
                                "total_silence",
                            ]
                        }
                    ),
                }
            )
        }
    if cmd == "command_high_accuracy_mode":
        return {
            "extra_fields": vol.Schema(
                {
                    vol.Required(ATTR_COMMAND): selector.SelectSelector(
                        {
                            "options": [
                                "turn_off",
                                "turn_on",
                                "force_off",
                                "force_on",
                                "high_accuracy_set_update_interval",
                            ]
                        }
                    ),
                    vol.Optional(
                        "high_accuracy_update_interval"
                    ): selector.NumberSelector(
                        {"min": 5, "mode": selector.NumberSelectorMode.BOX}
                    ),
                }
            )
        }
    if cmd == "command_launch_app":
        return {
            "extra_fields": vol.Schema(
                {
                    vol.Required("package_name"): str,
                }
            )
        }
    if cmd == "command_media":
        return {
            "extra_fields": vol.Schema(
                {
                    vol.Required("media_command"): selector.SelectSelector(
                        {
                            "options": [
                                "fast_forward",
                                "next",
                                "pause",
                                "play",
                                "play_pause",
                                "previous",
                                "rewind",
                                "stop",
                            ]
                        }
                    ),
                    vol.Required("media_package_name"): str,
                }
            )
        }
    if cmd == "command_ringer_mode":
        return {
            "extra_fields": vol.Schema(
                {
                    vol.Required(ATTR_COMMAND): selector.SelectSelector(
                        {"options": ["normal", "silent", "vibrate"]}
                    ),
                }
            )
        }
    if cmd == "command_screen_brightness_level":
        return {
            "extra_fields": vol.Schema(
                {
                    vol.Required(ATTR_COMMAND): selector.NumberSelector(
                        {
                            "min": 0,
                            "max": 255,
                            "mode": selector.NumberSelectorMode.SLIDER,
                        }
                    ),
                }
            )
        }
    if cmd == "command_screen_off_timeout":
        return {
            "extra_fields": vol.Schema(
                {
                    vol.Required(ATTR_COMMAND): selector.NumberSelector(
                        {"min": 0, "mode": selector.NumberSelectorMode.BOX}
                    ),
                }
            )
        }
    if cmd == "command_screen_on":
        return {
            "extra_fields": vol.Schema(
                {
                    vol.Optional(ATTR_COMMAND): str,
                }
            )
        }
    if cmd == "command_persistent_connection":
        return {
            "extra_fields": vol.Schema(
                {
                    vol.Required("persistent"): selector.SelectSelector(
                        {"options": ["always", "home_wifi", "screen_on", "never"]}
                    ),
                }
            )
        }
    if cmd == "command_volume_level":
        return {
            "extra_fields": vol.Schema(
                {
                    vol.Required(ATTR_COMMAND): selector.NumberSelector(
                        {"min": 0, "mode": selector.NumberSelectorMode.BOX}
                    ),
                    vol.Required("media_stream"): selector.SelectSelector(
                        {
                            "options": [
                                "alarm_stream",
                                "call_stream",
                                "dtmf_stream",
                                "music_stream",
                                "notification_stream",
                                "ring_stream",
                                "system_stream",
                            ]
                        }
                    ),
                }
            )
        }
    if cmd == "command_webview":
        return {
            "extra_fields": vol.Schema(
                {
                    vol.Required(ATTR_COMMAND): str,
                }
            )
        }
    if cmd == "remove_channel":
        return {
            "extra_fields": vol.Schema(
                {
                    vol.Required("channel"): str,
                }
            )
        }
    if cmd == "notify":
        return {
            "extra_fields": vol.Schema(
                {
                    vol.Required(notify.ATTR_MESSAGE): str,
                    vol.Optional(notify.ATTR_TITLE): str,
                }
            )
        }

    return {}
