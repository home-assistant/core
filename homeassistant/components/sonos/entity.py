"""Entity representing a Sonos player."""
from typing import Any, Dict

from pysonos.core import SoCo

import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.entity import Entity

from . import SonosData
from .const import DOMAIN as SONOS_DOMAIN


class SonosEntity(Entity):
    """Representation of a Sonos entity."""

    def __init__(self, soco: SoCo, sonos_data: SonosData):
        """Initialize a SonosEntity."""
        self._soco = soco
        self.data = sonos_data

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return information about the device."""
        speaker_info = self.data.speaker_info[self._soco.uid]
        return {
            "identifiers": {(SONOS_DOMAIN, self._soco.uid)},
            "name": speaker_info["zone_name"],
            "model": speaker_info["model_name"].replace("Sonos ", ""),
            "sw_version": speaker_info["software_version"],
            "connections": {(dr.CONNECTION_NETWORK_MAC, speaker_info["mac_address"])},
            "manufacturer": "Sonos",
            "suggested_area": speaker_info["zone_name"],
        }

    # Current state
    @property
    def available(self) -> bool:
        """Return whether this device is available."""
        return self._soco.uid in self.data.seen_timers
