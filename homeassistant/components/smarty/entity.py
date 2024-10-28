"""Smarty Entity class."""

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import SmartyCoordinator


class SmartyEntity(CoordinatorEntity[SmartyCoordinator]):
    """Representation of a Smarty Entity."""
