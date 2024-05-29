"""Support for Geolocation."""

from __future__ import annotations

from datetime import timedelta
from functools import cached_property
import logging
from typing import Any, final

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_validation import (  # noqa: F401
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

ATTR_DISTANCE = "distance"
ATTR_SOURCE = "source"

DOMAIN = "geo_location"

ENTITY_ID_FORMAT = DOMAIN + ".{}"

SCAN_INTERVAL = timedelta(seconds=60)

# mypy: disallow-any-generics


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Geolocation component."""
    component = hass.data[DOMAIN] = EntityComponent[GeolocationEvent](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    await component.async_setup(config)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    component: EntityComponent[GeolocationEvent] = hass.data[DOMAIN]
    return await component.async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    component: EntityComponent[GeolocationEvent] = hass.data[DOMAIN]
    return await component.async_unload_entry(entry)


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
    def state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of this external event."""
        data: dict[str, Any] = {ATTR_SOURCE: self.source}
        if self.latitude is not None:
            data[ATTR_LATITUDE] = round(self.latitude, 5)
        if self.longitude is not None:
            data[ATTR_LONGITUDE] = round(self.longitude, 5)
        return data
