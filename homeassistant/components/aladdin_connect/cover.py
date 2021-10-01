"""Platform for the Aladdin Connect cover component."""
from __future__ import annotations

import logging
from typing import Any, Final

from aladdin_connect import AladdinConnectClient
import voluptuous as vol

from homeassistant.components.cover import (
    DEVICE_CLASS_GARAGE,
    PLATFORM_SCHEMA as BASE_PLATFORM_SCHEMA,
    CoverEntity,
)
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPENING,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import NOTIFICATION_ID, NOTIFICATION_TITLE, STATES_MAP, SUPPORTED_FEATURES
from .model import DoorDevice

_LOGGER: Final = logging.getLogger(__name__)

PLATFORM_SCHEMA: Final = BASE_PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_USERNAME): cv.string, vol.Required(CONF_PASSWORD): cv.string}
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Aladdin Connect platform."""

    username: str = config[CONF_USERNAME]
    password: str = config[CONF_PASSWORD]
    acc = AladdinConnectClient(username, password)

    try:
        if not acc.login():
            raise ValueError("Username or Password is incorrect")
        add_entities(
            (AladdinDevice(acc, door) for door in acc.get_doors()),
            update_before_add=True,
        )
    except (TypeError, KeyError, NameError, ValueError) as ex:
        _LOGGER.error("%s", ex)
        hass.components.persistent_notification.create(
            "Error: {ex}<br />You will need to restart hass after fixing.",
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID,
        )


class AladdinDevice(CoverEntity):
    """Representation of Aladdin Connect cover."""

    _attr_device_class = DEVICE_CLASS_GARAGE
    _attr_supported_features = SUPPORTED_FEATURES

    def __init__(self, acc: AladdinConnectClient, device: DoorDevice) -> None:
        """Initialize the cover."""
        self._acc = acc
        self._device_id = device["device_id"]
        self._number = device["door_number"]
        self._attr_name = device["name"]
        self._attr_unique_id = f"{self._device_id}-{self._number}"

    def close_cover(self, **kwargs: Any) -> None:
        """Issue close command to cover."""
        self._acc.close_door(self._device_id, self._number)

    def open_cover(self, **kwargs: Any) -> None:
        """Issue open command to cover."""
        self._acc.open_door(self._device_id, self._number)

    def update(self) -> None:
        """Update status of cover."""
        status = STATES_MAP.get(
            self._acc.get_door_status(self._device_id, self._number)
        )
        self._attr_is_opening = status == STATE_OPENING
        self._attr_is_closing = status == STATE_CLOSING
        self._attr_is_closed = None if status is None else status == STATE_CLOSED
