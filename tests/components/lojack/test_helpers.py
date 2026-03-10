"""Tests for LoJack utility functions."""

from homeassistant.components.lojack.coordinator import (
    LoJackVehicleData,
    get_device_name,
)


def _make_vehicle(**kwargs) -> LoJackVehicleData:
    """Create a LoJackVehicleData with defaults for unspecified fields."""
    defaults = dict(
        device_id="123",
        name=None,
        vin=None,
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
    defaults.update(kwargs)
    return LoJackVehicleData(**defaults)


def test_get_device_name_full_info() -> None:
    """Test get_device_name with full vehicle info."""
    vehicle = _make_vehicle(year=2021, make="Honda", model="Accord", name="My Car")
    assert get_device_name(vehicle) == "2021 Honda Accord"


def test_get_device_name_no_year() -> None:
    """Test get_device_name without year."""
    vehicle = _make_vehicle(make="Honda", model="Accord", name="My Car")
    assert get_device_name(vehicle) == "Honda Accord"


def test_get_device_name_only_model() -> None:
    """Test get_device_name with only model."""
    vehicle = _make_vehicle(model="Accord", name="My Car")
    assert get_device_name(vehicle) == "Accord"


def test_get_device_name_only_make() -> None:
    """Test get_device_name with only make."""
    vehicle = _make_vehicle(make="Honda", name="My Car")
    assert get_device_name(vehicle) == "Honda"


def test_get_device_name_only_name() -> None:
    """Test get_device_name falls back to name when no make/model/year."""
    vehicle = _make_vehicle(name="My Car")
    assert get_device_name(vehicle) == "My Car"


def test_get_device_name_no_name() -> None:
    """Test get_device_name without any name info."""
    vehicle = _make_vehicle()
    assert get_device_name(vehicle) == "Vehicle"


def test_get_device_name_year_as_int() -> None:
    """Test get_device_name uses integer year correctly."""
    vehicle = _make_vehicle(year=2023, make="Ford", model="F-150")
    assert get_device_name(vehicle) == "2023 Ford F-150"
