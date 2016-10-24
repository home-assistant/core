"""
iOS push notification platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.ios/
"""
import logging
from datetime import datetime, timezone
import requests

from homeassistant.components import ios

import homeassistant.util.dt as dt_util

from homeassistant.components.notify import (
    ATTR_TARGET, ATTR_TITLE, ATTR_TITLE_DEFAULT, ATTR_MESSAGE,
    ATTR_DATA, BaseNotificationService)

_LOGGER = logging.getLogger(__name__)

PUSH_URL = "https://ios-push.home-assistant.io/push"

DEPENDENCIES = ["ios"]


# pylint: disable=invalid-name
def log_rate_limits(target, resp, level=20):
    """Output rate limit log line at given level."""
    rate_limits = resp["rateLimits"]
    resetsAt = dt_util.parse_datetime(rate_limits["resetsAt"])
    resetsAtTime = resetsAt - datetime.now(timezone.utc)
    rate_limit_msg = ("iOS push notification rate limits for %s: "
                      "%d sent, %d allowed, %d errors, "
                      "resets in %s")
    _LOGGER.log(level, rate_limit_msg,
                ios.device_name_for_push_id(target),
                rate_limits["successful"],
                rate_limits["maximum"], rate_limits["errors"],
                str(resetsAtTime).split(".")[0])


def get_service(hass, config):
    """Get the iOS notification service."""
    if "notify.ios" not in hass.config.components:
        # Need this to enable requirements checking in the app.
        hass.config.components.append("notify.ios")

    return iOSNotificationService()


# pylint: disable=too-few-public-methods, too-many-arguments, invalid-name
class iOSNotificationService(BaseNotificationService):
    """Implement the notification service for iOS."""

    def __init__(self):
        """Initialize the service."""

    @property
    def targets(self):
        """Return a dictionary of registered targets."""
        return ios.devices_with_push()

    def send_message(self, message="", **kwargs):
        """Send a message to the Lambda APNS gateway."""
        data = {ATTR_MESSAGE: message}

        if kwargs.get(ATTR_TITLE) is not None:
            # Remove default title from notifications.
            if kwargs.get(ATTR_TITLE) != ATTR_TITLE_DEFAULT:
                data[ATTR_TITLE] = kwargs.get(ATTR_TITLE)

        targets = kwargs.get(ATTR_TARGET)

        if not targets:
            targets = ios.enabled_push_ids()

        if kwargs.get(ATTR_DATA) is not None:
            data[ATTR_DATA] = kwargs.get(ATTR_DATA)

        for target in targets:
            data[ATTR_TARGET] = target

            req = requests.post(PUSH_URL, json=data, timeout=10)

            if req.status_code != 201:
                fallback_error = req.json().get("errorMessage",
                                                "Unknown error")
                fallback_message = ("Internal server error, "
                                    "please try again later: "
                                    "{}").format(fallback_error)
                message = req.json().get("message", fallback_message)
                if req.status_code == 429:
                    _LOGGER.warning(message)
                    log_rate_limits(target, req.json(), 30)
                else:
                    _LOGGER.error(message)
            else:
                log_rate_limits(target, req.json())
