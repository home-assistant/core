"""Tests for the ista EcoTrend utility functions."""

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.ista_ecotrend.util import (
    IstaConsumptionType,
    IstaValueType,
    as_number,
    get_native_value,
    get_statistics,
    get_values_by_type,
    last_day_of_month,
)

from .conftest import get_consumption_data


def test_as_number() -> None:
    """Test as_number formatting function."""
    assert as_number("10") == 10
    assert isinstance(as_number("10"), int)

    assert as_number("9,5") == 9.5
    assert isinstance(as_number("9,5"), float)

    assert as_number(None) is None
    assert isinstance(as_number(10.0), float)


def test_last_day_of_month(snapshot: SnapshotAssertion) -> None:
    """Test determining last day of month."""

    for month in range(12):
        assert last_day_of_month(month=month + 1, year=2024) == snapshot


def test_get_values_by_type(snapshot: SnapshotAssertion) -> None:
    """Test get_values_by_type function."""
    consumptions = {
        "readings": [
            {
                "type": "heating",
                "value": "35",
                "additionalValue": "38,0",
            },
            {
                "type": "warmwater",
                "value": "1,0",
                "additionalValue": "57,0",
            },
            {
                "type": "water",
                "value": "5,0",
            },
        ],
    }

    assert get_values_by_type(consumptions, IstaConsumptionType.HEATING) == snapshot
    assert get_values_by_type(consumptions, IstaConsumptionType.HOT_WATER) == snapshot
    assert get_values_by_type(consumptions, IstaConsumptionType.WATER) == snapshot

    costs = {
        "costsByEnergyType": [
            {
                "type": "heating",
                "value": 21,
            },
            {
                "type": "warmwater",
                "value": 7,
            },
            {
                "type": "water",
                "value": 3,
            },
        ],
    }

    assert get_values_by_type(costs, IstaConsumptionType.HEATING) == snapshot
    assert get_values_by_type(costs, IstaConsumptionType.HOT_WATER) == snapshot
    assert get_values_by_type(costs, IstaConsumptionType.WATER) == snapshot

    assert get_values_by_type({}, IstaConsumptionType.HEATING) == {}
    assert get_values_by_type({"readings": []}, IstaConsumptionType.HEATING) == {}


def test_get_native_value() -> None:
    """Test getting native value for sensor states."""
    test_data = get_consumption_data("26e93f1a-c828-11ea-87d0-0242ac130003")

    assert get_native_value(test_data, IstaConsumptionType.HEATING) == 35
    assert get_native_value(test_data, IstaConsumptionType.HOT_WATER) == 1.0
    assert get_native_value(test_data, IstaConsumptionType.WATER) == 5.0

    assert (
        get_native_value(test_data, IstaConsumptionType.HEATING, IstaValueType.COSTS)
        == 21
    )
    assert (
        get_native_value(test_data, IstaConsumptionType.HOT_WATER, IstaValueType.COSTS)
        == 7
    )
    assert (
        get_native_value(test_data, IstaConsumptionType.WATER, IstaValueType.COSTS) == 3
    )

    assert (
        get_native_value(test_data, IstaConsumptionType.HEATING, IstaValueType.ENERGY)
        == 38.0
    )
    assert (
        get_native_value(test_data, IstaConsumptionType.HOT_WATER, IstaValueType.ENERGY)
        == 57.0
    )

    no_data = {"consumptions": None, "costs": None}
    assert get_native_value(no_data, IstaConsumptionType.HEATING) is None
    assert (
        get_native_value(no_data, IstaConsumptionType.HEATING, IstaValueType.COSTS)
        is None
    )


def test_get_statistics(snapshot: SnapshotAssertion) -> None:
    """Test get_statistics function."""
    test_data = get_consumption_data("26e93f1a-c828-11ea-87d0-0242ac130003")
    for consumption_type in IstaConsumptionType:
        assert get_statistics(test_data, consumption_type) == snapshot
        assert get_statistics({"consumptions": None}, consumption_type) is None
        assert (
            get_statistics(test_data, consumption_type, IstaValueType.ENERGY)
            == snapshot
        )
        assert (
            get_statistics(
                {"consumptions": None}, consumption_type, IstaValueType.ENERGY
            )
            is None
        )
        assert (
            get_statistics(test_data, consumption_type, IstaValueType.COSTS) == snapshot
        )
        assert (
            get_statistics({"costs": None}, consumption_type, IstaValueType.COSTS)
            is None
        )
