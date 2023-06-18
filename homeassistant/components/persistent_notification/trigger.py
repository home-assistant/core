"""Offer persistent_notifications triggered automation rules."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.const import CONF_PLATFORM
from homeassistant.core import CALLBACK_TYPE, HassJob, HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.trigger import TriggerActionType, TriggerData, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from . import Notification, UpdateType, async_register_callback

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ("persistent_notification",)

CONF_NOTIFICATION_ID = "notification_id"
CONF_UPDATE_TYPE = "update_type"

TRIGGER_SCHEMA = cv.TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_PLATFORM): "persistent_notification",
        vol.Optional(CONF_NOTIFICATION_ID): str,
        vol.Optional(CONF_UPDATE_TYPE): vol.All(
            cv.ensure_list, [vol.Coerce(UpdateType)]
        ),
    }
)


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Listen for state changes based on configuration."""
    trigger_data: TriggerData = trigger_info["trigger_data"]
    job = HassJob(action)

    persistent_notification_id = config.get(CONF_NOTIFICATION_ID)
    persistent_notification_update_types = config.get(CONF_UPDATE_TYPE)

    @callback
    def persistent_notification_listener(
        update_type: UpdateType, notifications: dict[str, Notification]
    ) -> None:
        """Listen for persistent_notification updates."""

        for notification in list(notifications.values()):
            if (
                persistent_notification_id is None
                or notification[CONF_NOTIFICATION_ID] == persistent_notification_id  # type: ignore[literal-required]
            ) and (
                persistent_notification_update_types is None
                or update_type in persistent_notification_update_types
            ):
                hass.async_run_hass_job(
                    job,
                    {
                        "trigger": {
                            **trigger_data,  # type: ignore[arg-type]  # https://github.com/python/mypy/issues/9117
                            "platform": "persistent_notification",
                            "update_type": update_type,
                            "notification": notification,
                        }
                    },
                )

    _LOGGER.debug(
        "Attaching persistent_notification trigger for ID: '%s', update_types: %s",
        persistent_notification_id,
        persistent_notification_update_types,
    )

    return async_register_callback(hass, persistent_notification_listener)
