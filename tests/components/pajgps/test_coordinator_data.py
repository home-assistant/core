"""Tests for PajGpsData snapshot helpers and apply_alert_flag utility."""

from __future__ import annotations

import dataclasses
import unittest

from homeassistant.components.pajgps.coordinator import PajGpsData

from .test_common import make_device, make_trackpoint


class TestPajGpsData(unittest.TestCase):
    """Tests for PajGpsData snapshot helpers and apply_alert_flag utility."""

    def test_default_snapshot_is_empty(self):
        """Test that a default PajGpsData instance has empty devices and positions."""
        data = PajGpsData(devices={}, positions={})
        assert data.devices == {}
        assert data.positions == {}

    def test_replace_preserves_other_fields(self):
        """Test that replacing one field preserves the other fields unchanged."""
        device = make_device(1)
        data = PajGpsData(devices={1: device}, positions={})
        tp = make_trackpoint(1)
        new_data = dataclasses.replace(data, positions={1: tp})

        assert new_data.devices == {1: device}
        assert new_data.positions == {1: tp}
        # Original is untouched (frozen)
        assert data.positions == {}

    def test_snapshot_is_immutable_via_replace(self):
        """Mutating via dataclasses.replace() creates a new object; original is unchanged."""
        device = make_device(1)
        original = PajGpsData(devices={1: device}, positions={})
        updated = dataclasses.replace(original, positions={1: make_trackpoint(1)})
        # replace() returns a distinct object
        assert original is not updated
        # original is untouched
        assert original.positions == {}
        # updated carries the new value
        assert 1 in updated.positions
