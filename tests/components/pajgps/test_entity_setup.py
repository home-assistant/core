"""Tests for device model resolution in get_device_info and related helpers.

Covers:
- get_device_info reads model from device.device_models[0]["model"]
- get_device_info falls back to "Unknown" when device_models is empty or None
- get_device_info falls back to "Unknown" when the model entry is None
- the helper used to build a hass/config_entry pair around a coordinator
"""

from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.components.pajgps.coordinator import CoordinatorData

from .test_common import make_device
from .test_device_tracker import make_coordinator

# ---------------------------------------------------------------------------
# get_device_info — device model resolution
# ---------------------------------------------------------------------------


class TestGetDeviceInfoModel:
    """Verify that get_device_info reads the model from device.device_models."""

    def _make_coord_with_device(self, device):
        coord = make_coordinator()
        coord.data = CoordinatorData(devices=[device])
        return coord

    def test_model_read_from_device_models_first_entry(self):
        """Model should come from device_models[0]['model']."""
        device = make_device(1, device_models=[{"model": "PAJ ALLROUND Finder 4G"}])
        coord = self._make_coord_with_device(device)

        info = coord.get_device_info(1)

        assert info["model"] == "PAJ ALLROUND Finder 4G"

    def test_model_falls_back_to_unknown_when_device_models_is_empty_list(self):
        """When device_models is an empty list there is no model entry — fall back to 'Unknown'."""
        device = make_device(1, device_models=[])
        coord = self._make_coord_with_device(device)

        info = coord.get_device_info(1)

        assert info["model"] == "Unknown"

    def test_model_falls_back_to_unknown_when_device_models_is_none(self):
        """When device_models is None fall back to 'Unknown'."""
        device = make_device(1, device_models=None)
        coord = self._make_coord_with_device(device)

        info = coord.get_device_info(1)

        assert info["model"] == "Unknown"

    def test_model_falls_back_to_unknown_when_model_key_is_none(self):
        """When device_models[0]['model'] is None fall back to 'Unknown'."""
        device = make_device(1, device_models=[{"model": None}])
        coord = self._make_coord_with_device(device)

        info = coord.get_device_info(1)

        assert info["model"] == "Unknown"

    def test_model_uses_first_entry_when_multiple_models_present(self):
        """Only the first entry in device_models should be used."""
        device = make_device(
            1,
            device_models=[
                {"model": "First Model"},
                {"model": "Second Model"},
            ],
        )
        coord = self._make_coord_with_device(device)

        info = coord.get_device_info(1)

        assert info["model"] == "First Model"


# ---------------------------------------------------------------------------
# Helpers shared by switch + binary_sensor setup tests
# ---------------------------------------------------------------------------


def _make_hass_and_config_entry(coordinator):
    """Return a fake hass and config_entry wired to the given coordinator."""
    config_entry = MagicMock()
    config_entry.entry_id = "test_entry_id"
    config_entry.runtime_data = coordinator

    hass = MagicMock()

    return hass, config_entry
