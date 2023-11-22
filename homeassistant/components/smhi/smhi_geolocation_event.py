"""Smhi geolocation event."""
import uuid

from homeassistant.components.geo_location import GeolocationEvent


class SmhiGeolocationEvent(GeolocationEvent):
    """Representation of a Geolocation Event for SMHI."""

    def __init__(
        self,
        name: str,
        latitude: float,
        longitude: float,
        map_icon_url: str,
        card_icon: str,
        state: str,
    ) -> None:
        """Initialize the geolocation event."""
        self._attr_unique_id = str(uuid.uuid4())
        self._attr_source = "smhi_warning"
        self._name = name
        self._latitude = latitude
        self._longitude = longitude
        self._attr_icon = card_icon
        self._state = state
        self._attr_entity_picture = map_icon_url
        self.removed = False

    @property
    def name(self) -> str:
        """Return the name of the event."""
        return self._name

    @property
    def latitude(self) -> float:
        """Return latitude value of the event."""
        return self._latitude

    @property
    def longitude(self) -> float:
        """Return longitude value of the event."""
        return self._longitude

    def remove_self(self) -> None:
        """Mark this entity for removal."""
        if self.hass:
            if not self.removed:
                self.hass.async_create_task(self.async_remove())
                self.removed = True
        else:
            # Handle the case where hass is None, maybe log a warning
            pass
