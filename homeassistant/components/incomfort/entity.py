"""Common entity classes for InComfort integration."""

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import InComfortDataCoordinator


class IncomfortEntity(CoordinatorEntity[InComfortDataCoordinator]):
    """Base class for all InComfort entities."""

    _attr_has_entity_name = True
