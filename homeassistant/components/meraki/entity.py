"""Base entity for the Meraki integration."""

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import MerakiDataUpdateCoordinator


class MerakiEntity(CoordinatorEntity[MerakiDataUpdateCoordinator]):
    """An entity updated by the Meraki coordinator."""
