"""Test Home Assistant eneergy utility functions."""
import pytest

from homeassistant.const import (
    ENERGY_KILO_WATT_HOUR,
    ENERGY_MEGA_WATT_HOUR,
    ENERGY_WATT_HOUR,
    POWER_KILO_WATT,
    POWER_WATT,
    PRESSURE_CBAR,
    PRESSURE_HPA,
    PRESSURE_INHG,
    PRESSURE_KPA,
    PRESSURE_MBAR,
    PRESSURE_MMHG,
    PRESSURE_PA,
    PRESSURE_PSI,
)
from homeassistant.util.unit_conversion import (
    BaseUnitConverter,
    EnergyConverter,
    PowerConverter,
    PressureConverter,
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
        (PressureConverter, PRESSURE_PA),
        (PressureConverter, PRESSURE_HPA),
        (PressureConverter, PRESSURE_MBAR),
        (PressureConverter, PRESSURE_INHG),
        (PressureConverter, PRESSURE_KPA),
        (PressureConverter, PRESSURE_CBAR),
        (PressureConverter, PRESSURE_MMHG),
        (PressureConverter, PRESSURE_PSI),
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
        (PressureConverter, PRESSURE_PA),
    ],
)
def test_convert_invalid_unit(
    converter: type[BaseUnitConverter], valid_unit: str
) -> None:
    """Test exception is thrown for invalid units."""
    with pytest.raises(ValueError):
        converter.convert(5, INVALID_SYMBOL, valid_unit)

    with pytest.raises(ValueError):
        converter.convert(5, valid_unit, INVALID_SYMBOL)


@pytest.mark.parametrize(
    "converter,from_unit,to_unit",
    [
        (EnergyConverter, ENERGY_WATT_HOUR, ENERGY_KILO_WATT_HOUR),
        (PowerConverter, POWER_WATT, POWER_KILO_WATT),
        (PressureConverter, PRESSURE_HPA, PRESSURE_INHG),
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
        (
            PressureConverter,
            1000,
            PRESSURE_HPA,
            pytest.approx(14.5037743897),
            PRESSURE_PSI,
        ),
        (
            PressureConverter,
            1000,
            PRESSURE_HPA,
            pytest.approx(29.5299801647),
            PRESSURE_INHG,
        ),
        (
            PressureConverter,
            1000,
            PRESSURE_HPA,
            pytest.approx(100000),
            PRESSURE_PA,
        ),
        (
            PressureConverter,
            1000,
            PRESSURE_HPA,
            pytest.approx(100),
            PRESSURE_KPA,
        ),
        (
            PressureConverter,
            1000,
            PRESSURE_HPA,
            pytest.approx(1000),
            PRESSURE_MBAR,
        ),
        (
            PressureConverter,
            1000,
            PRESSURE_HPA,
            pytest.approx(100),
            PRESSURE_CBAR,
        ),
        (
            PressureConverter,
            100,
            PRESSURE_KPA,
            pytest.approx(14.5037743897),
            PRESSURE_PSI,
        ),
        (
            PressureConverter,
            100,
            PRESSURE_KPA,
            pytest.approx(29.5299801647),
            PRESSURE_INHG,
        ),
        (
            PressureConverter,
            100,
            PRESSURE_KPA,
            pytest.approx(100000),
            PRESSURE_PA,
        ),
        (
            PressureConverter,
            100,
            PRESSURE_KPA,
            pytest.approx(1000),
            PRESSURE_HPA,
        ),
        (
            PressureConverter,
            100,
            PRESSURE_KPA,
            pytest.approx(1000),
            PRESSURE_MBAR,
        ),
        (
            PressureConverter,
            100,
            PRESSURE_KPA,
            pytest.approx(100),
            PRESSURE_CBAR,
        ),
        (
            PressureConverter,
            30,
            PRESSURE_INHG,
            pytest.approx(14.7346266155),
            PRESSURE_PSI,
        ),
        (
            PressureConverter,
            30,
            PRESSURE_INHG,
            pytest.approx(101.59167),
            PRESSURE_KPA,
        ),
        (
            PressureConverter,
            30,
            PRESSURE_INHG,
            pytest.approx(1015.9167),
            PRESSURE_HPA,
        ),
        (
            PressureConverter,
            30,
            PRESSURE_INHG,
            pytest.approx(101591.67),
            PRESSURE_PA,
        ),
        (
            PressureConverter,
            30,
            PRESSURE_INHG,
            pytest.approx(1015.9167),
            PRESSURE_MBAR,
        ),
        (
            PressureConverter,
            30,
            PRESSURE_INHG,
            pytest.approx(101.59167),
            PRESSURE_CBAR,
        ),
        (
            PressureConverter,
            30,
            PRESSURE_INHG,
            pytest.approx(762.002),
            PRESSURE_MMHG,
        ),
        (
            PressureConverter,
            30,
            PRESSURE_MMHG,
            pytest.approx(0.580102),
            PRESSURE_PSI,
        ),
        (
            PressureConverter,
            30,
            PRESSURE_MMHG,
            pytest.approx(3.99966),
            PRESSURE_KPA,
        ),
        (
            PressureConverter,
            30,
            PRESSURE_MMHG,
            pytest.approx(39.9966),
            PRESSURE_HPA,
        ),
        (
            PressureConverter,
            30,
            PRESSURE_MMHG,
            pytest.approx(3999.66),
            PRESSURE_PA,
        ),
        (
            PressureConverter,
            30,
            PRESSURE_MMHG,
            pytest.approx(39.9966),
            PRESSURE_MBAR,
        ),
        (
            PressureConverter,
            30,
            PRESSURE_MMHG,
            pytest.approx(3.99966),
            PRESSURE_CBAR,
        ),
        (
            PressureConverter,
            30,
            PRESSURE_MMHG,
            pytest.approx(1.181099),
            PRESSURE_INHG,
        ),
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
