"""Support for iOS push notifications."""
import logging

import requests

from homeassistant.components import ios
from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_MESSAGE,
    ATTR_TARGET,
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    BaseNotificationService,
)
from homeassistant.const import HTTP_CREATED, HTTP_TOO_MANY_REQUESTS
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

PUSH_URL = "https://ios-push.home-assistant.io/push"


# pylint: disable=invalid-name
def log_rate_limits(hass, target, resp, level=20):
    """Output rate limit log line at given level."""
    rate_limits = resp["rateLimits"]
    resetsAt = dt_util.parse_datetime(rate_limits["resetsAt"])
    resetsAtTime = resetsAt - dt_util.utcnow()
    rate_limit_msg = (
        "iOS push notification rate limits for %s: "
        "%d sent, %d allowed, %d errors, "
        "resets in %s"
    )
    _LOGGER.log(
        level,
        rate_limit_msg,
        ios.device_name_for_push_id(hass, target),
        rate_limits["successful"],
        rate_limits["maximum"],
        rate_limits["errors"],
        str(resetsAtTime).split(".", maxsplit=1)[0],
    )


def get_service(hass, config, discovery_info=None):
    """Get the iOS notification service."""
    if "notify.ios" not in hass.config.components:
        # Need this to enable requirements checking in the app.
        hass.config.components.add("notify.ios")

    if not ios.devices_with_push(hass):
        return None

    return iOSNotificationService()


class iOSNotificationService(BaseNotificationService):
    """Implement the notification service for iOS."""

    def __init__(self):
        """Initialize the service."""

    @property
    def targets(self):
        """Return a dictionary of registered targets."""
        return ios.devices_with_push(self.hass)

    def send_message(self, message="", **kwargs):
        """Send a message to the Lambda APNS gateway."""
        data = {ATTR_MESSAGE: message}

        # Remove default title from notifications.
        if (
            kwargs.get(ATTR_TITLE) is not None
            and kwargs.get(ATTR_TITLE) != ATTR_TITLE_DEFAULT
        ):
            data[ATTR_TITLE] = kwargs.get(ATTR_TITLE)

        targets = kwargs.get(ATTR_TARGET)

        if not targets:
            targets = ios.enabled_push_ids(self.hass)

        if kwargs.get(ATTR_DATA) is not None:
            data[ATTR_DATA] = kwargs.get(ATTR_DATA)

        for target in targets:
            if target not in ios.enabled_push_ids(self.hass):
                _LOGGER.error("The target (%s) does not exist in .ios.conf", targets)
                return

            data[ATTR_TARGET] = target

            req = requests.post(PUSH_URL, json=data, timeout=10)

            if req.status_code != HTTP_CREATED:
                fallback_error = req.json().get("errorMessage", "Unknown error")
                fallback_message = (
                    f"Internal server error, please try again later: {fallback_error}"
                )
                message = req.json().get("message", fallback_message)
                if req.status_code == HTTP_TOO_MANY_REQUESTS:
                    _LOGGER.warning(message)
                    log_rate_limits(self.hass, target, req.json(), 30)
                else:
                    _LOGGER.error(message)
            else:
                log_rate_limits(self.hass, target, req.json())
