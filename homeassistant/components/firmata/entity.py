"""Entity for Firmata devices."""

from .const import DOMAIN, FIRMATA_MANUFACTURER


class FirmataEntity:
    """Representation of a Firmata entity."""

    def __init__(self, api):
        """Initialize the entity."""
        self._api = api

    @property
    def device_info(self) -> dict:
        """Return device info."""
        return {
            "connections": {},
            "identifiers": {(DOMAIN, self._api.board.name)},
            "manufacturer": FIRMATA_MANUFACTURER,
            "name": self._api.board.name,
            "sw_version": self._api.board.firmware_version,
        }
