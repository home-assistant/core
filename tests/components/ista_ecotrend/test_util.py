"""Tests for the ista EcoTrend utility functions."""

import pytest
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


@pytest.mark.parametrize(
    "consumption_type",
    [
        IstaConsumptionType.HEATING,
        IstaConsumptionType.HOT_WATER,
        IstaConsumptionType.WATER,
    ],
)
def test_get_values_by_type(
    snapshot: SnapshotAssertion, consumption_type: IstaConsumptionType
) -> None:
    """Test get_values_by_type function."""
    consumptions = {
        "readings": [
            {
                "type": "heating",
                "value": "35",
                "unit": "Einheiten",
                "additionalValue": "38,0",
                "additionalUnit": "kWh",
            },
            {
                "type": "warmwater",
                "value": "1,0",
                "unit": "m³",
                "additionalValue": "57,0",
                "additionalUnit": "kWh",
            },
            {
                "type": "water",
                "value": "5,0",
                "unit": "m³",
            },
        ],
    }

    assert get_values_by_type(consumptions, consumption_type) == snapshot

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

    assert get_values_by_type(costs, consumption_type) == snapshot

    assert get_values_by_type({}, consumption_type) == {}
    assert get_values_by_type({"readings": []}, consumption_type) == {}


@pytest.mark.parametrize(
    ("consumption_type", "value_type", "expected_value"),
    [
        (IstaConsumptionType.HEATING, None, 35),
        (IstaConsumptionType.HOT_WATER, None, 1.0),
        (IstaConsumptionType.WATER, None, 5.0),
        (IstaConsumptionType.HEATING, IstaValueType.COSTS, 21),
        (IstaConsumptionType.HOT_WATER, IstaValueType.COSTS, 7),
        (IstaConsumptionType.WATER, IstaValueType.COSTS, 3),
        (IstaConsumptionType.HEATING, IstaValueType.ENERGY, 38.0),
        (IstaConsumptionType.HOT_WATER, IstaValueType.ENERGY, 57.0),
    ],
)
def test_get_native_value(
    consumption_type: IstaConsumptionType,
    value_type: IstaValueType | None,
    expected_value: float,
) -> None:
    """Test getting native value for sensor states."""
    test_data = get_consumption_data("26e93f1a-c828-11ea-87d0-0242ac130003")

    assert get_native_value(test_data, consumption_type, value_type) == expected_value

    no_data = {"consumptions": None, "costs": None}
    assert get_native_value(no_data, consumption_type, value_type) is None


@pytest.mark.parametrize(
    "value_type",
    [None, IstaValueType.ENERGY, IstaValueType.COSTS],
)
@pytest.mark.parametrize(
    "consumption_type",
    [
        IstaConsumptionType.HEATING,
        IstaConsumptionType.HOT_WATER,
        IstaConsumptionType.WATER,
    ],
)
def test_get_statistics(
    snapshot: SnapshotAssertion,
    value_type: IstaValueType | None,
    consumption_type: IstaConsumptionType,
) -> None:
    """Test get_statistics function."""
    test_data = get_consumption_data("26e93f1a-c828-11ea-87d0-0242ac130003")
    assert get_statistics(test_data, consumption_type, value_type) == snapshot

    assert get_statistics({"consumptions": None}, consumption_type, value_type) is None
