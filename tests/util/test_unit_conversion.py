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
    VOLUME_CUBIC_FEET,
    VOLUME_CUBIC_METERS,
    VOLUME_FLUID_OUNCE,
    VOLUME_GALLONS,
    VOLUME_LITERS,
    VOLUME_MILLILITERS,
)
from homeassistant.util.unit_conversion import (
    BaseUnitConverter,
    EnergyConverter,
    PowerConverter,
    PressureConverter,
    VolumeConverter,
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
        (VolumeConverter, VOLUME_LITERS),
        (VolumeConverter, VOLUME_MILLILITERS),
        (VolumeConverter, VOLUME_GALLONS),
        (VolumeConverter, VOLUME_FLUID_OUNCE),
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
        (VolumeConverter, VOLUME_LITERS),
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
        (VolumeConverter, VOLUME_GALLONS, VOLUME_LITERS),
    ],
)
def test_convert_nonnumeric_value(
    converter: type[BaseUnitConverter], from_unit: str, to_unit: str
) -> None:
    """Test exception is thrown for nonnumeric type."""
    with pytest.raises(TypeError):
        converter.convert("a", from_unit, to_unit)


@pytest.mark.parametrize(
    "value,from_unit,expected,to_unit",
    [
        (10, ENERGY_WATT_HOUR, 0.01, ENERGY_KILO_WATT_HOUR),
        (10, ENERGY_WATT_HOUR, 0.00001, ENERGY_MEGA_WATT_HOUR),
        (10, ENERGY_KILO_WATT_HOUR, 10000, ENERGY_WATT_HOUR),
        (10, ENERGY_KILO_WATT_HOUR, 0.01, ENERGY_MEGA_WATT_HOUR),
        (10, ENERGY_MEGA_WATT_HOUR, 10000000, ENERGY_WATT_HOUR),
        (10, ENERGY_MEGA_WATT_HOUR, 10000, ENERGY_KILO_WATT_HOUR),
    ],
)
def test_energy_convert(
    value: float,
    from_unit: str,
    expected: float,
    to_unit: str,
) -> None:
    """Test conversion to other units."""
    assert EnergyConverter.convert(value, from_unit, to_unit) == expected


@pytest.mark.parametrize(
    "value,from_unit,expected,to_unit",
    [
        (10, POWER_KILO_WATT, 10000, POWER_WATT),
        (10, POWER_WATT, 0.01, POWER_KILO_WATT),
    ],
)
def test_power_convert(
    value: float,
    from_unit: str,
    expected: float,
    to_unit: str,
) -> None:
    """Test conversion to other units."""
    assert PowerConverter.convert(value, from_unit, to_unit) == expected


@pytest.mark.parametrize(
    "value,from_unit,expected,to_unit",
    [
        (1000, PRESSURE_HPA, pytest.approx(14.5037743897), PRESSURE_PSI),
        (1000, PRESSURE_HPA, pytest.approx(29.5299801647), PRESSURE_INHG),
        (1000, PRESSURE_HPA, pytest.approx(100000), PRESSURE_PA),
        (1000, PRESSURE_HPA, pytest.approx(100), PRESSURE_KPA),
        (1000, PRESSURE_HPA, pytest.approx(1000), PRESSURE_MBAR),
        (1000, PRESSURE_HPA, pytest.approx(100), PRESSURE_CBAR),
        (100, PRESSURE_KPA, pytest.approx(14.5037743897), PRESSURE_PSI),
        (100, PRESSURE_KPA, pytest.approx(29.5299801647), PRESSURE_INHG),
        (100, PRESSURE_KPA, pytest.approx(100000), PRESSURE_PA),
        (100, PRESSURE_KPA, pytest.approx(1000), PRESSURE_HPA),
        (100, PRESSURE_KPA, pytest.approx(1000), PRESSURE_MBAR),
        (100, PRESSURE_KPA, pytest.approx(100), PRESSURE_CBAR),
        (30, PRESSURE_INHG, pytest.approx(14.7346266155), PRESSURE_PSI),
        (30, PRESSURE_INHG, pytest.approx(101.59167), PRESSURE_KPA),
        (30, PRESSURE_INHG, pytest.approx(1015.9167), PRESSURE_HPA),
        (30, PRESSURE_INHG, pytest.approx(101591.67), PRESSURE_PA),
        (30, PRESSURE_INHG, pytest.approx(1015.9167), PRESSURE_MBAR),
        (30, PRESSURE_INHG, pytest.approx(101.59167), PRESSURE_CBAR),
        (30, PRESSURE_INHG, pytest.approx(762.002), PRESSURE_MMHG),
        (30, PRESSURE_MMHG, pytest.approx(0.580102), PRESSURE_PSI),
        (30, PRESSURE_MMHG, pytest.approx(3.99966), PRESSURE_KPA),
        (30, PRESSURE_MMHG, pytest.approx(39.9966), PRESSURE_HPA),
        (30, PRESSURE_MMHG, pytest.approx(3999.66), PRESSURE_PA),
        (30, PRESSURE_MMHG, pytest.approx(39.9966), PRESSURE_MBAR),
        (30, PRESSURE_MMHG, pytest.approx(3.99966), PRESSURE_CBAR),
        (30, PRESSURE_MMHG, pytest.approx(1.181099), PRESSURE_INHG),
    ],
)
def test_pressure_convert(
    value: float,
    from_unit: str,
    expected: float,
    to_unit: str,
) -> None:
    """Test conversion to other units."""
    assert PressureConverter.convert(value, from_unit, to_unit) == expected


