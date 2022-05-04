"""Tests for the Lutron Caseta integration."""


class MockBridge:
    """Mock Lutron bridge that emulates configured connected status."""

    def __init__(self, can_connect=True):
        """Initialize MockBridge instance with configured mock connectivity."""
        self.can_connect = can_connect
        self.is_currently_connected = False
        self.buttons = {}
        self.areas = {}
        self.occupancy_groups = {}
        self.scenes = self.get_scenes()
        self.devices = self.get_devices()

    async def connect(self):
        """Connect the mock bridge."""
        if self.can_connect:
            self.is_currently_connected = True

    def is_connected(self):
        """Return whether the mock bridge is connected."""
        return self.is_currently_connected

    def get_devices(self):
        """Return devices on the bridge."""
        return {
            "1": {"serial": 1234, "name": "bridge", "model": "model", "type": "type"}
        }

    def get_devices_by_domain(self, domain):
        """Return devices on the bridge."""
        return {}

    def get_scenes(self):
        """Return scenes on the bridge."""
        return {}

    async def close(self):
        """Close the mock bridge connection."""
        self.is_currently_connected = False
