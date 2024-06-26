"""Notification support for Homematic."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_DATA,
    PLATFORM_SCHEMA as NOTIFY_PLATFORM_SCHEMA,
    BaseNotificationService,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
import homeassistant.helpers.template as template_helper
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    ATTR_ADDRESS,
    ATTR_CHANNEL,
    ATTR_INTERFACE,
    ATTR_PARAM,
    ATTR_VALUE,
    DOMAIN,
    SERVICE_SET_DEVICE_VALUE,
)

PLATFORM_SCHEMA = NOTIFY_PLATFORM_SCHEMA.extend(
    {
        vol.Required(ATTR_ADDRESS): vol.All(cv.string, vol.Upper),
        vol.Required(ATTR_CHANNEL): vol.Coerce(int),
        vol.Required(ATTR_PARAM): vol.All(cv.string, vol.Upper),
        vol.Required(ATTR_VALUE): cv.match_all,
        vol.Optional(ATTR_INTERFACE): cv.string,
    }
)


def get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> HomematicNotificationService:
    """Get the Homematic notification service."""
    data = {
        ATTR_ADDRESS: config[ATTR_ADDRESS],
        ATTR_CHANNEL: config[ATTR_CHANNEL],
        ATTR_PARAM: config[ATTR_PARAM],
        ATTR_VALUE: config[ATTR_VALUE],
    }
    if ATTR_INTERFACE in config:
        data[ATTR_INTERFACE] = config[ATTR_INTERFACE]

    return HomematicNotificationService(hass, data)


class HomematicNotificationService(BaseNotificationService):
    """Implement the notification service for Homematic."""

    def __init__(self, hass, data):
        """Initialize the service."""
        self.hass = hass
        self.data = data

    def send_message(self, message="", **kwargs):
        """Send a notification to the device."""
        data = {**self.data, **kwargs.get(ATTR_DATA, {})}

        if data.get(ATTR_VALUE) is not None:
            templ = template_helper.Template(self.data[ATTR_VALUE], self.hass)
            data[ATTR_VALUE] = template_helper.render_complex(templ, None)

        self.hass.services.call(DOMAIN, SERVICE_SET_DEVICE_VALUE, data)
