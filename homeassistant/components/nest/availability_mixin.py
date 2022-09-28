"""Mixin for SDM availability."""
from google_nest_sdm.device import Device
from google_nest_sdm.device_traits import ConnectivityTrait
from .const import CONNECTIVITY_TRAIT_OFFLINE


class AvailabilityMixin:
    """Mixin for entities to set availability based on the connectivity trait."""

    def __init__(self):
        """Initialize the mixin."""
        self._device: Device = None

    @property
    def available(self) -> bool:
        """Return entity availability."""
        if ConnectivityTrait.NAME in self._device.traits:
            trait: ConnectivityTrait = self._device.traits[ConnectivityTrait.NAME]
            if trait.status == CONNECTIVITY_TRAIT_OFFLINE:
                return False
        return True
