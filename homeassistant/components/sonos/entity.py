"""Entity representing a Sonos player."""
from typing import Any, Dict

from pysonos.core import SoCo

import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.entity import Entity

from .const import DATA_SONOS, DOMAIN as SONOS_DOMAIN


class SonosEntity(Entity):
    """Representation of a Sonos entity."""

    def __init__(self, soco: SoCo):
        """Initialize a SonosEntity."""
        self._soco = soco

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return information about the device."""
        speaker_info = self.hass.data[DATA_SONOS].speaker_info[self._soco.uid]
        return {
            "identifiers": {(SONOS_DOMAIN, self._soco.uid)},
            "name": speaker_info["zone_name"],
            "model": speaker_info["model_name"].replace("Sonos ", ""),
            "sw_version": speaker_info["software_version"],
            "connections": {(dr.CONNECTION_NETWORK_MAC, speaker_info["mac_address"])},
            "manufacturer": "Sonos",
            "suggested_area": speaker_info["zone_name"],
        }
