"""A entity class for Tractive integration."""

from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class TractiveEntity(Entity):
    """Tractive entity class."""

    def __init__(self, user_id, trackable, tracker_details):
        """Initialize tracker entity."""
        self._attr_device_info = {
            "identifiers": {(DOMAIN, tracker_details["_id"])},
            "name": f"Tractive ({tracker_details['_id']})",
            "manufacturer": "Tractive GmbH",
            "sw_version": tracker_details["fw_version"],
            "model": tracker_details["model_number"],
        }
        self._user_id = user_id
        self._tracker_id = tracker_details["_id"]
        self._trackable = trackable
