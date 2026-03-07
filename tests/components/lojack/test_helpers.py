"""Tests for LoJack utility functions."""

from homeassistant.components.lojack.coordinator import (
    get_device_name,
    _safe_float,
    LoJackVehicleData,
)


def test_get_device_name_full_info() -> None:
    """Test get_device_name with full vehicle info."""
    vehicle = LoJackVehicleData(
        device_id="123",
        name="My Car",
        vin="VIN123",
        make="Honda",
        model="Accord",
        year="2021",
        latitude=None,
        longitude=None,
        accuracy=None,
        address=None,
        heading=None,
        timestamp=None,
    )
    assert get_device_name(vehicle) == "2021 Honda Accord"


def test_get_device_name_no_year() -> None:
    """Test get_device_name without year."""
    vehicle = LoJackVehicleData(
        device_id="123",
        name="My Car",
        vin="VIN123",
        make="Honda",
        model="Accord",
        year=None,
        latitude=None,
        longitude=None,
        accuracy=None,
        address=None,
        heading=None,
        timestamp=None,
    )
    assert get_device_name(vehicle) == "Honda Accord"


def test_get_device_name_no_year_or_make() -> None:
    """Test get_device_name with only model."""
    vehicle = LoJackVehicleData(
        device_id="123",
        name="My Car",
        vin="VIN123",
        make=None,
        model="Accord",
        year=None,
        latitude=None,
        longitude=None,
        accuracy=None,
        address=None,
        heading=None,
        timestamp=None,
    )
    assert get_device_name(vehicle) == "My Car"


def test_get_device_name_only_make() -> None:
    """Test get_device_name with only make."""
    vehicle = LoJackVehicleData(
        device_id="123",
        name="My Car",
        vin="VIN123",
        make="Honda",
        model=None,
        year=None,
        latitude=None,
        longitude=None,
        accuracy=None,
        address=None,
        heading=None,
        timestamp=None,
    )
    assert get_device_name(vehicle) == "My Car"


def test_get_device_name_no_name() -> None:
    """Test get_device_name without any name info."""
    vehicle = LoJackVehicleData(
        device_id="123",
        name=None,
        vin="VIN123",
        make=None,
        model=None,
        year=None,
        latitude=None,
        longitude=None,
        accuracy=None,
        address=None,
        heading=None,
        timestamp=None,
    )
    assert get_device_name(vehicle) == "Vehicle"


def test_safe_float_valid_float() -> None:
    """Test _safe_float with valid float."""
    assert _safe_float(123.45) == 123.45


def test_safe_float_valid_int() -> None:
    """Test _safe_float with valid int."""
    assert _safe_float(123) == 123.0


def test_safe_float_valid_string() -> None:
    """Test _safe_float with valid string."""
    assert _safe_float("123.45") == 123.45


def test_safe_float_invalid_string() -> None:
    """Test _safe_float with invalid string."""
    assert _safe_float("not a number") is None


def test_safe_float_none() -> None:
    """Test _safe_float with None."""
    assert _safe_float(None) is None


def test_safe_float_empty_string() -> None:
    """Test _safe_float with empty string."""
    assert _safe_float("") is None


def test_safe_float_zero() -> None:
    """Test _safe_float with zero."""
    assert _safe_float(0) == 0.0


def test_safe_float_negative() -> None:
    """Test _safe_float with negative number."""
    assert _safe_float(-123.45) == -123.45


def test_safe_float_scientific_notation() -> None:
    """Test _safe_float with scientific notation."""
    assert _safe_float(1.23e-4) == 0.000123


def test_safe_float_bool() -> None:
    """Test _safe_float with boolean."""
    # Booleans are explicitly rejected to prevent invalid coordinates
    # (bool is a subclass of int, but True/False should not become 1.0/0.0)
    assert _safe_float(True) is None
    assert _safe_float(False) is None
