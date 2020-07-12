"""Reusable utilities for the Bond component."""

from typing import List, Optional

from bond import Bond


class BondDevice:
    """Helper device class to hold ID and attributes together."""

    def __init__(self, device_id: str, attrs: dict):
        """Create a helper device from ID and attributes returned by API."""
        self.device_id = device_id
        self._attrs = attrs

    @property
    def name(self) -> str:
        """Get the name of this device."""
        return self._attrs["name"]

    @property
    def type(self) -> str:
        """Get the type of this device."""
        return self._attrs["type"]

    def supports_command(self, command: str) -> bool:
        """Return True if this device supports specified command."""
        actions: List[str] = self._attrs["actions"]
        return command in actions


class BondHub:
    """Hub device representing Bond Bridge."""

    def __init__(self, bond: Bond):
        """Initialize Bond Hub."""
        self.bond: Bond = bond
        self._version: Optional[dict] = None

    def setup(self):
        """Read hub version information."""
        self._version = self.bond.getVersion()

    def get_bond_devices(self) -> List[BondDevice]:
        """Fetch all available devices using Bond API."""
        device_ids = self.bond.getDeviceIds()
        devices = [
            BondDevice(device_id, self.bond.getDevice(device_id))
            for device_id in device_ids
        ]
        return devices

    @property
    def bond_id(self) -> str:
        """Return unique Bond ID for this hub."""
        return self._version["bondid"]

    @property
    def target(self) -> str:
        """Return this hub model."""
        return self._version.get("target")

    @property
    def fw_ver(self) -> str:
        """Return this hub firmware version."""
        return self._version.get("fw_ver")
