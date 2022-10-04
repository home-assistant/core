"""Test Home Assistant eneergy utility functions."""
import pytest

from homeassistant.const import (
    ENERGY_KILO_WATT_HOUR,
    ENERGY_MEGA_WATT_HOUR,
    ENERGY_WATT_HOUR,
    LENGTH_CENTIMETERS,
    LENGTH_FEET,
    LENGTH_INCHES,
    LENGTH_KILOMETERS,
    LENGTH_METERS,
    LENGTH_MILES,
    LENGTH_MILLIMETERS,
    LENGTH_YARD,
    MASS_GRAMS,
    MASS_KILOGRAMS,
    MASS_MICROGRAMS,
    MASS_MILLIGRAMS,
    MASS_OUNCES,
    MASS_POUNDS,
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
    SPEED_FEET_PER_SECOND,
    SPEED_INCHES_PER_DAY,
    SPEED_INCHES_PER_HOUR,
    SPEED_KILOMETERS_PER_HOUR,
    SPEED_KNOTS,
    SPEED_METERS_PER_SECOND,
    SPEED_MILES_PER_HOUR,
    SPEED_MILLIMETERS_PER_DAY,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    TEMP_KELVIN,
    VOLUME_CUBIC_FEET,
    VOLUME_CUBIC_METERS,
    VOLUME_FLUID_OUNCE,
    VOLUME_GALLONS,
    VOLUME_LITERS,
    VOLUME_MILLILITERS,
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
        (DistanceConverter, LENGTH_KILOMETERS),
        (DistanceConverter, LENGTH_METERS),
        (DistanceConverter, LENGTH_CENTIMETERS),
        (DistanceConverter, LENGTH_MILLIMETERS),
        (DistanceConverter, LENGTH_MILES),
        (DistanceConverter, LENGTH_YARD),
        (DistanceConverter, LENGTH_FEET),
        (DistanceConverter, LENGTH_INCHES),
        (EnergyConverter, ENERGY_WATT_HOUR),
        (EnergyConverter, ENERGY_KILO_WATT_HOUR),
        (EnergyConverter, ENERGY_MEGA_WATT_HOUR),
        (MassConverter, MASS_GRAMS),
        (MassConverter, MASS_KILOGRAMS),
        (MassConverter, MASS_MICROGRAMS),
        (MassConverter, MASS_MILLIGRAMS),
        (MassConverter, MASS_OUNCES),
        (MassConverter, MASS_POUNDS),
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
        (SpeedConverter, SPEED_FEET_PER_SECOND),
        (SpeedConverter, SPEED_INCHES_PER_DAY),
        (SpeedConverter, SPEED_INCHES_PER_HOUR),
        (SpeedConverter, SPEED_KILOMETERS_PER_HOUR),
        (SpeedConverter, SPEED_KNOTS),
        (SpeedConverter, SPEED_METERS_PER_SECOND),
        (SpeedConverter, SPEED_MILES_PER_HOUR),
        (SpeedConverter, SPEED_MILLIMETERS_PER_DAY),
        (TemperatureConverter, TEMP_CELSIUS),
        (TemperatureConverter, TEMP_FAHRENHEIT),
        (TemperatureConverter, TEMP_KELVIN),
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
        (DistanceConverter, LENGTH_KILOMETERS),
        (EnergyConverter, ENERGY_KILO_WATT_HOUR),
        (MassConverter, MASS_GRAMS),
        (PowerConverter, POWER_WATT),
        (PressureConverter, PRESSURE_PA),
        (SpeedConverter, SPEED_KILOMETERS_PER_HOUR),
        (TemperatureConverter, TEMP_CELSIUS),
        (TemperatureConverter, TEMP_FAHRENHEIT),
        (TemperatureConverter, TEMP_KELVIN),
        (VolumeConverter, VOLUME_LITERS),
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
        (DistanceConverter, LENGTH_KILOMETERS, LENGTH_METERS),
        (EnergyConverter, ENERGY_WATT_HOUR, ENERGY_KILO_WATT_HOUR),
        (MassConverter, MASS_GRAMS, MASS_KILOGRAMS),
        (PowerConverter, POWER_WATT, POWER_KILO_WATT),
        (PressureConverter, PRESSURE_HPA, PRESSURE_INHG),
        (SpeedConverter, SPEED_KILOMETERS_PER_HOUR, SPEED_MILES_PER_HOUR),
        (TemperatureConverter, TEMP_CELSIUS, TEMP_FAHRENHEIT),
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
    "converter,from_unit,to_unit,expected",
    [
        (DistanceConverter, LENGTH_KILOMETERS, LENGTH_METERS, 1 / 1000),
        (EnergyConverter, ENERGY_WATT_HOUR, ENERGY_KILO_WATT_HOUR, 1000),
        (PowerConverter, POWER_WATT, POWER_KILO_WATT, 1000),
        (PressureConverter, PRESSURE_HPA, PRESSURE_INHG, pytest.approx(33.86389)),
        (
            SpeedConverter,
            SPEED_KILOMETERS_PER_HOUR,
            SPEED_MILES_PER_HOUR,
            pytest.approx(1.609343),
        ),
        (TemperatureConverter, TEMP_CELSIUS, TEMP_FAHRENHEIT, 1 / 1.8),
        (VolumeConverter, VOLUME_GALLONS, VOLUME_LITERS, pytest.approx(0.264172)),
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
        (5, LENGTH_MILES, pytest.approx(8.04672), LENGTH_KILOMETERS),
        (5, LENGTH_MILES, pytest.approx(8046.72), LENGTH_METERS),
        (5, LENGTH_MILES, pytest.approx(804672.0), LENGTH_CENTIMETERS),
        (5, LENGTH_MILES, pytest.approx(8046720.0), LENGTH_MILLIMETERS),
        (5, LENGTH_MILES, pytest.approx(8800.0), LENGTH_YARD),
        (5, LENGTH_MILES, pytest.approx(26400.0008448), LENGTH_FEET),
        (5, LENGTH_MILES, pytest.approx(316800.171072), LENGTH_INCHES),
        (5, LENGTH_YARD, pytest.approx(0.0045720000000000005), LENGTH_KILOMETERS),
        (5, LENGTH_YARD, pytest.approx(4.572), LENGTH_METERS),
        (5, LENGTH_YARD, pytest.approx(457.2), LENGTH_CENTIMETERS),
        (5, LENGTH_YARD, pytest.approx(4572), LENGTH_MILLIMETERS),
        (5, LENGTH_YARD, pytest.approx(0.002840908212), LENGTH_MILES),
        (5, LENGTH_YARD, pytest.approx(15.00000048), LENGTH_FEET),
        (5, LENGTH_YARD, pytest.approx(180.0000972), LENGTH_INCHES),
        (5000, LENGTH_FEET, pytest.approx(1.524), LENGTH_KILOMETERS),
        (5000, LENGTH_FEET, pytest.approx(1524), LENGTH_METERS),
        (5000, LENGTH_FEET, pytest.approx(152400.0), LENGTH_CENTIMETERS),
        (5000, LENGTH_FEET, pytest.approx(1524000.0), LENGTH_MILLIMETERS),
        (5000, LENGTH_FEET, pytest.approx(0.9469694040000001), LENGTH_MILES),
        (5000, LENGTH_FEET, pytest.approx(1666.66667), LENGTH_YARD),
        (5000, LENGTH_FEET, pytest.approx(60000.032400000004), LENGTH_INCHES),
        (5000, LENGTH_INCHES, pytest.approx(0.127), LENGTH_KILOMETERS),
        (5000, LENGTH_INCHES, pytest.approx(127.0), LENGTH_METERS),
        (5000, LENGTH_INCHES, pytest.approx(12700.0), LENGTH_CENTIMETERS),
        (5000, LENGTH_INCHES, pytest.approx(127000.0), LENGTH_MILLIMETERS),
        (5000, LENGTH_INCHES, pytest.approx(0.078914117), LENGTH_MILES),
        (5000, LENGTH_INCHES, pytest.approx(138.88889), LENGTH_YARD),
        (5000, LENGTH_INCHES, pytest.approx(416.66668), LENGTH_FEET),
        (5, LENGTH_KILOMETERS, pytest.approx(5000), LENGTH_METERS),
        (5, LENGTH_KILOMETERS, pytest.approx(500000), LENGTH_CENTIMETERS),
        (5, LENGTH_KILOMETERS, pytest.approx(5000000), LENGTH_MILLIMETERS),
        (5, LENGTH_KILOMETERS, pytest.approx(3.106855), LENGTH_MILES),
        (5, LENGTH_KILOMETERS, pytest.approx(5468.066), LENGTH_YARD),
        (5, LENGTH_KILOMETERS, pytest.approx(16404.2), LENGTH_FEET),
        (5, LENGTH_KILOMETERS, pytest.approx(196850.5), LENGTH_INCHES),
        (5000, LENGTH_METERS, pytest.approx(5), LENGTH_KILOMETERS),
        (5000, LENGTH_METERS, pytest.approx(500000), LENGTH_CENTIMETERS),
        (5000, LENGTH_METERS, pytest.approx(5000000), LENGTH_MILLIMETERS),
        (5000, LENGTH_METERS, pytest.approx(3.106855), LENGTH_MILES),
        (5000, LENGTH_METERS, pytest.approx(5468.066), LENGTH_YARD),
        (5000, LENGTH_METERS, pytest.approx(16404.2), LENGTH_FEET),
        (5000, LENGTH_METERS, pytest.approx(196850.5), LENGTH_INCHES),
        (500000, LENGTH_CENTIMETERS, pytest.approx(5), LENGTH_KILOMETERS),
        (500000, LENGTH_CENTIMETERS, pytest.approx(5000), LENGTH_METERS),
        (500000, LENGTH_CENTIMETERS, pytest.approx(5000000), LENGTH_MILLIMETERS),
        (500000, LENGTH_CENTIMETERS, pytest.approx(3.106855), LENGTH_MILES),
        (500000, LENGTH_CENTIMETERS, pytest.approx(5468.066), LENGTH_YARD),
        (500000, LENGTH_CENTIMETERS, pytest.approx(16404.2), LENGTH_FEET),
        (500000, LENGTH_CENTIMETERS, pytest.approx(196850.5), LENGTH_INCHES),
        (5000000, LENGTH_MILLIMETERS, pytest.approx(5), LENGTH_KILOMETERS),
        (5000000, LENGTH_MILLIMETERS, pytest.approx(5000), LENGTH_METERS),
        (5000000, LENGTH_MILLIMETERS, pytest.approx(500000), LENGTH_CENTIMETERS),
        (5000000, LENGTH_MILLIMETERS, pytest.approx(3.106855), LENGTH_MILES),
        (5000000, LENGTH_MILLIMETERS, pytest.approx(5468.066), LENGTH_YARD),
        (5000000, LENGTH_MILLIMETERS, pytest.approx(16404.2), LENGTH_FEET),
        (5000000, LENGTH_MILLIMETERS, pytest.approx(196850.5), LENGTH_INCHES),
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
        (10, MASS_KILOGRAMS, 10000, MASS_GRAMS),
        (10, MASS_KILOGRAMS, 10000000, MASS_MILLIGRAMS),
        (10, MASS_KILOGRAMS, 10000000000, MASS_MICROGRAMS),
        (10, MASS_KILOGRAMS, pytest.approx(352.73961), MASS_OUNCES),
        (10, MASS_KILOGRAMS, pytest.approx(22.046226), MASS_POUNDS),
        (10, MASS_GRAMS, 0.01, MASS_KILOGRAMS),
        (10, MASS_GRAMS, 10000, MASS_MILLIGRAMS),
        (10, MASS_GRAMS, 10000000, MASS_MICROGRAMS),
        (10, MASS_GRAMS, pytest.approx(0.35273961), MASS_OUNCES),
        (10, MASS_GRAMS, pytest.approx(0.022046226), MASS_POUNDS),
        (10, MASS_MILLIGRAMS, 0.00001, MASS_KILOGRAMS),
        (10, MASS_MILLIGRAMS, 0.01, MASS_GRAMS),
        (10, MASS_MILLIGRAMS, 10000, MASS_MICROGRAMS),
        (10, MASS_MILLIGRAMS, pytest.approx(0.00035273961), MASS_OUNCES),
        (10, MASS_MILLIGRAMS, pytest.approx(0.000022046226), MASS_POUNDS),
        (10000, MASS_MICROGRAMS, 0.00001, MASS_KILOGRAMS),
        (10000, MASS_MICROGRAMS, 0.01, MASS_GRAMS),
        (10000, MASS_MICROGRAMS, 10, MASS_MILLIGRAMS),
        (10000, MASS_MICROGRAMS, pytest.approx(0.00035273961), MASS_OUNCES),
        (10000, MASS_MICROGRAMS, pytest.approx(0.000022046226), MASS_POUNDS),
        (1, MASS_POUNDS, 0.45359237, MASS_KILOGRAMS),
        (1, MASS_POUNDS, 453.59237, MASS_GRAMS),
        (1, MASS_POUNDS, 453592.37, MASS_MILLIGRAMS),
        (1, MASS_POUNDS, 453592370, MASS_MICROGRAMS),
        (1, MASS_POUNDS, 16, MASS_OUNCES),
        (16, MASS_OUNCES, 0.45359237, MASS_KILOGRAMS),
        (16, MASS_OUNCES, 453.59237, MASS_GRAMS),
        (16, MASS_OUNCES, 453592.37, MASS_MILLIGRAMS),
        (16, MASS_OUNCES, 453592370, MASS_MICROGRAMS),
        (16, MASS_OUNCES, 1, MASS_POUNDS),
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
        # 5 km/h / 1.609 km/mi = 3.10686 mi/h
        (5, SPEED_KILOMETERS_PER_HOUR, pytest.approx(3.106856), SPEED_MILES_PER_HOUR),
        # 5 mi/h * 1.609 km/mi = 8.04672 km/h
        (5, SPEED_MILES_PER_HOUR, 8.04672, SPEED_KILOMETERS_PER_HOUR),
        # 5 in/day * 25.4 mm/in = 127 mm/day
        (5, SPEED_INCHES_PER_DAY, 127, SPEED_MILLIMETERS_PER_DAY),
        # 5 mm/day / 25.4 mm/in = 0.19685 in/day
        (5, SPEED_MILLIMETERS_PER_DAY, pytest.approx(0.1968504), SPEED_INCHES_PER_DAY),
        # 5 in/hr * 24 hr/day = 3048 mm/day
        (5, SPEED_INCHES_PER_HOUR, 3048, SPEED_MILLIMETERS_PER_DAY),
        # 5 m/s * 39.3701 in/m * 3600 s/hr = 708661
        (5, SPEED_METERS_PER_SECOND, pytest.approx(708661.42), SPEED_INCHES_PER_HOUR),
        # 5000 in/h / 39.3701 in/m / 3600 s/h = 0.03528 m/s
        (
            5000,
            SPEED_INCHES_PER_HOUR,
            pytest.approx(0.0352778),
            SPEED_METERS_PER_SECOND,
        ),
        # 5 kt * 1852 m/nmi / 3600 s/h = 2.5722 m/s
        (5, SPEED_KNOTS, pytest.approx(2.57222), SPEED_METERS_PER_SECOND),
        # 5 ft/s * 0.3048 m/ft = 1.524 m/s
        (5, SPEED_FEET_PER_SECOND, pytest.approx(1.524), SPEED_METERS_PER_SECOND),
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
        (100, TEMP_CELSIUS, 212, TEMP_FAHRENHEIT),
        (100, TEMP_CELSIUS, 373.15, TEMP_KELVIN),
        (100, TEMP_FAHRENHEIT, pytest.approx(37.77777777777778), TEMP_CELSIUS),
        (100, TEMP_FAHRENHEIT, pytest.approx(310.92777777777775), TEMP_KELVIN),
        (100, TEMP_KELVIN, pytest.approx(-173.15), TEMP_CELSIUS),
        (100, TEMP_KELVIN, pytest.approx(-279.66999999999996), TEMP_FAHRENHEIT),
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
        (100, TEMP_CELSIUS, 180, TEMP_FAHRENHEIT),
        (100, TEMP_CELSIUS, 100, TEMP_KELVIN),
        (100, TEMP_FAHRENHEIT, pytest.approx(55.55555555555556), TEMP_CELSIUS),
        (100, TEMP_FAHRENHEIT, pytest.approx(55.55555555555556), TEMP_KELVIN),
        (100, TEMP_KELVIN, 100, TEMP_CELSIUS),
        (100, TEMP_KELVIN, 180, TEMP_FAHRENHEIT),
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
