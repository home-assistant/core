"""Support for mobile_app push notifications."""
from datetime import datetime, timezone
import logging

import requests

from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.components.notify import (
    ATTR_DATA, ATTR_MESSAGE, ATTR_TARGET, ATTR_TITLE, ATTR_TITLE_DEFAULT,
    BaseNotificationService)
from homeassistant.components.mobile_app import push_registrations
from homeassistant.components.mobile_app.const import (
    ATTR_APP_DATA, ATTR_APP_ID, ATTR_APP_NAME, ATTR_APP_VERSION,
    ATTR_DEVICE_NAME, ATTR_MANUFACTURER, ATTR_MODEL, ATTR_OS_NAME,
    ATTR_OS_VERSION, ATTR_PUSH_TOKEN, ATTR_PUSH_URL, DATA_CONFIG_ENTRIES,
    DOMAIN)
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ["mobile_app"]


# pylint: disable=invalid-name
def log_rate_limits(hass, device_name, resp, level=20):
    """Output rate limit log line at given level."""
    rate_limits = resp["rateLimits"]
    resetsAt = dt_util.parse_datetime(rate_limits["resetsAt"])
    resetsAtTime = resetsAt - datetime.now(timezone.utc)
    rate_limit_msg = ("mobile_app push notification rate limits for %s: "
                      "%d sent, %d allowed, %d errors, "
                      "resets in %s")
    _LOGGER.log(level, rate_limit_msg,
                device_name,
                rate_limits["successful"],
                rate_limits["maximum"], rate_limits["errors"],
                str(resetsAtTime).split(".")[0])


def get_service(hass, config, discovery_info=None):
    """Get the mobile_app notification service."""
    return MobileAppNotificationService()


class MobileAppNotificationService(BaseNotificationService):
    """Implement the notification service for mobile_app."""

    def __init__(self):
        """Initialize the service."""

    @property
    def targets(self):
        """Return a dictionary of registered targets."""
        return push_registrations(self.hass)

    def send_message(self, message="", **kwargs):
        """Send a message to the Lambda APNS gateway."""
        data = {ATTR_MESSAGE: message}

        if kwargs.get(ATTR_TITLE) is not None:
            # Remove default title from notifications.
            if kwargs.get(ATTR_TITLE) != ATTR_TITLE_DEFAULT:
                data[ATTR_TITLE] = kwargs.get(ATTR_TITLE)

        targets = kwargs.get(ATTR_TARGET)

        if not targets:
            targets = push_registrations(self.hass)

        if kwargs.get(ATTR_DATA) is not None:
            data[ATTR_DATA] = kwargs.get(ATTR_DATA)

        for target in targets:

            entry = self.hass.data[DOMAIN][DATA_CONFIG_ENTRIES][target]
            entry_data = entry.data

            app_data = entry_data[ATTR_APP_DATA]
            push_token = app_data[ATTR_PUSH_TOKEN]
            push_url = app_data[ATTR_PUSH_URL]

            data[ATTR_PUSH_TOKEN] = push_token

            reg_info = {
                ATTR_APP_DATA: app_data,
                ATTR_APP_ID: entry_data[ATTR_APP_ID],
                ATTR_APP_NAME: entry_data[ATTR_APP_NAME],
                ATTR_APP_VERSION: entry_data[ATTR_APP_VERSION],
                ATTR_DEVICE_NAME: entry_data[ATTR_DEVICE_NAME],
                ATTR_MANUFACTURER: entry_data[ATTR_MANUFACTURER],
                ATTR_MODEL: entry_data[ATTR_MODEL],
                ATTR_OS_NAME: entry_data[ATTR_OS_NAME],
                CONF_WEBHOOK_ID: entry_data[CONF_WEBHOOK_ID],
            }
            if ATTR_OS_VERSION in entry_data:
                reg_info[ATTR_OS_VERSION] = entry_data[ATTR_OS_VERSION]

            data['registration_info'] = reg_info

            req = requests.post(push_url, json=data, timeout=10)

            if req.status_code != 201:
                fallback_error = req.json().get("errorMessage",
                                                "Unknown error")
                fallback_message = ("Internal server error, "
                                    "please try again later: "
                                    "{}").format(fallback_error)
                message = req.json().get("message", fallback_message)
                if req.status_code == 429:
                    _LOGGER.warning(message)
                    log_rate_limits(self.hass, entry_data[ATTR_DEVICE_NAME],
                                    req.json(), 30)
                else:
                    _LOGGER.error(message)
            else:
                log_rate_limits(self.hass, entry_data[ATTR_DEVICE_NAME],
                                req.json())
