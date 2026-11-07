"""Tests for the monoprice component."""

from collections import defaultdict

from homeassistant.components.monoprice.const import CONF_SOURCES
from homeassistant.const import CONF_PORT

MOCK_CONFIG = {CONF_PORT: "fake port", CONF_SOURCES: {"1": "one", "3": "three"}}


class AttrDict(dict):
    """Helper class for mocking attributes."""

    def __setattr__(self, name, value):
        """Set attribute."""
        self[name] = value

    def __getattr__(self, item):
        """Get attribute."""
        return self[item]


class MockMonoprice:
    """Mock for pymonoprice object."""

    def __init__(self) -> None:
        """Init mock object."""
        self.zones = defaultdict(
            lambda: AttrDict(power=True, volume=0, mute=True, source=1)
        )

    def zone_status(self, zone_id):
        """Get zone status."""
        status = self.zones[zone_id]
        status.zone = zone_id
        return AttrDict(status)

    def set_source(self, zone_id, source_idx):
        """Set source for zone."""
        self.zones[zone_id].source = source_idx

    def set_power(self, zone_id, power):
        """Turn zone on/off."""
        self.zones[zone_id].power = power

    def set_mute(self, zone_id, mute):
        """Mute/unmute zone."""
        self.zones[zone_id].mute = mute

    def set_volume(self, zone_id, volume):
        """Set volume for zone."""
        self.zones[zone_id].volume = volume

    def restore_zone(self, zone):
        """Restore zone status."""
        self.zones[zone.zone] = AttrDict(zone)
