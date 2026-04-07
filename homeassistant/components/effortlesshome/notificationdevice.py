from __future__ import annotations

import json
import logging
from typing import Optional, List, Dict, Any

from homeassistant.helpers.entity import Entity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.restore_state import RestoreEntity

_LOGGER = logging.getLogger(__name__)


class effortlesshomenotificationdevice(RestoreEntity):
    """Entity representing a push notification device (phone, tablet, etc.)."""

    def __init__(self, hass: Optional[HomeAssistant], token: str, name: str, platform: str):
        self.hass = hass
        self._attr_unique_id = name
        self._attr_name = name
        self._platform = platform
        self._state = "available"
        self._token = token

    # ---- Home Assistant standard properties ----
    @property
    def state(self) -> str:
        """Return the state (usually 'available')."""
        return self._state

    @property
    def DeviceToken(self) -> str:
        """Return the token."""
        return self._token

    @DeviceToken.setter
    def DeviceToken(self, value: str) -> None:
        """Set the token."""
        self._token = value

    @property
    def Name(self) -> str:
        """Return the name."""
        return self._attr_name

    @property
    def Platform(self) -> str:
        """Return the platform."""
        return self._platform

    @Platform.setter
    def Platform(self, value: str) -> None:
        """Set the platform."""
        self._platform = value

    @property
    def unique_id(self) -> str:
        """Return the unique ID."""
        return self._attr_unique_id

    # ---- JSON serialization helpers ----
    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serializable dictionary."""
        return {
            "name": self._attr_name,
            "unique_id": self._attr_unique_id,
            "platform": self._platform,
            "state": self._state,
            "token": self._token,
        }

    def to_json(self) -> str:
        """Return a JSON string representation."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "effortlesshomenotificationdevice":
        """Reconstruct a device from a dict (hass optional)."""
        # Note: hass may be injected later after reload
        return cls(
            hass=None,
            token=data.get("token", ""),
            name=data.get("name", ""),
            platform=data.get("platform", ""),
        )

    def __repr__(self):
        return f"<EffortlessHomeNotificationDevice name={self._attr_name!r} platform={self._platform!r}>"
