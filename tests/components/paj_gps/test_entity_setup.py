"""Tests for device model resolution in PajGpsEntity._build_device_info.

Covers:
- _build_device_info reads model from device.device_models[0]["model"]
- _build_device_info falls back to None when device_models is empty or None
- _build_device_info falls back to None when the model entry is None
"""

from __future__ import annotations

from homeassistant.components.paj_gps.coordinator import PajGpsData
from homeassistant.components.paj_gps.entity import PajGpsEntity

from .test_common import make_coordinator, make_device

# ---------------------------------------------------------------------------
# PajGpsEntity._build_device_info — device model resolution
# ---------------------------------------------------------------------------


class TestGetDeviceInfoModel:
    """Verify that _build_device_info reads the model from device.device_models."""

    def _make_entity_with_device(self, device) -> PajGpsEntity:
        coord = make_coordinator()
        coord.data = PajGpsData(devices={device.id: device}, positions={})
        return PajGpsEntity(coord, device.id)

    def test_model_read_from_device_models_first_entry(self):
        """Model should come from device_models[0]['model']."""
        device = make_device(1, device_models=[{"model": "PAJ ALLROUND Finder 4G"}])
        entity = self._make_entity_with_device(device)

        assert entity._attr_device_info["model"] == "PAJ ALLROUND Finder 4G"

    def test_model_falls_back_to_none_when_device_models_is_empty_list(self):
        """When device_models is an empty list there is no model entry — fall back to None."""
        device = make_device(1, device_models=[])
        entity = self._make_entity_with_device(device)

        assert entity._attr_device_info["model"] is None

    def test_model_falls_back_to_none_when_device_models_is_none(self):
        """When device_models is None fall back to None."""
        device = make_device(1, device_models=None)
        entity = self._make_entity_with_device(device)

        assert entity._attr_device_info["model"] is None

    def test_model_falls_back_to_none_when_model_key_is_none(self):
        """When device_models[0]['model'] is None fall back to None."""
        device = make_device(1, device_models=[{"model": None}])
        entity = self._make_entity_with_device(device)

        assert entity._attr_device_info["model"] is None

    def test_model_uses_first_entry_when_multiple_models_present(self):
        """Only the first entry in device_models should be used."""
        device = make_device(
            1,
            device_models=[
                {"model": "First Model"},
                {"model": "Second Model"},
            ],
        )
        entity = self._make_entity_with_device(device)

        assert entity._attr_device_info["model"] == "First Model"
