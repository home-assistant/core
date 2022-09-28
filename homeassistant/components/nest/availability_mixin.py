"""Mixin for SDM availability."""
from __future__ import annotations

from google_nest_sdm.device import Device
from google_nest_sdm.device_traits import ConnectivityTrait

from .const import CONNECTIVITY_TRAIT_OFFLINE


class AvailabilityMixin:
    """Mixin for entities to set availability based on the connectivity trait."""

    @property
    def available(self) -> bool:
        """Return entity availability."""
        device: Device = getattr(
            self, "_device"
        )  # To prevent linter errors on access to member in instantiated class
        if ConnectivityTrait.NAME in device.traits:
            trait: ConnectivityTrait = device.traits[ConnectivityTrait.NAME]
            if trait.status == CONNECTIVITY_TRAIT_OFFLINE:
                return False
        return True
