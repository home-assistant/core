"""Simplepush notification service."""
from __future__ import annotations

import logging
from typing import Any

from simplepush import BadRequest, FeedbackActionTimeout, UnknownError, async_send

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    PLATFORM_SCHEMA as BASE_PLATFORM_SCHEMA,
    BaseNotificationService,
)
from homeassistant.const import CONF_EVENT, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    ATTR_ACTIONS,
    ATTR_ATTACHMENTS,
    ATTR_EVENT,
    ATTR_FEEDBACK_ACTION_TIMEOUT,
    CONF_DEVICE_KEY,
    CONF_SALT,
    DOMAIN,
    EVENT_ACTION_TRIGGERED,
)

# Configuring Simplepush under the notify has been removed in 2022.9.0
PLATFORM_SCHEMA = BASE_PLATFORM_SCHEMA

_LOGGER = logging.getLogger(__name__)


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> SimplePushNotificationService | None:
    """Get the Simplepush notification service."""
    if discovery_info is None:
        async_create_issue(
            hass,
            DOMAIN,
            "removed_yaml",
            breaks_in_ha_version="2022.9.0",
            is_fixable=False,
            severity=IssueSeverity.WARNING,
            translation_key="removed_yaml",
        )
        return None

    return SimplePushNotificationService(hass, discovery_info)


class SimplePushNotificationService(BaseNotificationService):
    """Implementation of the notification service for Simplepush."""

    def __init__(self, hass: HomeAssistant, config: dict[str, Any]) -> None:
        """Initialize the Simplepush notification service."""
        self.hass = hass
        self.session = async_get_clientsession(hass)
        self._device_key: str = config[CONF_DEVICE_KEY]
        self._event: str | None = config.get(CONF_EVENT)
        self._password: str | None = config.get(CONF_PASSWORD)
        self._salt: str | None = config.get(CONF_SALT)

    async def async_send_message(self, message: str, **kwargs: Any) -> None:
        """Send a message to a Simplepush user."""
        title = kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)

        actions = None
        action_ids = {}
        attachments = None
        # event can now be passed in the service data
        event = None
        feedback_action_timeout = None

        if data := kwargs.get(ATTR_DATA):
            event = data.get(ATTR_EVENT)

            actions_data = data.get(ATTR_ACTIONS)
            if isinstance(actions_data, list) and actions_data:
                actions = []
                for action in actions_data:
                    if "action" in action and "url" in action:
                        actions.append({"name": action["action"], "url": action["url"]})
                    elif "action" in action:
                        actions.append(action["action"])
                        if "id" in action:
                            action_ids.update({action["action"]: action["id"]})

                try:
                    feedback_action_timeout = int(
                        data.get(ATTR_FEEDBACK_ACTION_TIMEOUT)
                    )
                except (ValueError, TypeError):
                    feedback_action_timeout = 60

            attachments_data = data.get(ATTR_ATTACHMENTS)
            if isinstance(attachments_data, list) and attachments_data:
                attachments = []
                for attachment in attachments_data:
                    if "attachment" in attachment and "thumbnail" in attachment:
                        attachments.append(
                            {
                                "video": attachment["attachment"],
                                "thumbnail": attachment["thumbnail"],
                            }
                        )
                    elif "attachment" in attachment:
                        attachments.append(attachment["attachment"])

        # use event from config until YAML config is removed
        event = event or self._event

        def feedback_action_callback(
            action_selected, action_selected_at, action_delivered_at, feedback_id
        ):
            payload = {
                "action_selected": action_selected,
                "action_selected_at": action_selected_at,
                "action_delivered_at": action_delivered_at,
                "feedback_id": feedback_id,
            }

            if action_selected in action_ids:
                payload.update({"id": action_ids[action_selected]})

            self.hass.bus.async_fire(EVENT_ACTION_TRIGGERED, payload)

        try:
            if self._password:
                self.hass.async_create_task(
                    async_send(
                        key=self._device_key,
                        password=self._password,
                        salt=self._salt,
                        title=title,
                        message=message,
                        actions=actions,
                        attachments=attachments,
                        event=event,
                        feedback_callback=feedback_action_callback,
                        feedback_callback_timeout=feedback_action_timeout,
                        aiohttp_session=self.session,
                    )
                )
            else:
                self.hass.async_create_task(
                    async_send(
                        key=self._device_key,
                        title=title,
                        message=message,
                        actions=actions,
                        attachments=attachments,
                        event=event,
                        feedback_callback=feedback_action_callback,
                        feedback_callback_timeout=feedback_action_timeout,
                        aiohttp_session=self.session,
                    )
                )

        except BadRequest:
            _LOGGER.error("Bad request. Title or message are too long")
        except UnknownError:
            _LOGGER.error("Failed to send the notification")
        except FeedbackActionTimeout:
            _LOGGER.error("Feedback action timed out")
