"""Base entity for the NMBS integration."""

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import NMBSCoordinator


class NMBSEntity(CoordinatorEntity[NMBSCoordinator]):
    """Base entity for the NMBS integration."""

    _attr_attribution = "https://api.irail.be/"
    _attr_has_entity_name = True
