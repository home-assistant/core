"""Tests for the BIR coordinator."""

from datetime import date

from pybirno import WastePickup as BirWastePickup

from homeassistant.components.bir.coordinator import BirDataUpdateCoordinator


def test_process_pickup_data() -> None:
    """Test processing raw pickup data from the API."""
    pickups = [
        BirWastePickup(date=date(2026, 4, 15), waste_type="mixed_waste", waste_type_name="Restavfall", waste_type_id="1", frequency_type=0, frequency_interval=0),
        BirWastePickup(date=date(2026, 4, 20), waste_type="paper_and_plastic", waste_type_name="Papir", waste_type_id="2", frequency_type=0, frequency_interval=0),
        BirWastePickup(date=date(2026, 4, 10), waste_type="food_waste", waste_type_name="Matavfall", waste_type_id="3", frequency_type=0, frequency_interval=0),
        BirWastePickup(date=date(2026, 5, 1), waste_type="glass_and_metal_packaging", waste_type_name="Glass og metallemballasje", waste_type_id="4", frequency_type=0, frequency_interval=0),
        BirWastePickup(date=date(2026, 4, 12), waste_type="Unknown Type", waste_type_name="Unknown Type", waste_type_id="99", frequency_type=0, frequency_interval=0),
    ]

    coordinator = BirDataUpdateCoordinator.__new__(BirDataUpdateCoordinator)
    result = coordinator._process_pickup_data(pickups, reference_date=date(2026, 4, 1))

    assert len(result) == 4
    assert result["mixed_waste"]["date"] == date(2026, 4, 15)
    assert result["mixed_waste"]["days_until"] == 14
    assert result["paper_and_plastic"]["date"] == date(2026, 4, 20)
    assert result["paper_and_plastic"]["days_until"] == 19
    assert result["food_waste"]["date"] == date(2026, 4, 10)
    assert result["food_waste"]["days_until"] == 9
    assert result["glass_and_metal_packaging"]["date"] == date(2026, 5, 1)
    assert result["glass_and_metal_packaging"]["days_until"] == 30


def test_process_pickup_data_keeps_earliest() -> None:
    """Test that only the earliest pickup date is kept per waste type."""
    pickups = [
        BirWastePickup(date=date(2026, 4, 20), waste_type="mixed_waste", waste_type_name="Restavfall", waste_type_id="1", frequency_type=0, frequency_interval=0),
        BirWastePickup(date=date(2026, 4, 10), waste_type="mixed_waste", waste_type_name="Restavfall", waste_type_id="1", frequency_type=0, frequency_interval=0),
        BirWastePickup(date=date(2026, 4, 30), waste_type="mixed_waste", waste_type_name="Restavfall", waste_type_id="1", frequency_type=0, frequency_interval=0),
    ]

    coordinator = BirDataUpdateCoordinator.__new__(BirDataUpdateCoordinator)
    result = coordinator._process_pickup_data(pickups, reference_date=date(2026, 4, 1))

    assert len(result) == 1
    assert result["mixed_waste"]["date"] == date(2026, 4, 10)
    assert result["mixed_waste"]["days_until"] == 9


def test_process_pickup_data_empty() -> None:
    """Test processing empty pickup data."""
    coordinator = BirDataUpdateCoordinator.__new__(BirDataUpdateCoordinator)
    result = coordinator._process_pickup_data([], reference_date=date(2026, 4, 1))

    assert result == {}


def test_process_pickup_data_days_until_minimum_zero() -> None:
    """Test that days_until is never negative."""
    pickups = [
        BirWastePickup(date=date(2026, 3, 15), waste_type="mixed_waste", waste_type_name="Restavfall", waste_type_id="1", frequency_type=0, frequency_interval=0),
    ]

    coordinator = BirDataUpdateCoordinator.__new__(BirDataUpdateCoordinator)
    result = coordinator._process_pickup_data(pickups, reference_date=date(2026, 4, 1))

    assert result["mixed_waste"]["days_until"] == 0
