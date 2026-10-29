"""Base entity for the Geolocation platform."""

from typing import Any, final, override

from propcache.api import cached_property

from homeassistant.const import EntityStateAttribute
from homeassistant.helpers.entity import Entity

from .const import GeolocationEntityStateAttribute

CACHED_PROPERTIES_WITH_ATTR_ = {
    "source",
    "distance",
    "latitude",
    "longitude",
}


class GeolocationEvent(Entity, cached_properties=CACHED_PROPERTIES_WITH_ATTR_):
    """Base class for an external event with an associated geolocation."""

    # Entity Properties
    _attr_source: str
    _attr_distance: float | None = None
    _attr_latitude: float | None = None
    _attr_longitude: float | None = None

    @final
    @property
    @override
    def state(self) -> float | None:
        """Return the state of the sensor."""
        if self.distance is not None:
            return round(self.distance, 1)
        return None

    @cached_property
    def source(self) -> str:
        """Return source value of this external event."""
        return self._attr_source

    @cached_property
    def distance(self) -> float | None:
        """Return distance value of this external event."""
        return self._attr_distance

    @cached_property
    def latitude(self) -> float | None:
        """Return latitude value of this external event."""
        return self._attr_latitude

    @cached_property
    def longitude(self) -> float | None:
        """Return longitude value of this external event."""
        return self._attr_longitude

    @final
    @property
    @override
    def state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of this external event."""
        data: dict[str, Any] = {GeolocationEntityStateAttribute.SOURCE: self.source}
        if self.latitude is not None:
            data[EntityStateAttribute.LATITUDE] = round(self.latitude, 5)
        if self.longitude is not None:
            data[EntityStateAttribute.LONGITUDE] = round(self.longitude, 5)
        return data
