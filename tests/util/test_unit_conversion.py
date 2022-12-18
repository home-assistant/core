"""Test Home Assistant eneergy utility functions."""
import pytest

from homeassistant.const import (
    UnitOfEnergy,
    UnitOfLength,
    UnitOfMass,
    UnitOfPower,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfVolume,
    UnitOfVolumetricFlux,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.unit_conversion import (
    BaseUnitConverter,
    DistanceConverter,
    EnergyConverter,
    MassConverter,
    PowerConverter,
    PressureConverter,
    SpeedConverter,
    TemperatureConverter,
    VolumeConverter,
)

INVALID_SYMBOL = "bob"


@pytest.mark.parametrize(
    "converter,valid_unit",
    [
        (DistanceConverter, UnitOfLength.KILOMETERS),
        (DistanceConverter, UnitOfLength.METERS),
        (DistanceConverter, UnitOfLength.CENTIMETERS),
        (DistanceConverter, UnitOfLength.MILLIMETERS),
        (DistanceConverter, UnitOfLength.MILES),
        (DistanceConverter, UnitOfLength.YARDS),
        (DistanceConverter, UnitOfLength.FEET),
        (DistanceConverter, UnitOfLength.INCHES),
        (EnergyConverter, UnitOfEnergy.WATT_HOUR),
        (EnergyConverter, UnitOfEnergy.KILO_WATT_HOUR),
        (EnergyConverter, UnitOfEnergy.MEGA_WATT_HOUR),
        (EnergyConverter, UnitOfEnergy.GIGA_JOULE),
        (MassConverter, UnitOfMass.GRAMS),
        (MassConverter, UnitOfMass.KILOGRAMS),
        (MassConverter, UnitOfMass.MICROGRAMS),
        (MassConverter, UnitOfMass.MILLIGRAMS),
        (MassConverter, UnitOfMass.OUNCES),
        (MassConverter, UnitOfMass.POUNDS),
        (PowerConverter, UnitOfPower.WATT),
        (PowerConverter, UnitOfPower.KILO_WATT),
        (PressureConverter, UnitOfPressure.PA),
        (PressureConverter, UnitOfPressure.HPA),
        (PressureConverter, UnitOfPressure.MBAR),
        (PressureConverter, UnitOfPressure.INHG),
        (PressureConverter, UnitOfPressure.KPA),
        (PressureConverter, UnitOfPressure.CBAR),
        (PressureConverter, UnitOfPressure.MMHG),
        (PressureConverter, UnitOfPressure.PSI),
        (SpeedConverter, UnitOfVolumetricFlux.INCHES_PER_DAY),
        (SpeedConverter, UnitOfVolumetricFlux.INCHES_PER_HOUR),
        (SpeedConverter, UnitOfVolumetricFlux.MILLIMETERS_PER_DAY),
        (SpeedConverter, UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR),
        (SpeedConverter, UnitOfSpeed.FEET_PER_SECOND),
        (SpeedConverter, UnitOfSpeed.KILOMETERS_PER_HOUR),
        (SpeedConverter, UnitOfSpeed.KNOTS),
        (SpeedConverter, UnitOfSpeed.METERS_PER_SECOND),
        (SpeedConverter, UnitOfSpeed.MILES_PER_HOUR),
        (TemperatureConverter, UnitOfTemperature.CELSIUS),
        (TemperatureConverter, UnitOfTemperature.FAHRENHEIT),
        (TemperatureConverter, UnitOfTemperature.KELVIN),
        (VolumeConverter, UnitOfVolume.LITERS),
        (VolumeConverter, UnitOfVolume.MILLILITERS),
        (VolumeConverter, UnitOfVolume.GALLONS),
        (VolumeConverter, UnitOfVolume.FLUID_OUNCES),
    ],
)
def test_convert_same_unit(converter: type[BaseUnitConverter], valid_unit: str) -> None:
    """Test conversion from any valid unit to same unit."""
    assert converter.convert(2, valid_unit, valid_unit) == 2


@pytest.mark.parametrize(
    "converter,valid_unit",
    [
        (DistanceConverter, UnitOfLength.KILOMETERS),
        (EnergyConverter, UnitOfEnergy.KILO_WATT_HOUR),
        (MassConverter, UnitOfMass.GRAMS),
        (PowerConverter, UnitOfPower.WATT),
        (PressureConverter, UnitOfPressure.PA),
        (SpeedConverter, UnitOfSpeed.KILOMETERS_PER_HOUR),
        (TemperatureConverter, UnitOfTemperature.CELSIUS),
        (TemperatureConverter, UnitOfTemperature.FAHRENHEIT),
        (TemperatureConverter, UnitOfTemperature.KELVIN),
        (VolumeConverter, UnitOfVolume.LITERS),
    ],
)
def test_convert_invalid_unit(
    converter: type[BaseUnitConverter], valid_unit: str
) -> None:
    """Test exception is thrown for invalid units."""
    with pytest.raises(HomeAssistantError, match="is not a recognized .* unit"):
        converter.convert(5, INVALID_SYMBOL, valid_unit)

    with pytest.raises(HomeAssistantError, match="is not a recognized .* unit"):
        converter.convert(5, valid_unit, INVALID_SYMBOL)


@pytest.mark.parametrize(
    "converter,from_unit,to_unit",
    [
        (DistanceConverter, UnitOfLength.KILOMETERS, UnitOfLength.METERS),
        (EnergyConverter, UnitOfEnergy.WATT_HOUR, UnitOfEnergy.KILO_WATT_HOUR),
        (MassConverter, UnitOfMass.GRAMS, UnitOfMass.KILOGRAMS),
        (PowerConverter, UnitOfPower.WATT, UnitOfPower.KILO_WATT),
        (PressureConverter, UnitOfPressure.HPA, UnitOfPressure.INHG),
        (SpeedConverter, UnitOfSpeed.KILOMETERS_PER_HOUR, UnitOfSpeed.MILES_PER_HOUR),
        (TemperatureConverter, UnitOfTemperature.CELSIUS, UnitOfTemperature.FAHRENHEIT),
        (VolumeConverter, UnitOfVolume.GALLONS, UnitOfVolume.LITERS),
    ],
)
def test_convert_nonnumeric_value(
    converter: type[BaseUnitConverter], from_unit: str, to_unit: str
) -> None:
    """Test exception is thrown for nonnumeric type."""
    with pytest.raises(TypeError):
        converter.convert("a", from_unit, to_unit)


@pytest.mark.parametrize(
    "converter,from_unit,to_unit,expected",
    [
        (DistanceConverter, UnitOfLength.KILOMETERS, UnitOfLength.METERS, 1 / 1000),
        (EnergyConverter, UnitOfEnergy.WATT_HOUR, UnitOfEnergy.KILO_WATT_HOUR, 1000),
        (PowerConverter, UnitOfPower.WATT, UnitOfPower.KILO_WATT, 1000),
        (
            PressureConverter,
            UnitOfPressure.HPA,
            UnitOfPressure.INHG,
            pytest.approx(33.86389),
        ),
        (
            SpeedConverter,
            UnitOfSpeed.KILOMETERS_PER_HOUR,
            UnitOfSpeed.MILES_PER_HOUR,
            pytest.approx(1.609343),
        ),
        (
            TemperatureConverter,
            UnitOfTemperature.CELSIUS,
            UnitOfTemperature.FAHRENHEIT,
            1 / 1.8,
        ),
        (
            VolumeConverter,
            UnitOfVolume.GALLONS,
            UnitOfVolume.LITERS,
            pytest.approx(0.264172),
        ),
    ],
)
def test_get_unit_ratio(
    converter: type[BaseUnitConverter], from_unit: str, to_unit: str, expected: float
) -> None:
    """Test unit ratio."""
    assert converter.get_unit_ratio(from_unit, to_unit) == expected


@pytest.mark.parametrize(
    "value,from_unit,expected,to_unit",
    [
        (5, UnitOfLength.MILES, pytest.approx(8.04672), UnitOfLength.KILOMETERS),
        (5, UnitOfLength.MILES, pytest.approx(8046.72), UnitOfLength.METERS),
        (5, UnitOfLength.MILES, pytest.approx(804672.0), UnitOfLength.CENTIMETERS),
        (5, UnitOfLength.MILES, pytest.approx(8046720.0), UnitOfLength.MILLIMETERS),
        (5, UnitOfLength.MILES, pytest.approx(8800.0), UnitOfLength.YARDS),
        (5, UnitOfLength.MILES, pytest.approx(26400.0008448), UnitOfLength.FEET),
        (5, UnitOfLength.MILES, pytest.approx(316800.171072), UnitOfLength.INCHES),
        (
            5,
            UnitOfLength.YARDS,
            pytest.approx(0.0045720000000000005),
            UnitOfLength.KILOMETERS,
        ),
        (5, UnitOfLength.YARDS, pytest.approx(4.572), UnitOfLength.METERS),
        (5, UnitOfLength.YARDS, pytest.approx(457.2), UnitOfLength.CENTIMETERS),
        (5, UnitOfLength.YARDS, pytest.approx(4572), UnitOfLength.MILLIMETERS),
        (5, UnitOfLength.YARDS, pytest.approx(0.002840908212), UnitOfLength.MILES),
        (5, UnitOfLength.YARDS, pytest.approx(15.00000048), UnitOfLength.FEET),
        (5, UnitOfLength.YARDS, pytest.approx(180.0000972), UnitOfLength.INCHES),
        (5000, UnitOfLength.FEET, pytest.approx(1.524), UnitOfLength.KILOMETERS),
        (5000, UnitOfLength.FEET, pytest.approx(1524), UnitOfLength.METERS),
        (5000, UnitOfLength.FEET, pytest.approx(152400.0), UnitOfLength.CENTIMETERS),
        (5000, UnitOfLength.FEET, pytest.approx(1524000.0), UnitOfLength.MILLIMETERS),
        (
            5000,
            UnitOfLength.FEET,
            pytest.approx(0.9469694040000001),
            UnitOfLength.MILES,
        ),
        (5000, UnitOfLength.FEET, pytest.approx(1666.66667), UnitOfLength.YARDS),
        (
            5000,
            UnitOfLength.FEET,
            pytest.approx(60000.032400000004),
            UnitOfLength.INCHES,
        ),
        (5000, UnitOfLength.INCHES, pytest.approx(0.127), UnitOfLength.KILOMETERS),
        (5000, UnitOfLength.INCHES, pytest.approx(127.0), UnitOfLength.METERS),
        (5000, UnitOfLength.INCHES, pytest.approx(12700.0), UnitOfLength.CENTIMETERS),
        (5000, UnitOfLength.INCHES, pytest.approx(127000.0), UnitOfLength.MILLIMETERS),
        (5000, UnitOfLength.INCHES, pytest.approx(0.078914117), UnitOfLength.MILES),
        (5000, UnitOfLength.INCHES, pytest.approx(138.88889), UnitOfLength.YARDS),
        (5000, UnitOfLength.INCHES, pytest.approx(416.66668), UnitOfLength.FEET),
        (5, UnitOfLength.KILOMETERS, pytest.approx(5000), UnitOfLength.METERS),
        (5, UnitOfLength.KILOMETERS, pytest.approx(500000), UnitOfLength.CENTIMETERS),
        (5, UnitOfLength.KILOMETERS, pytest.approx(5000000), UnitOfLength.MILLIMETERS),
        (5, UnitOfLength.KILOMETERS, pytest.approx(3.106855), UnitOfLength.MILES),
        (5, UnitOfLength.KILOMETERS, pytest.approx(5468.066), UnitOfLength.YARDS),
        (5, UnitOfLength.KILOMETERS, pytest.approx(16404.2), UnitOfLength.FEET),
        (5, UnitOfLength.KILOMETERS, pytest.approx(196850.5), UnitOfLength.INCHES),
        (5000, UnitOfLength.METERS, pytest.approx(5), UnitOfLength.KILOMETERS),
        (5000, UnitOfLength.METERS, pytest.approx(500000), UnitOfLength.CENTIMETERS),
        (5000, UnitOfLength.METERS, pytest.approx(5000000), UnitOfLength.MILLIMETERS),
        (5000, UnitOfLength.METERS, pytest.approx(3.106855), UnitOfLength.MILES),
        (5000, UnitOfLength.METERS, pytest.approx(5468.066), UnitOfLength.YARDS),
        (5000, UnitOfLength.METERS, pytest.approx(16404.2), UnitOfLength.FEET),
        (5000, UnitOfLength.METERS, pytest.approx(196850.5), UnitOfLength.INCHES),
        (500000, UnitOfLength.CENTIMETERS, pytest.approx(5), UnitOfLength.KILOMETERS),
        (500000, UnitOfLength.CENTIMETERS, pytest.approx(5000), UnitOfLength.METERS),
        (
            500000,
            UnitOfLength.CENTIMETERS,
            pytest.approx(5000000),
            UnitOfLength.MILLIMETERS,
        ),
        (500000, UnitOfLength.CENTIMETERS, pytest.approx(3.106855), UnitOfLength.MILES),
        (500000, UnitOfLength.CENTIMETERS, pytest.approx(5468.066), UnitOfLength.YARDS),
        (500000, UnitOfLength.CENTIMETERS, pytest.approx(16404.2), UnitOfLength.FEET),
        (
            500000,
            UnitOfLength.CENTIMETERS,
            pytest.approx(196850.5),
            UnitOfLength.INCHES,
        ),
        (5000000, UnitOfLength.MILLIMETERS, pytest.approx(5), UnitOfLength.KILOMETERS),
        (5000000, UnitOfLength.MILLIMETERS, pytest.approx(5000), UnitOfLength.METERS),
        (
            5000000,
            UnitOfLength.MILLIMETERS,
            pytest.approx(500000),
            UnitOfLength.CENTIMETERS,
        ),
        (
            5000000,
            UnitOfLength.MILLIMETERS,
            pytest.approx(3.106855),
            UnitOfLength.MILES,
        ),
        (
            5000000,
            UnitOfLength.MILLIMETERS,
            pytest.approx(5468.066),
            UnitOfLength.YARDS,
        ),
        (5000000, UnitOfLength.MILLIMETERS, pytest.approx(16404.2), UnitOfLength.FEET),
        (
            5000000,
            UnitOfLength.MILLIMETERS,
            pytest.approx(196850.5),
            UnitOfLength.INCHES,
        ),
    ],
)
def test_distance_convert(
    value: float,
    from_unit: str,
    expected: float,
    to_unit: str,
) -> None:
    """Test conversion to other units."""
    assert DistanceConverter.convert(value, from_unit, to_unit) == expected


@pytest.mark.parametrize(
    "value,from_unit,expected,to_unit",
    [
        (10, UnitOfEnergy.WATT_HOUR, 0.01, UnitOfEnergy.KILO_WATT_HOUR),
        (10, UnitOfEnergy.WATT_HOUR, 0.00001, UnitOfEnergy.MEGA_WATT_HOUR),
        (10, UnitOfEnergy.KILO_WATT_HOUR, 10000, UnitOfEnergy.WATT_HOUR),
        (10, UnitOfEnergy.KILO_WATT_HOUR, 0.01, UnitOfEnergy.MEGA_WATT_HOUR),
        (10, UnitOfEnergy.MEGA_WATT_HOUR, 10000000, UnitOfEnergy.WATT_HOUR),
        (10, UnitOfEnergy.MEGA_WATT_HOUR, 10000, UnitOfEnergy.KILO_WATT_HOUR),
        (10, UnitOfEnergy.GIGA_JOULE, 10000 / 3.6, UnitOfEnergy.KILO_WATT_HOUR),
        (10, UnitOfEnergy.GIGA_JOULE, 10 / 3.6, UnitOfEnergy.MEGA_WATT_HOUR),
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
        (10, UnitOfMass.KILOGRAMS, 10000, UnitOfMass.GRAMS),
        (10, UnitOfMass.KILOGRAMS, 10000000, UnitOfMass.MILLIGRAMS),
        (10, UnitOfMass.KILOGRAMS, 10000000000, UnitOfMass.MICROGRAMS),
        (10, UnitOfMass.KILOGRAMS, pytest.approx(352.73961), UnitOfMass.OUNCES),
        (10, UnitOfMass.KILOGRAMS, pytest.approx(22.046226), UnitOfMass.POUNDS),
        (10, UnitOfMass.GRAMS, 0.01, UnitOfMass.KILOGRAMS),
        (10, UnitOfMass.GRAMS, 10000, UnitOfMass.MILLIGRAMS),
        (10, UnitOfMass.GRAMS, 10000000, UnitOfMass.MICROGRAMS),
        (10, UnitOfMass.GRAMS, pytest.approx(0.35273961), UnitOfMass.OUNCES),
        (10, UnitOfMass.GRAMS, pytest.approx(0.022046226), UnitOfMass.POUNDS),
        (10, UnitOfMass.MILLIGRAMS, 0.00001, UnitOfMass.KILOGRAMS),
        (10, UnitOfMass.MILLIGRAMS, 0.01, UnitOfMass.GRAMS),
        (10, UnitOfMass.MILLIGRAMS, 10000, UnitOfMass.MICROGRAMS),
        (10, UnitOfMass.MILLIGRAMS, pytest.approx(0.00035273961), UnitOfMass.OUNCES),
        (10, UnitOfMass.MILLIGRAMS, pytest.approx(0.000022046226), UnitOfMass.POUNDS),
        (10000, UnitOfMass.MICROGRAMS, 0.00001, UnitOfMass.KILOGRAMS),
        (10000, UnitOfMass.MICROGRAMS, 0.01, UnitOfMass.GRAMS),
        (10000, UnitOfMass.MICROGRAMS, 10, UnitOfMass.MILLIGRAMS),
        (10000, UnitOfMass.MICROGRAMS, pytest.approx(0.00035273961), UnitOfMass.OUNCES),
        (
            10000,
            UnitOfMass.MICROGRAMS,
            pytest.approx(0.000022046226),
            UnitOfMass.POUNDS,
        ),
        (1, UnitOfMass.POUNDS, 0.45359237, UnitOfMass.KILOGRAMS),
        (1, UnitOfMass.POUNDS, 453.59237, UnitOfMass.GRAMS),
        (1, UnitOfMass.POUNDS, 453592.37, UnitOfMass.MILLIGRAMS),
        (1, UnitOfMass.POUNDS, 453592370, UnitOfMass.MICROGRAMS),
        (1, UnitOfMass.POUNDS, 16, UnitOfMass.OUNCES),
        (16, UnitOfMass.OUNCES, 0.45359237, UnitOfMass.KILOGRAMS),
        (16, UnitOfMass.OUNCES, 453.59237, UnitOfMass.GRAMS),
        (16, UnitOfMass.OUNCES, 453592.37, UnitOfMass.MILLIGRAMS),
        (16, UnitOfMass.OUNCES, 453592370, UnitOfMass.MICROGRAMS),
        (16, UnitOfMass.OUNCES, 1, UnitOfMass.POUNDS),
        (1, UnitOfMass.STONES, pytest.approx(6.350293), UnitOfMass.KILOGRAMS),
        (1, UnitOfMass.STONES, pytest.approx(6350.293), UnitOfMass.GRAMS),
        (1, UnitOfMass.STONES, pytest.approx(6350293), UnitOfMass.MILLIGRAMS),
        (1, UnitOfMass.STONES, pytest.approx(14), UnitOfMass.POUNDS),
        (1, UnitOfMass.STONES, pytest.approx(224), UnitOfMass.OUNCES),
    ],
)
def test_mass_convert(
    value: float,
    from_unit: str,
    expected: float,
    to_unit: str,
) -> None:
    """Test conversion to other units."""
    assert MassConverter.convert(value, from_unit, to_unit) == expected


@pytest.mark.parametrize(
    "value,from_unit,expected,to_unit",
    [
        (10, UnitOfPower.KILO_WATT, 10000, UnitOfPower.WATT),
        (10, UnitOfPower.WATT, 0.01, UnitOfPower.KILO_WATT),
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
        (1000, UnitOfPressure.HPA, pytest.approx(14.5037743897), UnitOfPressure.PSI),
        (1000, UnitOfPressure.HPA, pytest.approx(29.5299801647), UnitOfPressure.INHG),
        (1000, UnitOfPressure.HPA, pytest.approx(100000), UnitOfPressure.PA),
        (1000, UnitOfPressure.HPA, pytest.approx(100), UnitOfPressure.KPA),
        (1000, UnitOfPressure.HPA, pytest.approx(1000), UnitOfPressure.MBAR),
        (1000, UnitOfPressure.HPA, pytest.approx(100), UnitOfPressure.CBAR),
        (100, UnitOfPressure.KPA, pytest.approx(14.5037743897), UnitOfPressure.PSI),
        (100, UnitOfPressure.KPA, pytest.approx(29.5299801647), UnitOfPressure.INHG),
        (100, UnitOfPressure.KPA, pytest.approx(100000), UnitOfPressure.PA),
        (100, UnitOfPressure.KPA, pytest.approx(1000), UnitOfPressure.HPA),
        (100, UnitOfPressure.KPA, pytest.approx(1000), UnitOfPressure.MBAR),
        (100, UnitOfPressure.KPA, pytest.approx(100), UnitOfPressure.CBAR),
        (30, UnitOfPressure.INHG, pytest.approx(14.7346266155), UnitOfPressure.PSI),
        (30, UnitOfPressure.INHG, pytest.approx(101.59167), UnitOfPressure.KPA),
        (30, UnitOfPressure.INHG, pytest.approx(1015.9167), UnitOfPressure.HPA),
        (30, UnitOfPressure.INHG, pytest.approx(101591.67), UnitOfPressure.PA),
        (30, UnitOfPressure.INHG, pytest.approx(1015.9167), UnitOfPressure.MBAR),
        (30, UnitOfPressure.INHG, pytest.approx(101.59167), UnitOfPressure.CBAR),
        (30, UnitOfPressure.INHG, pytest.approx(762), UnitOfPressure.MMHG),
        (30, UnitOfPressure.MMHG, pytest.approx(0.580103), UnitOfPressure.PSI),
        (30, UnitOfPressure.MMHG, pytest.approx(3.99967), UnitOfPressure.KPA),
        (30, UnitOfPressure.MMHG, pytest.approx(39.9967), UnitOfPressure.HPA),
        (30, UnitOfPressure.MMHG, pytest.approx(3999.67), UnitOfPressure.PA),
        (30, UnitOfPressure.MMHG, pytest.approx(39.9967), UnitOfPressure.MBAR),
        (30, UnitOfPressure.MMHG, pytest.approx(3.99967), UnitOfPressure.CBAR),
        (30, UnitOfPressure.MMHG, pytest.approx(1.181102), UnitOfPressure.INHG),
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
        # 5 km/h / 1.609 km/mi = 3.10686 mi/h
        (
            5,
            UnitOfSpeed.KILOMETERS_PER_HOUR,
            pytest.approx(3.106856),
            UnitOfSpeed.MILES_PER_HOUR,
        ),
        # 5 mi/h * 1.609 km/mi = 8.04672 km/h
        (5, UnitOfSpeed.MILES_PER_HOUR, 8.04672, UnitOfSpeed.KILOMETERS_PER_HOUR),
        # 5 in/day * 25.4 mm/in = 127 mm/day
        (
            5,
            UnitOfVolumetricFlux.INCHES_PER_DAY,
            127,
            UnitOfVolumetricFlux.MILLIMETERS_PER_DAY,
        ),
        # 5 mm/day / 25.4 mm/in = 0.19685 in/day
        (
            5,
            UnitOfVolumetricFlux.MILLIMETERS_PER_DAY,
            pytest.approx(0.1968504),
            UnitOfVolumetricFlux.INCHES_PER_DAY,
        ),
        # 48 mm/day = 2 mm/h
        (
            48,
            UnitOfVolumetricFlux.MILLIMETERS_PER_DAY,
            pytest.approx(2),
            UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        ),
        # 5 in/hr * 24 hr/day = 3048 mm/day
        (
            5,
            UnitOfVolumetricFlux.INCHES_PER_HOUR,
            3048,
            UnitOfVolumetricFlux.MILLIMETERS_PER_DAY,
        ),
        # 5 m/s * 39.3701 in/m * 3600 s/hr = 708661
        (
            5,
            UnitOfSpeed.METERS_PER_SECOND,
            pytest.approx(708661.42),
            UnitOfVolumetricFlux.INCHES_PER_HOUR,
        ),
        # 5000 in/h / 39.3701 in/m / 3600 s/h = 0.03528 m/s
        (
            5000,
            UnitOfVolumetricFlux.INCHES_PER_HOUR,
            pytest.approx(0.0352778),
            UnitOfSpeed.METERS_PER_SECOND,
        ),
        # 5 kt * 1852 m/nmi / 3600 s/h = 2.5722 m/s
        (5, UnitOfSpeed.KNOTS, pytest.approx(2.57222), UnitOfSpeed.METERS_PER_SECOND),
        # 5 ft/s * 0.3048 m/ft = 1.524 m/s
        (
            5,
            UnitOfSpeed.FEET_PER_SECOND,
            pytest.approx(1.524),
            UnitOfSpeed.METERS_PER_SECOND,
        ),
    ],
)
def test_speed_convert(
    value: float,
    from_unit: str,
    expected: float,
    to_unit: str,
) -> None:
    """Test conversion to other units."""
    assert SpeedConverter.convert(value, from_unit, to_unit) == expected


@pytest.mark.parametrize(
    "value,from_unit,expected,to_unit",
    [
        (100, UnitOfTemperature.CELSIUS, 212, UnitOfTemperature.FAHRENHEIT),
        (100, UnitOfTemperature.CELSIUS, 373.15, UnitOfTemperature.KELVIN),
        (
            100,
            UnitOfTemperature.FAHRENHEIT,
            pytest.approx(37.77777777777778),
            UnitOfTemperature.CELSIUS,
        ),
        (
            100,
            UnitOfTemperature.FAHRENHEIT,
            pytest.approx(310.92777777777775),
            UnitOfTemperature.KELVIN,
        ),
        (
            100,
            UnitOfTemperature.KELVIN,
            pytest.approx(-173.15),
            UnitOfTemperature.CELSIUS,
        ),
        (
            100,
            UnitOfTemperature.KELVIN,
            pytest.approx(-279.66999999999996),
            UnitOfTemperature.FAHRENHEIT,
        ),
    ],
)
def test_temperature_convert(
    value: float, from_unit: str, expected: float, to_unit: str
) -> None:
    """Test conversion to other units."""
    assert TemperatureConverter.convert(value, from_unit, to_unit) == expected


@pytest.mark.parametrize(
    "value,from_unit,expected,to_unit",
    [
        (100, UnitOfTemperature.CELSIUS, 180, UnitOfTemperature.FAHRENHEIT),
        (100, UnitOfTemperature.CELSIUS, 100, UnitOfTemperature.KELVIN),
        (
            100,
            UnitOfTemperature.FAHRENHEIT,
            pytest.approx(55.55555555555556),
            UnitOfTemperature.CELSIUS,
        ),
        (
            100,
            UnitOfTemperature.FAHRENHEIT,
            pytest.approx(55.55555555555556),
            UnitOfTemperature.KELVIN,
        ),
        (100, UnitOfTemperature.KELVIN, 100, UnitOfTemperature.CELSIUS),
        (100, UnitOfTemperature.KELVIN, 180, UnitOfTemperature.FAHRENHEIT),
    ],
)
def test_temperature_convert_with_interval(
    value: float, from_unit: str, expected: float, to_unit: str
) -> None:
    """Test conversion to other units."""
    assert TemperatureConverter.convert_interval(value, from_unit, to_unit) == expected


@pytest.mark.parametrize(
    "value,from_unit,expected,to_unit",
    [
        (5, UnitOfVolume.LITERS, pytest.approx(1.32086), UnitOfVolume.GALLONS),
        (5, UnitOfVolume.GALLONS, pytest.approx(18.92706), UnitOfVolume.LITERS),
        (
            5,
            UnitOfVolume.CUBIC_METERS,
            pytest.approx(176.5733335),
            UnitOfVolume.CUBIC_FEET,
        ),
        (
            500,
            UnitOfVolume.CUBIC_FEET,
            pytest.approx(14.1584233),
            UnitOfVolume.CUBIC_METERS,
        ),
        (
            500,
            UnitOfVolume.CUBIC_FEET,
            pytest.approx(14.1584233),
            UnitOfVolume.CUBIC_METERS,
        ),
        (
            500,
            UnitOfVolume.CUBIC_FEET,
            pytest.approx(478753.2467),
            UnitOfVolume.FLUID_OUNCES,
        ),
        (500, UnitOfVolume.CUBIC_FEET, pytest.approx(3740.25974), UnitOfVolume.GALLONS),
        (
            500,
            UnitOfVolume.CUBIC_FEET,
            pytest.approx(14158.42329599),
            UnitOfVolume.LITERS,
        ),
        (
            500,
            UnitOfVolume.CUBIC_FEET,
            pytest.approx(14158423.29599),
            UnitOfVolume.MILLILITERS,
        ),
        (500, UnitOfVolume.CUBIC_METERS, 500, UnitOfVolume.CUBIC_METERS),
        (
            500,
            UnitOfVolume.CUBIC_METERS,
            pytest.approx(16907011.35),
            UnitOfVolume.FLUID_OUNCES,
        ),
        (
            500,
            UnitOfVolume.CUBIC_METERS,
            pytest.approx(132086.02617),
            UnitOfVolume.GALLONS,
        ),
        (500, UnitOfVolume.CUBIC_METERS, 500000, UnitOfVolume.LITERS),
        (500, UnitOfVolume.CUBIC_METERS, 500000000, UnitOfVolume.MILLILITERS),
        (
            500,
            UnitOfVolume.FLUID_OUNCES,
            pytest.approx(0.52218967),
            UnitOfVolume.CUBIC_FEET,
        ),
        (
            500,
            UnitOfVolume.FLUID_OUNCES,
            pytest.approx(0.014786764),
            UnitOfVolume.CUBIC_METERS,
        ),
        (500, UnitOfVolume.FLUID_OUNCES, 3.90625, UnitOfVolume.GALLONS),
        (500, UnitOfVolume.FLUID_OUNCES, pytest.approx(14.786764), UnitOfVolume.LITERS),
        (
            500,
            UnitOfVolume.FLUID_OUNCES,
            pytest.approx(14786.764),
            UnitOfVolume.MILLILITERS,
        ),
        (500, UnitOfVolume.GALLONS, pytest.approx(66.84027), UnitOfVolume.CUBIC_FEET),
        (500, UnitOfVolume.GALLONS, pytest.approx(1.892706), UnitOfVolume.CUBIC_METERS),
        (500, UnitOfVolume.GALLONS, 64000, UnitOfVolume.FLUID_OUNCES),
        (500, UnitOfVolume.GALLONS, pytest.approx(1892.70589), UnitOfVolume.LITERS),
        (
            500,
            UnitOfVolume.GALLONS,
            pytest.approx(1892705.89),
            UnitOfVolume.MILLILITERS,
        ),
        (500, UnitOfVolume.LITERS, pytest.approx(17.65733), UnitOfVolume.CUBIC_FEET),
        (500, UnitOfVolume.LITERS, 0.5, UnitOfVolume.CUBIC_METERS),
        (500, UnitOfVolume.LITERS, pytest.approx(16907.011), UnitOfVolume.FLUID_OUNCES),
        (500, UnitOfVolume.LITERS, pytest.approx(132.086), UnitOfVolume.GALLONS),
        (500, UnitOfVolume.LITERS, 500000, UnitOfVolume.MILLILITERS),
        (
            500,
            UnitOfVolume.MILLILITERS,
            pytest.approx(0.01765733),
            UnitOfVolume.CUBIC_FEET,
        ),
        (500, UnitOfVolume.MILLILITERS, 0.0005, UnitOfVolume.CUBIC_METERS),
        (
            500,
            UnitOfVolume.MILLILITERS,
            pytest.approx(16.907),
            UnitOfVolume.FLUID_OUNCES,
        ),
        (500, UnitOfVolume.MILLILITERS, pytest.approx(0.132086), UnitOfVolume.GALLONS),
        (500, UnitOfVolume.MILLILITERS, 0.5, UnitOfVolume.LITERS),
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
