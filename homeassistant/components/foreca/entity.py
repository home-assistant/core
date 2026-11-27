"""Base entity for the Foreca integration."""

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION
from .coordinator import ForecaCoordinator


class ForecaEntity[CoordinatorT: ForecaCoordinator](CoordinatorEntity[CoordinatorT]):
    """Defines a base Foreca entity."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True