@pytest.mark.parametrize(
    "value,from_unit,expected,to_unit",
    [
        (5, VOLUME_LITERS, pytest.approx(1.32086), VOLUME_GALLONS),
        (5, VOLUME_GALLONS, pytest.approx(18.92706), VOLUME_LITERS),
        (5, VOLUME_CUBIC_METERS, pytest.approx(176.5733335), VOLUME_CUBIC_FEET),
        (500, VOLUME_CUBIC_FEET, pytest.approx(14.1584233), VOLUME_CUBIC_METERS),
        (500, VOLUME_CUBIC_FEET, pytest.approx(14.1584233), VOLUME_CUBIC_METERS),
        (500, VOLUME_CUBIC_FEET, pytest.approx(478753.2467), VOLUME_FLUID_OUNCE),
        (500, VOLUME_CUBIC_FEET, pytest.approx(3740.25974), VOLUME_GALLONS),
        (500, VOLUME_CUBIC_FEET, pytest.approx(14158.42329599), VOLUME_LITERS),
        (500, VOLUME_CUBIC_FEET, pytest.approx(14158423.29599), VOLUME_MILLILITERS),
        (500, VOLUME_CUBIC_METERS, 500, VOLUME_CUBIC_METERS),
        (500, VOLUME_CUBIC_METERS, pytest.approx(16907011.35), VOLUME_FLUID_OUNCE),
        (500, VOLUME_CUBIC_METERS, pytest.approx(132086.02617), VOLUME_GALLONS),
        (500, VOLUME_CUBIC_METERS, 500000, VOLUME_LITERS),
        (500, VOLUME_CUBIC_METERS, 500000000, VOLUME_MILLILITERS),
        (500, VOLUME_FLUID_OUNCE, pytest.approx(0.52218967), VOLUME_CUBIC_FEET),
        (500, VOLUME_FLUID_OUNCE, pytest.approx(0.014786764), VOLUME_CUBIC_METERS),
        (500, VOLUME_FLUID_OUNCE, 3.90625, VOLUME_GALLONS),
        (500, VOLUME_FLUID_OUNCE, pytest.approx(14.786764), VOLUME_LITERS),
        (500, VOLUME_FLUID_OUNCE, pytest.approx(14786.764), VOLUME_MILLILITERS),
        (500, VOLUME_GALLONS, pytest.approx(66.84027), VOLUME_CUBIC_FEET),
        (500, VOLUME_GALLONS, pytest.approx(1.892706), VOLUME_CUBIC_METERS),
        (500, VOLUME_GALLONS, 64000, VOLUME_FLUID_OUNCE),
        (500, VOLUME_GALLONS, pytest.approx(1892.70589), VOLUME_LITERS),
        (500, VOLUME_GALLONS, pytest.approx(1892705.89), VOLUME_MILLILITERS),
        (500, VOLUME_LITERS, pytest.approx(17.65733), VOLUME_CUBIC_FEET),
        (500, VOLUME_LITERS, 0.5, VOLUME_CUBIC_METERS),
        (500, VOLUME_LITERS, pytest.approx(16907.011), VOLUME_FLUID_OUNCE),
        (500, VOLUME_LITERS, pytest.approx(132.086), VOLUME_GALLONS),
        (500, VOLUME_LITERS, 500000, VOLUME_MILLILITERS),
        (500, VOLUME_MILLILITERS, pytest.approx(0.01765733), VOLUME_CUBIC_FEET),
        (500, VOLUME_MILLILITERS, 0.0005, VOLUME_CUBIC_METERS),
        (500, VOLUME_MILLILITERS, pytest.approx(16.907), VOLUME_FLUID_OUNCE),
        (500, VOLUME_MILLILITERS, pytest.approx(0.132086), VOLUME_GALLONS),
        (500, VOLUME_MILLILITERS, 0.5, VOLUME_LITERS),
    ],
)
def test_volume_convert(
    value: float,
    from_unit: str,
    expected: float,
    to_unit: str,
) -> None:
    """Test conversion to other units."""
    assert VolumeConverter.convert(value, from_unit, to_unit) == expected
