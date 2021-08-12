"""Type definitions for Tractive integration."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import SensorEntityDescription

from .const import DOMAIN


@dataclass
class TractiveSensorEntityDescription(SensorEntityDescription):
    """Class describing Tractive sensor entities."""

    event_type: str | None = None
    attributes: tuple = ()


class TractiveEntity:
    """Tractive entity class."""

    def __init__(self, user_id, trackable, tracker_details):
        """Initialize tracker entity."""
        self._device_info = {
            "identifiers": {(DOMAIN, tracker_details["_id"])},
            "name": f"Tractive ({tracker_details['_id']})",
            "manufacturer": "Tractive GmbH",
            "sw_version": tracker_details["fw_version"],
            "model": tracker_details["model_number"],
        }
        self._user_id = user_id
        self._tracker_id = tracker_details["_id"]
        self._trackable = trackable
