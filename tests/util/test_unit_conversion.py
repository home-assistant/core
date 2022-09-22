"""Test Home Assistant eneergy utility functions."""
import pytest

from homeassistant.const import (
    ENERGY_KILO_WATT_HOUR,
    ENERGY_MEGA_WATT_HOUR,
    ENERGY_WATT_HOUR,
    POWER_KILO_WATT,
    POWER_WATT,
)
from homeassistant.util.unit_conversion import (
    BaseUnitConverter,
    EnergyConverter,
    PowerConverter,
)

INVALID_SYMBOL = "bob"


@pytest.mark.parametrize(
    "converter,valid_unit",
    [
        (EnergyConverter, ENERGY_WATT_HOUR),
        (EnergyConverter, ENERGY_KILO_WATT_HOUR),
        (EnergyConverter, ENERGY_MEGA_WATT_HOUR),
        (PowerConverter, POWER_WATT),
        (PowerConverter, POWER_KILO_WATT),
    ],
)
def test_convert_same_unit(converter: type[BaseUnitConverter], valid_unit: str) -> None:
    """Test conversion from any valid unit to same unit."""
    assert converter.convert(2, valid_unit, valid_unit) == 2


@pytest.mark.parametrize(
    "converter,valid_unit",
    [
        (EnergyConverter, ENERGY_KILO_WATT_HOUR),
        (PowerConverter, POWER_WATT),
    ],
)
def test_convert_invalid_unit(
    converter: type[BaseUnitConverter], valid_unit: str
) -> None:
    """Test exception is thrown for invalid units."""
    with pytest.raises(ValueError):
        converter.convert(5, INVALID_SYMBOL, valid_unit)

    with pytest.raises(ValueError):
        EnergyConverter.convert(5, valid_unit, INVALID_SYMBOL)


@pytest.mark.parametrize(
    "converter,from_unit,to_unit",
    [
        (EnergyConverter, ENERGY_WATT_HOUR, ENERGY_KILO_WATT_HOUR),
        (PowerConverter, POWER_WATT, POWER_KILO_WATT),
    ],
)
def test_convert_nonnumeric_value(
    converter: type[BaseUnitConverter], from_unit: str, to_unit: str
) -> None:
    """Test exception is thrown for nonnumeric type."""
    with pytest.raises(TypeError):
        converter.convert("a", from_unit, to_unit)


@pytest.mark.parametrize(
    "converter,value,from_unit,expected,to_unit",
    [
        (EnergyConverter, 10, ENERGY_WATT_HOUR, 0.01, ENERGY_KILO_WATT_HOUR),
        (EnergyConverter, 10, ENERGY_WATT_HOUR, 0.00001, ENERGY_MEGA_WATT_HOUR),
        (EnergyConverter, 10, ENERGY_KILO_WATT_HOUR, 10000, ENERGY_WATT_HOUR),
        (EnergyConverter, 10, ENERGY_KILO_WATT_HOUR, 0.01, ENERGY_MEGA_WATT_HOUR),
        (EnergyConverter, 10, ENERGY_MEGA_WATT_HOUR, 10000000, ENERGY_WATT_HOUR),
        (EnergyConverter, 10, ENERGY_MEGA_WATT_HOUR, 10000, ENERGY_KILO_WATT_HOUR),
        (PowerConverter, 10, POWER_KILO_WATT, 10000, POWER_WATT),
        (PowerConverter, 10, POWER_WATT, 0.01, POWER_KILO_WATT),
    ],
)
def test_convert(
    converter: type[BaseUnitConverter],
    value: float,
    from_unit: str,
    expected: float,
    to_unit: str,
) -> None:
    """Test conversion to other units."""
    assert converter.convert(value, from_unit, to_unit) == expected
