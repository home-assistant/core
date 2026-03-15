"""Support for Matrix notifications."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_MESSAGE,
    ATTR_TARGET,
    PLATFORM_SCHEMA as NOTIFY_PLATFORM_SCHEMA,
    BaseNotificationService,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import RoomAnyID
from .const import CONF_CONFIG_ENTRY_ID, CONF_ROOMS_REGEX, DOMAIN, SERVICE_SEND_MESSAGE

CONF_DEFAULT_ROOM = "default_room"

PLATFORM_SCHEMA = NOTIFY_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_DEFAULT_ROOM): cv.matches_regex(CONF_ROOMS_REGEX),
        vol.Required(CONF_CONFIG_ENTRY_ID): cv.string,
    }
)


def get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> MatrixNotificationService:
    """Get the Matrix notification service."""
    return MatrixNotificationService(
        config[CONF_DEFAULT_ROOM], config[CONF_CONFIG_ENTRY_ID]
    )


class MatrixNotificationService(BaseNotificationService):
    """Send notifications to a Matrix room."""

    def __init__(self, default_room: RoomAnyID, config_entry_id: str) -> None:
        """Set up the Matrix notification service."""
        self._default_room = default_room
        self._config_entry_id = config_entry_id

    def send_message(self, message: str = "", **kwargs: Any) -> None:
        """Send the message to the Matrix server."""
        target_rooms: list[RoomAnyID] = kwargs.get(ATTR_TARGET) or [self._default_room]
        service_data = {
            ATTR_TARGET: target_rooms,
            ATTR_MESSAGE: message,
            CONF_CONFIG_ENTRY_ID: self._config_entry_id,
        }
        if (data := kwargs.get(ATTR_DATA)) is not None:
            service_data[ATTR_DATA] = data
        self.hass.services.call(DOMAIN, SERVICE_SEND_MESSAGE, service_data=service_data)
