"""Entity for Firmata devices."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo

from .board import FirmataPinType
from .const import DOMAIN, FIRMATA_MANUFACTURER
from .pin import FirmataBoardPin


class FirmataEntity:
    """Representation of a Firmata entity."""

    def __init__(self, api):
        """Initialize the entity."""
        self._api = api

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            connections=set(),
            identifiers={(DOMAIN, self._api.board.name)},
            manufacturer=FIRMATA_MANUFACTURER,
            name=self._api.board.name,
            sw_version=self._api.board.firmware_version,
        )


class FirmataPinEntity(FirmataEntity):
    """Representation of a Firmata pin entity."""

    _attr_should_poll = False

    def __init__(
        self,
        api: FirmataBoardPin,
        config_entry: ConfigEntry,
        name: str,
        pin: FirmataPinType,
    ) -> None:
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
    def unique_id(self) -> str:
        """Return a unique identifier for this device."""
        return self._unique_id
