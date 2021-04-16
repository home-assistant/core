"""Support for Geolocation."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import final

from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.helpers.config_validation import (  # noqa: F401
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent

# mypy: allow-untyped-defs, no-check-untyped-defs

_LOGGER = logging.getLogger(__name__)

ATTR_DISTANCE = "distance"
ATTR_SOURCE = "source"

DOMAIN = "geo_location"

ENTITY_ID_FORMAT = DOMAIN + ".{}"

SCAN_INTERVAL = timedelta(seconds=60)


async def async_setup(hass, config):
    """Set up the Geolocation component."""
    component = hass.data[DOMAIN] = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    await component.async_setup(config)
    return True


async def async_setup_entry(hass, entry):
    """Set up a config entry."""
    return await hass.data[DOMAIN].async_setup_entry(entry)


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    return await hass.data[DOMAIN].async_unload_entry(entry)


class GeolocationEvent(Entity):
    """Base class for an external event with an associated geolocation."""

    @property
    def state(self):
        """Return the state of the sensor."""
        if self.distance is not None:
            return round(self.distance, 1)
        return None

    @property
    def source(self) -> str:
        """Return source value of this external event."""
        raise NotImplementedError

    @property
    def distance(self) -> float | None:
        """Return distance value of this external event."""
        return None

    @property
    def latitude(self) -> float | None:
        """Return latitude value of this external event."""
        return None

    @property
    def longitude(self) -> float | None:
        """Return longitude value of this external event."""
        return None

    @final
    @property
    def state_attributes(self):
        """Return the state attributes of this external event."""
        data = {}
        if self.latitude is not None:
            data[ATTR_LATITUDE] = round(self.latitude, 5)
        if self.longitude is not None:
            data[ATTR_LONGITUDE] = round(self.longitude, 5)
        if self.source is not None:
            data[ATTR_SOURCE] = self.source
        return data
