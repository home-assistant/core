"""Reusable utilities for the Bond component."""

from typing import List, Optional

from bond import Actions, Bond


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

    def supports_speed(self) -> bool:
        """Return True if this device supports any of the speed related commands."""
        actions: List[str] = self._attrs["actions"]
        return len([action for action in actions if action in [Actions.SET_SPEED]]) > 0

    def supports_direction(self) -> bool:
        """Return True if this device supports any of the direction related commands."""
        actions: List[str] = self._attrs["actions"]
        return (
            len(
                [
                    action
                    for action in actions
                    if action in [Actions.SET_DIRECTION, Actions.TOGGLE_DIRECTION]
                ]
            )
            > 0
        )

    def supports_light(self) -> bool:
        """Return True if this device supports any of the light related commands."""
        actions: List[str] = self._attrs["actions"]
        return (
            len(
                [
                    action
                    for action in actions
                    if action in [Actions.TURN_LIGHT_ON, Actions.TOGGLE_LIGHT]
                ]
            )
            > 0
        )


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
