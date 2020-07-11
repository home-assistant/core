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


class FirmataPinEntity(FirmataEntity):
    """Representation of a Firmata pin entity."""

    def __init__(self, api, config_entry, name, pin):
        """Initialize the pin entity."""
        super().__init__(api)
        self._name = name

        location = (config_entry.entry_id, "pin", pin)
        self._unique_id = "_".join(str(i) for i in location)

    @property
    def name(self) -> str:
        """Get the name of the pin."""
        return self._name

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    @property
    def unique_id(self):
        """Return a unique identifier for this device."""
        return self._unique_id
