"""Common device classes for the Actron Air Neo integration."""

from .const import DOMAIN

UNKNOWN_STATUS = "Unknown"


class ACUnit:
    """Representation of an Actron Neo Air Conditioner device."""

    def __init__(self, serial_number, system, status) -> None:
        """Initialize the air conditioner device."""
        self._serial_number = serial_number
        self._status = status
        self._manufacturer = "Actron Air"
        self._name = system["_embedded"]["ac-system"][0]["description"]
        self._firmware_version = self._status.get("AirconSystem", {}).get(
            "MasterWCFirmwareVersion", UNKNOWN_STATUS
        )
        self._model_name = self._status.get("AirconSystem", {}).get(
            "MasterWCModel", UNKNOWN_STATUS
        )

    @property
    def device_info(self):
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self._serial_number)},
            "name": self._name,
            "manufacturer": self._manufacturer,
            "model": self._model_name,
            "sw_version": self._firmware_version,
            "serial_number": self._serial_number,
        }

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{DOMAIN}_{self._serial_number}"

    @property
    def manufacturer(self) -> str:
        """Return the manufacturer name."""
        return self._manufacturer
