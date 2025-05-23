"""Sensor entities for Geocaching."""

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import GeocachingDataUpdateCoordinator


# Base class for all platforms
class GeocachingBaseEntity(CoordinatorEntity[GeocachingDataUpdateCoordinator]):
    """Base class for Geocaching sensors."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: GeocachingDataUpdateCoordinator) -> None:
        """Initialize the Geocaching sensor."""
        super().__init__(coordinator)
