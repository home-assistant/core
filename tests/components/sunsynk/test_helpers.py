"""Tests for helpers module."""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.sunsynk.helpers import (
    extract_value,
    get_inv_data,
    get_inverter_settings,
    get_source_obj,
    inverter_device_info,
    safe_float,
)


class TestExtractValue:
    """Tests for extract_value."""

    def test_getattr(self) -> None:
        """Test getattr extraction."""
        obj = MagicMock()
        obj.some_key = "val"
        assert extract_value(obj, "some_key") == "val"

    def test_dict_fallback(self) -> None:
        """Test dict fallback extraction."""
        assert extract_value({"foo": "bar"}, "foo") == "bar"

    def test_model_extra(self) -> None:
        """Test model_extra extraction."""

        class FakeModel:
            some_key = None
            model_extra: dict[str, str] = {"some_key": "extra_val"}

        assert extract_value(FakeModel(), "some_key") == "extra_val"

    def test_returns_none_for_missing(self) -> None:
        """Test returns None for missing key."""
        assert extract_value({"a": 1}, "missing") is None


class TestSafeFloat:
    """Tests for safe_float."""

    def test_none(self) -> None:
        """Test None input returns None."""
        assert safe_float(None) is None

    def test_string_number(self) -> None:
        """Test string number conversion."""
        result = safe_float("3.14")
        assert result is not None
        assert abs(result - 3.14) < 1e-9

    def test_int(self) -> None:
        """Test int conversion."""
        result = safe_float(42)
        assert result is not None
        assert abs(result - 42.0) < 1e-9

    def test_invalid(self) -> None:
        """Test invalid input returns None."""
        assert safe_float("not_a_number") is None

    def test_zero(self) -> None:
        """Test zero conversion."""
        result = safe_float(0)
        assert result is not None
        assert abs(result) < 1e-9


class TestGetInvData:
    """Tests for get_inv_data."""

    def _make_coordinator(self, data: dict | None) -> MagicMock:
        coord = MagicMock()
        coord.data = data
        return coord

    def test_returns_inverter_data(self) -> None:
        """Test returns inverter data."""
        inv = {"battery": MagicMock(), "settings": MagicMock()}
        coord = self._make_coordinator(
            {
                "plants": {1: {"inverters": {"SN123": inv}}},
            }
        )
        assert get_inv_data(coord, 1, "SN123") is inv

    def test_returns_none_no_data(self) -> None:
        """Test returns None when no data."""
        coord = self._make_coordinator(None)
        assert get_inv_data(coord, 1, "SN123") is None

    def test_returns_none_missing_plant(self) -> None:
        """Test returns None when plant is missing."""
        coord = self._make_coordinator({"plants": {}})
        assert get_inv_data(coord, 1, "SN123") is None


class TestGetSourceObj:
    """Tests for get_source_obj."""

    def test_returns_source(self) -> None:
        """Test returns source object."""
        batt = MagicMock()
        coord = MagicMock()
        coord.data = {"plants": {1: {"inverters": {"SN1": {"battery": batt}}}}}
        assert get_source_obj(coord, 1, "SN1", "battery") is batt

    def test_returns_none_missing(self) -> None:
        """Test returns None when source is missing."""
        coord = MagicMock()
        coord.data = {"plants": {1: {"inverters": {"SN1": {}}}}}
        assert get_source_obj(coord, 1, "SN1", "battery") is None


class TestGetInverterSettings:
    """Tests for get_inverter_settings."""

    def test_returns_settings(self) -> None:
        """Test returns inverter settings."""
        settings = MagicMock()
        coord = MagicMock()
        coord.data = {"plants": {1: {"inverters": {"SN1": {"settings": settings}}}}}
        assert get_inverter_settings(coord, 1, "SN1") is settings

    def test_returns_none_no_settings(self) -> None:
        """Test returns None when settings are missing."""
        coord = MagicMock()
        coord.data = {"plants": {1: {"inverters": {"SN1": {}}}}}
        assert get_inverter_settings(coord, 1, "SN1") is None


class TestInverterDeviceInfo:
    """Tests for inverter_device_info."""

    def test_creates_device_info(self) -> None:
        """Test creates device info."""
        info = inverter_device_info(1, "SN123")
        assert ("sunsynk", "inverter_SN123") in info.get("identifiers", set())
        assert info.get("serial_number") == "SN123"
        assert info.get("via_device") == ("sunsynk", "plant_1")
