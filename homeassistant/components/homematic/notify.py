"""Notification support for Homematic."""

from typing import Any, override

import probatio

from homeassistant.components.notify import (
    ATTR_DATA,
    PLATFORM_SCHEMA as NOTIFY_PLATFORM_SCHEMA,
    BaseNotificationService,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, template as template_helper
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
        probatio.Required(ATTR_ADDRESS): probatio.All(cv.string, probatio.Upper),
        probatio.Required(ATTR_CHANNEL): probatio.Coerce(int),
        probatio.Required(ATTR_PARAM): probatio.All(cv.string, probatio.Upper),
        probatio.Required(ATTR_VALUE): cv.match_all,
        probatio.Optional(ATTR_INTERFACE): cv.string,
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

    @override
    def send_message(self, message: str = "", **kwargs: Any) -> None:
        """Send a notification to the device."""
        data = {**self.data, **kwargs.get(ATTR_DATA, {})}

        if data.get(ATTR_VALUE) is not None:
            templ = template_helper.Template(self.data[ATTR_VALUE], self.hass)
            data[ATTR_VALUE] = template_helper.render_complex(templ, None)

        self.hass.services.call(DOMAIN, SERVICE_SET_DEVICE_VALUE, data)
