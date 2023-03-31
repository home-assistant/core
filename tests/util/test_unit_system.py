"""Test the unit system helper."""
from __future__ import annotations

import pytest

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.sensor.const import DEVICE_CLASS_UNITS
from homeassistant.const import (
    ACCUMULATED_PRECIPITATION,
    LENGTH,
    MASS,
    PRESSURE,
    TEMPERATURE,
    VOLUME,
    WIND_SPEED,
    UnitOfLength,
    UnitOfMass,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfVolume,
    UnitOfVolumetricFlux,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.unit_system import (
    _CONF_UNIT_SYSTEM_IMPERIAL,
    _CONF_UNIT_SYSTEM_METRIC,
    _CONF_UNIT_SYSTEM_US_CUSTOMARY,
    IMPERIAL_SYSTEM,
    METRIC_SYSTEM,
    US_CUSTOMARY_SYSTEM,
    UnitSystem,
    get_unit_system,
)

SYSTEM_NAME = "TEST"
INVALID_UNIT = "INVALID"


def test_invalid_units() -> None:
    """Test errors are raised when invalid units are passed in."""
    with pytest.raises(ValueError):
        UnitSystem(
            SYSTEM_NAME,
            accumulated_precipitation=UnitOfLength.MILLIMETERS,
            conversions={},
            length=UnitOfLength.METERS,
            mass=UnitOfMass.GRAMS,
            pressure=UnitOfPressure.PA,
            temperature=INVALID_UNIT,
            volume=UnitOfVolume.LITERS,
            wind_speed=UnitOfSpeed.METERS_PER_SECOND,
        )

    with pytest.raises(ValueError):
        UnitSystem(
            SYSTEM_NAME,
            accumulated_precipitation=UnitOfLength.MILLIMETERS,
            conversions={},
            length=INVALID_UNIT,
            mass=UnitOfMass.GRAMS,
            pressure=UnitOfPressure.PA,
            temperature=UnitOfTemperature.CELSIUS,
            volume=UnitOfVolume.LITERS,
            wind_speed=UnitOfSpeed.METERS_PER_SECOND,
        )

    with pytest.raises(ValueError):
        UnitSystem(
            SYSTEM_NAME,
            accumulated_precipitation=UnitOfLength.MILLIMETERS,
            conversions={},
            length=UnitOfLength.METERS,
            mass=UnitOfMass.GRAMS,
            pressure=UnitOfPressure.PA,
            temperature=UnitOfTemperature.CELSIUS,
            volume=UnitOfVolume.LITERS,
            wind_speed=INVALID_UNIT,
        )

    with pytest.raises(ValueError):
        UnitSystem(
            SYSTEM_NAME,
            accumulated_precipitation=UnitOfLength.MILLIMETERS,
            conversions={},
            length=UnitOfLength.METERS,
            mass=UnitOfMass.GRAMS,
            pressure=UnitOfPressure.PA,
            temperature=UnitOfTemperature.CELSIUS,
            volume=INVALID_UNIT,
            wind_speed=UnitOfSpeed.METERS_PER_SECOND,
        )

    with pytest.raises(ValueError):
        UnitSystem(
            SYSTEM_NAME,
            accumulated_precipitation=UnitOfLength.MILLIMETERS,
            conversions={},
            length=UnitOfLength.METERS,
            mass=INVALID_UNIT,
            pressure=UnitOfPressure.PA,
            temperature=UnitOfTemperature.CELSIUS,
            volume=UnitOfVolume.LITERS,
            wind_speed=UnitOfSpeed.METERS_PER_SECOND,
        )

    with pytest.raises(ValueError):
        UnitSystem(
            SYSTEM_NAME,
            accumulated_precipitation=UnitOfLength.MILLIMETERS,
            conversions={},
            length=UnitOfLength.METERS,
            mass=UnitOfMass.GRAMS,
            pressure=INVALID_UNIT,
            temperature=UnitOfTemperature.CELSIUS,
            volume=UnitOfVolume.LITERS,
            wind_speed=UnitOfSpeed.METERS_PER_SECOND,
        )

    with pytest.raises(ValueError):
        UnitSystem(
            SYSTEM_NAME,
            accumulated_precipitation=INVALID_UNIT,
            conversions={},
            length=UnitOfLength.METERS,
            mass=UnitOfMass.GRAMS,
            pressure=UnitOfPressure.PA,
            temperature=UnitOfTemperature.CELSIUS,
            volume=UnitOfVolume.LITERS,
            wind_speed=UnitOfSpeed.METERS_PER_SECOND,
        )


def test_invalid_value() -> None:
    """Test no conversion happens if value is non-numeric."""
    with pytest.raises(TypeError):
        METRIC_SYSTEM.length("25a", UnitOfLength.KILOMETERS)
    with pytest.raises(TypeError):
        METRIC_SYSTEM.temperature("50K", UnitOfTemperature.CELSIUS)
    with pytest.raises(TypeError):
        METRIC_SYSTEM.wind_speed("50km/h", UnitOfSpeed.METERS_PER_SECOND)
    with pytest.raises(TypeError):
        METRIC_SYSTEM.volume("50L", UnitOfVolume.LITERS)
    with pytest.raises(TypeError):
        METRIC_SYSTEM.pressure("50Pa", UnitOfPressure.PA)
    with pytest.raises(TypeError):
        METRIC_SYSTEM.accumulated_precipitation("50mm", UnitOfLength.MILLIMETERS)


def test_as_dict() -> None:
    """Test that the as_dict() method returns the expected dictionary."""
    expected = {
        LENGTH: UnitOfLength.KILOMETERS,
        WIND_SPEED: UnitOfSpeed.METERS_PER_SECOND,
        TEMPERATURE: UnitOfTemperature.CELSIUS,
        VOLUME: UnitOfVolume.LITERS,
        MASS: UnitOfMass.GRAMS,
        PRESSURE: UnitOfPressure.PA,
        ACCUMULATED_PRECIPITATION: UnitOfLength.MILLIMETERS,
    }

    assert expected == METRIC_SYSTEM.as_dict()


def test_temperature_same_unit() -> None:
    """Test no conversion happens if to unit is same as from unit."""
    assert METRIC_SYSTEM.temperature(5, METRIC_SYSTEM.temperature_unit) == 5


def test_temperature_unknown_unit() -> None:
    """Test no conversion happens if unknown unit."""
    with pytest.raises(HomeAssistantError, match="is not a recognized .* unit"):
        METRIC_SYSTEM.temperature(5, "abc")


def test_temperature_to_metric() -> None:
    """Test temperature conversion to metric system."""
    assert METRIC_SYSTEM.temperature(25, METRIC_SYSTEM.temperature_unit) == 25
    assert (
        round(METRIC_SYSTEM.temperature(80, IMPERIAL_SYSTEM.temperature_unit), 1)
        == 26.7
    )


def test_temperature_to_imperial() -> None:
    """Test temperature conversion to imperial system."""
    assert IMPERIAL_SYSTEM.temperature(77, IMPERIAL_SYSTEM.temperature_unit) == 77
    assert IMPERIAL_SYSTEM.temperature(25, METRIC_SYSTEM.temperature_unit) == 77


def test_length_unknown_unit() -> None:
    """Test length conversion with unknown from unit."""
    with pytest.raises(HomeAssistantError, match="is not a recognized .* unit"):
        METRIC_SYSTEM.length(5, "fr")


def test_length_to_metric() -> None:
    """Test length conversion to metric system."""
    assert METRIC_SYSTEM.length(100, METRIC_SYSTEM.length_unit) == 100
    assert METRIC_SYSTEM.length(5, IMPERIAL_SYSTEM.length_unit) == pytest.approx(
        8.04672
    )


def test_length_to_imperial() -> None:
    """Test length conversion to imperial system."""
    assert IMPERIAL_SYSTEM.length(100, IMPERIAL_SYSTEM.length_unit) == 100
    assert IMPERIAL_SYSTEM.length(5, METRIC_SYSTEM.length_unit) == pytest.approx(
        3.106855
    )


def test_wind_speed_unknown_unit() -> None:
    """Test wind_speed conversion with unknown from unit."""
    with pytest.raises(HomeAssistantError, match="is not a recognized .* unit"):
        METRIC_SYSTEM.length(5, "turtles")


def test_wind_speed_to_metric() -> None:
    """Test length conversion to metric system."""
    assert METRIC_SYSTEM.wind_speed(100, METRIC_SYSTEM.wind_speed_unit) == 100
    # 1 m/s is about 2.237 mph
    assert METRIC_SYSTEM.wind_speed(
        2237, IMPERIAL_SYSTEM.wind_speed_unit
    ) == pytest.approx(1000, abs=0.1)


def test_wind_speed_to_imperial() -> None:
    """Test wind_speed conversion to imperial system."""
    assert IMPERIAL_SYSTEM.wind_speed(100, IMPERIAL_SYSTEM.wind_speed_unit) == 100
    assert IMPERIAL_SYSTEM.wind_speed(
        1000, METRIC_SYSTEM.wind_speed_unit
    ) == pytest.approx(2237, abs=0.1)


def test_pressure_same_unit() -> None:
    """Test no conversion happens if to unit is same as from unit."""
    assert METRIC_SYSTEM.pressure(5, METRIC_SYSTEM.pressure_unit) == 5


def test_pressure_unknown_unit() -> None:
    """Test no conversion happens if unknown unit."""
    with pytest.raises(HomeAssistantError, match="is not a recognized .* unit"):
        METRIC_SYSTEM.pressure(5, "K")


def test_pressure_to_metric() -> None:
    """Test pressure conversion to metric system."""
    assert METRIC_SYSTEM.pressure(25, METRIC_SYSTEM.pressure_unit) == 25
    assert METRIC_SYSTEM.pressure(14.7, IMPERIAL_SYSTEM.pressure_unit) == pytest.approx(
        101352.932, abs=1e-1
    )


def test_pressure_to_imperial() -> None:
    """Test pressure conversion to imperial system."""
    assert IMPERIAL_SYSTEM.pressure(77, IMPERIAL_SYSTEM.pressure_unit) == 77
    assert IMPERIAL_SYSTEM.pressure(
        101352.932, METRIC_SYSTEM.pressure_unit
    ) == pytest.approx(14.7, abs=1e-4)


def test_accumulated_precipitation_same_unit() -> None:
    """Test no conversion happens if to unit is same as from unit."""
    assert (
        METRIC_SYSTEM.accumulated_precipitation(
            5, METRIC_SYSTEM.accumulated_precipitation_unit
        )
        == 5
    )


def test_accumulated_precipitation_unknown_unit() -> None:
    """Test no conversion happens if unknown unit."""
    with pytest.raises(HomeAssistantError, match="is not a recognized .* unit"):
        METRIC_SYSTEM.accumulated_precipitation(5, "K")


def test_accumulated_precipitation_to_metric() -> None:
    """Test accumulated_precipitation conversion to metric system."""
    assert (
        METRIC_SYSTEM.accumulated_precipitation(
            25, METRIC_SYSTEM.accumulated_precipitation_unit
        )
        == 25
    )
    assert METRIC_SYSTEM.accumulated_precipitation(
        10, IMPERIAL_SYSTEM.accumulated_precipitation_unit
    ) == pytest.approx(254, abs=1e-4)


def test_accumulated_precipitation_to_imperial() -> None:
    """Test accumulated_precipitation conversion to imperial system."""
    assert (
        IMPERIAL_SYSTEM.accumulated_precipitation(
            10, IMPERIAL_SYSTEM.accumulated_precipitation_unit
        )
        == 10
    )
    assert IMPERIAL_SYSTEM.accumulated_precipitation(
        254, METRIC_SYSTEM.accumulated_precipitation_unit
    ) == pytest.approx(10, abs=1e-4)


def test_properties() -> None:
    """Test the unit properties are returned as expected."""
    assert METRIC_SYSTEM.length_unit == UnitOfLength.KILOMETERS
    assert METRIC_SYSTEM.wind_speed_unit == UnitOfSpeed.METERS_PER_SECOND
    assert METRIC_SYSTEM.temperature_unit == UnitOfTemperature.CELSIUS
    assert METRIC_SYSTEM.mass_unit == UnitOfMass.GRAMS
    assert METRIC_SYSTEM.volume_unit == UnitOfVolume.LITERS
    assert METRIC_SYSTEM.pressure_unit == UnitOfPressure.PA
    assert METRIC_SYSTEM.accumulated_precipitation_unit == UnitOfLength.MILLIMETERS


@pytest.mark.parametrize(
    ("key", "expected_system"),
    [
        (_CONF_UNIT_SYSTEM_METRIC, METRIC_SYSTEM),
        (_CONF_UNIT_SYSTEM_US_CUSTOMARY, US_CUSTOMARY_SYSTEM),
    ],
)
def test_get_unit_system(key: str, expected_system: UnitSystem) -> None:
    """Test get_unit_system."""
    assert get_unit_system(key) is expected_system


@pytest.mark.parametrize(
    "key", [None, "", "invalid_custom", _CONF_UNIT_SYSTEM_IMPERIAL]
)
def test_get_unit_system_invalid(key: str) -> None:
    """Test get_unit_system with an invalid key."""
    with pytest.raises(ValueError, match=f"`{key}` is not a valid unit system key"):
        _ = get_unit_system(key)


@pytest.mark.parametrize(
    ("device_class", "original_unit", "state_unit"),
    (
        # Test atmospheric pressure
        (
            SensorDeviceClass.ATMOSPHERIC_PRESSURE,
            UnitOfPressure.PSI,
            UnitOfPressure.HPA,
        ),
        (
            SensorDeviceClass.ATMOSPHERIC_PRESSURE,
            UnitOfPressure.BAR,
            UnitOfPressure.HPA,
        ),
        (
            SensorDeviceClass.ATMOSPHERIC_PRESSURE,
            UnitOfPressure.INHG,
            UnitOfPressure.HPA,
        ),
        (SensorDeviceClass.ATMOSPHERIC_PRESSURE, UnitOfPressure.HPA, None),
        (SensorDeviceClass.ATMOSPHERIC_PRESSURE, "very_much", None),
        # Test distance conversion
        (SensorDeviceClass.DISTANCE, UnitOfLength.FEET, UnitOfLength.METERS),
        (SensorDeviceClass.DISTANCE, UnitOfLength.INCHES, UnitOfLength.MILLIMETERS),
        (SensorDeviceClass.DISTANCE, UnitOfLength.MILES, UnitOfLength.KILOMETERS),
        (SensorDeviceClass.DISTANCE, UnitOfLength.YARDS, UnitOfLength.METERS),
        (SensorDeviceClass.DISTANCE, UnitOfLength.KILOMETERS, None),
        (SensorDeviceClass.DISTANCE, "very_long", None),
        # Test gas meter conversion
        (
            SensorDeviceClass.GAS,
            UnitOfVolume.CENTUM_CUBIC_FEET,
            UnitOfVolume.CUBIC_METERS,
        ),
        (SensorDeviceClass.GAS, UnitOfVolume.CUBIC_FEET, UnitOfVolume.CUBIC_METERS),
        (SensorDeviceClass.GAS, UnitOfVolume.CUBIC_METERS, None),
        (SensorDeviceClass.GAS, "very_much", None),
        # Test precipitation conversion
        (
            SensorDeviceClass.PRECIPITATION,
            UnitOfLength.INCHES,
            UnitOfLength.MILLIMETERS,
        ),
        (SensorDeviceClass.PRECIPITATION, UnitOfLength.CENTIMETERS, None),
        (SensorDeviceClass.PRECIPITATION, UnitOfLength.MILLIMETERS, None),
        (SensorDeviceClass.PRECIPITATION, "very_much", None),
        # Test precipitation intensity conversion
        (
            SensorDeviceClass.PRECIPITATION_INTENSITY,
            UnitOfVolumetricFlux.INCHES_PER_DAY,
            UnitOfVolumetricFlux.MILLIMETERS_PER_DAY,
        ),
        (
            SensorDeviceClass.PRECIPITATION_INTENSITY,
            UnitOfVolumetricFlux.INCHES_PER_HOUR,
            UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        ),
        (
            SensorDeviceClass.PRECIPITATION_INTENSITY,
            UnitOfVolumetricFlux.MILLIMETERS_PER_DAY,
            None,
        ),
        (
            SensorDeviceClass.PRECIPITATION_INTENSITY,
            UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
            None,
        ),
        (SensorDeviceClass.PRECIPITATION_INTENSITY, "very_heavy", None),
        # Test pressure conversion
        (SensorDeviceClass.PRESSURE, UnitOfPressure.PSI, UnitOfPressure.KPA),
        (SensorDeviceClass.PRESSURE, UnitOfPressure.BAR, None),
        (SensorDeviceClass.PRESSURE, "very_much", None),
        # Test speed conversion
        (
            SensorDeviceClass.SPEED,
            UnitOfSpeed.FEET_PER_SECOND,
            UnitOfSpeed.KILOMETERS_PER_HOUR,
        ),
        (
            SensorDeviceClass.SPEED,
            UnitOfSpeed.MILES_PER_HOUR,
            UnitOfSpeed.KILOMETERS_PER_HOUR,
        ),
        (SensorDeviceClass.SPEED, UnitOfSpeed.KILOMETERS_PER_HOUR, None),
        (SensorDeviceClass.SPEED, UnitOfSpeed.KNOTS, None),
        (SensorDeviceClass.SPEED, UnitOfSpeed.METERS_PER_SECOND, None),
        (
            SensorDeviceClass.SPEED,
            UnitOfVolumetricFlux.INCHES_PER_DAY,
            UnitOfVolumetricFlux.MILLIMETERS_PER_DAY,
        ),
        (
            SensorDeviceClass.SPEED,
            UnitOfVolumetricFlux.INCHES_PER_HOUR,
            UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        ),
        (SensorDeviceClass.SPEED, UnitOfVolumetricFlux.MILLIMETERS_PER_DAY, None),
        (SensorDeviceClass.SPEED, UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR, None),
        (SensorDeviceClass.SPEED, "very_fast", None),
        # Test volume conversion
        (
            SensorDeviceClass.VOLUME,
            UnitOfVolume.CENTUM_CUBIC_FEET,
            UnitOfVolume.CUBIC_METERS,
        ),
        (SensorDeviceClass.VOLUME, UnitOfVolume.CUBIC_FEET, UnitOfVolume.CUBIC_METERS),
        (SensorDeviceClass.VOLUME, UnitOfVolume.FLUID_OUNCES, UnitOfVolume.MILLILITERS),
        (SensorDeviceClass.VOLUME, UnitOfVolume.GALLONS, UnitOfVolume.LITERS),
        (SensorDeviceClass.VOLUME, UnitOfVolume.CUBIC_METERS, None),
        (SensorDeviceClass.VOLUME, UnitOfVolume.LITERS, None),
        (SensorDeviceClass.VOLUME, UnitOfVolume.MILLILITERS, None),
        (SensorDeviceClass.VOLUME, "very_much", None),
        # Test water meter conversion
        (
            SensorDeviceClass.WATER,
            UnitOfVolume.CENTUM_CUBIC_FEET,
            UnitOfVolume.CUBIC_METERS,
        ),
        (SensorDeviceClass.WATER, UnitOfVolume.CUBIC_FEET, UnitOfVolume.CUBIC_METERS),
        (SensorDeviceClass.WATER, UnitOfVolume.GALLONS, UnitOfVolume.LITERS),
        (SensorDeviceClass.WATER, UnitOfVolume.CUBIC_METERS, None),
        (SensorDeviceClass.WATER, UnitOfVolume.LITERS, None),
        (SensorDeviceClass.WATER, "very_much", None),
        # Test wind speed conversion
        (
            SensorDeviceClass.WIND_SPEED,
            UnitOfSpeed.FEET_PER_SECOND,
            UnitOfSpeed.KILOMETERS_PER_HOUR,
        ),
        (
            SensorDeviceClass.WIND_SPEED,
            UnitOfSpeed.MILES_PER_HOUR,
            UnitOfSpeed.KILOMETERS_PER_HOUR,
        ),
        (SensorDeviceClass.WIND_SPEED, UnitOfSpeed.KILOMETERS_PER_HOUR, None),
        (SensorDeviceClass.WIND_SPEED, UnitOfSpeed.KNOTS, None),
        (
            SensorDeviceClass.WIND_SPEED,
            UnitOfSpeed.METERS_PER_SECOND,
            UnitOfSpeed.KILOMETERS_PER_HOUR,
        ),
        (SensorDeviceClass.WIND_SPEED, "very_fast", None),
    ),
)
def test_get_metric_converted_unit_(
    device_class: SensorDeviceClass,
    original_unit: str,
    state_unit: str | None,
) -> None:
    """Test unit conversion rules."""
    unit_system = METRIC_SYSTEM
    assert unit_system.get_converted_unit(device_class, original_unit) == state_unit


UNCONVERTED_UNITS_METRIC_SYSTEM = {
    SensorDeviceClass.ATMOSPHERIC_PRESSURE: (UnitOfPressure.HPA,),
    SensorDeviceClass.DISTANCE: (
        UnitOfLength.CENTIMETERS,
        UnitOfLength.KILOMETERS,
        UnitOfLength.METERS,
        UnitOfLength.MILLIMETERS,
    ),
    SensorDeviceClass.GAS: (UnitOfVolume.CUBIC_METERS,),
    SensorDeviceClass.PRECIPITATION: (
        UnitOfLength.CENTIMETERS,
        UnitOfLength.MILLIMETERS,
    ),
    SensorDeviceClass.PRECIPITATION_INTENSITY: (
        UnitOfVolumetricFlux.MILLIMETERS_PER_DAY,
        UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
    ),
    SensorDeviceClass.PRESSURE: (
        UnitOfPressure.BAR,
        UnitOfPressure.CBAR,
        UnitOfPressure.HPA,
        UnitOfPressure.KPA,
        UnitOfPressure.MBAR,
        UnitOfPressure.MMHG,
        UnitOfPressure.PA,
    ),
    SensorDeviceClass.SPEED: (
        UnitOfSpeed.KILOMETERS_PER_HOUR,
        UnitOfSpeed.KNOTS,
        UnitOfSpeed.METERS_PER_SECOND,
        UnitOfVolumetricFlux.MILLIMETERS_PER_DAY,
        UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
    ),
    SensorDeviceClass.VOLUME: (
        UnitOfVolume.CUBIC_METERS,
        UnitOfVolume.LITERS,
        UnitOfVolume.MILLILITERS,
    ),
    SensorDeviceClass.WATER: (
        UnitOfVolume.CUBIC_METERS,
        UnitOfVolume.LITERS,
    ),
}


@pytest.mark.parametrize(
    "device_class",
    (
        SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        SensorDeviceClass.DISTANCE,
        SensorDeviceClass.GAS,
        SensorDeviceClass.PRECIPITATION,
        SensorDeviceClass.PRECIPITATION_INTENSITY,
        SensorDeviceClass.PRESSURE,
        SensorDeviceClass.SPEED,
        SensorDeviceClass.VOLUME,
        SensorDeviceClass.WATER,
    ),
)
def test_metric_converted_units(device_class: SensorDeviceClass) -> None:
    """Test unit conversion rules are in place for all units."""
    unit_system = METRIC_SYSTEM
    # Make sure excluded_units is not stale
    for unit in UNCONVERTED_UNITS_METRIC_SYSTEM[device_class]:
        assert unit in DEVICE_CLASS_UNITS[device_class]

    for unit in DEVICE_CLASS_UNITS[device_class]:
        if unit in UNCONVERTED_UNITS_METRIC_SYSTEM[device_class]:
            assert (device_class, unit) not in unit_system._conversions
            continue
        assert (device_class, unit) in unit_system._conversions


@pytest.mark.parametrize(
    ("device_class", "original_unit", "state_unit"),
    (
        # Test atmospheric pressure
        (
            SensorDeviceClass.ATMOSPHERIC_PRESSURE,
            UnitOfPressure.PSI,
            UnitOfPressure.INHG,
        ),
        (
            SensorDeviceClass.ATMOSPHERIC_PRESSURE,
            UnitOfPressure.BAR,
            UnitOfPressure.INHG,
        ),
        (
            SensorDeviceClass.ATMOSPHERIC_PRESSURE,
            UnitOfPressure.HPA,
            UnitOfPressure.INHG,
        ),
        (SensorDeviceClass.ATMOSPHERIC_PRESSURE, UnitOfPressure.INHG, None),
        (SensorDeviceClass.ATMOSPHERIC_PRESSURE, "very_much", None),
        # Test distance conversion
        (SensorDeviceClass.DISTANCE, UnitOfLength.CENTIMETERS, UnitOfLength.INCHES),
        (SensorDeviceClass.DISTANCE, UnitOfLength.KILOMETERS, UnitOfLength.MILES),
        (SensorDeviceClass.DISTANCE, UnitOfLength.METERS, UnitOfLength.FEET),
        (SensorDeviceClass.DISTANCE, UnitOfLength.MILLIMETERS, UnitOfLength.INCHES),
        (SensorDeviceClass.DISTANCE, UnitOfLength.MILES, None),
        (SensorDeviceClass.DISTANCE, "very_long", None),
        # Test gas meter conversion
        (SensorDeviceClass.GAS, UnitOfVolume.CENTUM_CUBIC_FEET, None),
        (SensorDeviceClass.GAS, UnitOfVolume.CUBIC_METERS, UnitOfVolume.CUBIC_FEET),
        (SensorDeviceClass.GAS, UnitOfVolume.CUBIC_FEET, None),
        (SensorDeviceClass.GAS, "very_much", None),
        # Test precipitation conversion
        (
            SensorDeviceClass.PRECIPITATION,
            UnitOfLength.CENTIMETERS,
            UnitOfLength.INCHES,
        ),
        (
            SensorDeviceClass.PRECIPITATION,
            UnitOfLength.MILLIMETERS,
            UnitOfLength.INCHES,
        ),
        (SensorDeviceClass.PRECIPITATION, UnitOfLength.INCHES, None),
        (SensorDeviceClass.PRECIPITATION, "very_much", None),
        # Test precipitation intensity conversion
        (
            SensorDeviceClass.PRECIPITATION_INTENSITY,
            UnitOfVolumetricFlux.MILLIMETERS_PER_DAY,
            UnitOfVolumetricFlux.INCHES_PER_DAY,
        ),
        (
            SensorDeviceClass.PRECIPITATION_INTENSITY,
            UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
            UnitOfVolumetricFlux.INCHES_PER_HOUR,
        ),
        (
            SensorDeviceClass.PRECIPITATION_INTENSITY,
            UnitOfVolumetricFlux.INCHES_PER_DAY,
            None,
        ),
        (
            SensorDeviceClass.PRECIPITATION_INTENSITY,
            UnitOfVolumetricFlux.INCHES_PER_HOUR,
            None,
        ),
        (SensorDeviceClass.PRECIPITATION_INTENSITY, "very_heavy", None),
        # Test pressure conversion
        (SensorDeviceClass.PRESSURE, UnitOfPressure.BAR, UnitOfPressure.PSI),
        (SensorDeviceClass.PRESSURE, UnitOfPressure.PSI, None),
        (SensorDeviceClass.PRESSURE, "very_much", None),
        # Test speed conversion
        (
            SensorDeviceClass.SPEED,
            UnitOfSpeed.METERS_PER_SECOND,
            UnitOfSpeed.MILES_PER_HOUR,
        ),
        (
            SensorDeviceClass.SPEED,
            UnitOfSpeed.KILOMETERS_PER_HOUR,
            UnitOfSpeed.MILES_PER_HOUR,
        ),
        (SensorDeviceClass.SPEED, UnitOfSpeed.FEET_PER_SECOND, None),
        (SensorDeviceClass.SPEED, UnitOfSpeed.KNOTS, None),
        (SensorDeviceClass.SPEED, UnitOfSpeed.MILES_PER_HOUR, None),
        (
            SensorDeviceClass.SPEED,
            UnitOfVolumetricFlux.MILLIMETERS_PER_DAY,
            UnitOfVolumetricFlux.INCHES_PER_DAY,
        ),
        (
            SensorDeviceClass.SPEED,
            UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
            UnitOfVolumetricFlux.INCHES_PER_HOUR,
        ),
        (SensorDeviceClass.SPEED, UnitOfVolumetricFlux.INCHES_PER_DAY, None),
        (SensorDeviceClass.SPEED, UnitOfVolumetricFlux.INCHES_PER_HOUR, None),
        (SensorDeviceClass.SPEED, "very_fast", None),
        # Test volume conversion
        (SensorDeviceClass.VOLUME, UnitOfVolume.CUBIC_METERS, UnitOfVolume.CUBIC_FEET),
        (SensorDeviceClass.VOLUME, UnitOfVolume.LITERS, UnitOfVolume.GALLONS),
        (SensorDeviceClass.VOLUME, UnitOfVolume.MILLILITERS, UnitOfVolume.FLUID_OUNCES),
        (SensorDeviceClass.VOLUME, UnitOfVolume.CENTUM_CUBIC_FEET, None),
        (SensorDeviceClass.VOLUME, UnitOfVolume.CUBIC_FEET, None),
        (SensorDeviceClass.VOLUME, UnitOfVolume.FLUID_OUNCES, None),
        (SensorDeviceClass.VOLUME, UnitOfVolume.GALLONS, None),
        (SensorDeviceClass.VOLUME, "very_much", None),
        # Test water meter conversion
        (SensorDeviceClass.WATER, UnitOfVolume.CUBIC_METERS, UnitOfVolume.CUBIC_FEET),
        (SensorDeviceClass.WATER, UnitOfVolume.LITERS, UnitOfVolume.GALLONS),
        (SensorDeviceClass.WATER, UnitOfVolume.CENTUM_CUBIC_FEET, None),
        (SensorDeviceClass.WATER, UnitOfVolume.CUBIC_FEET, None),
        (SensorDeviceClass.WATER, UnitOfVolume.GALLONS, None),
        (SensorDeviceClass.WATER, "very_much", None),
        # Test wind speed conversion
        (
            SensorDeviceClass.WIND_SPEED,
            UnitOfSpeed.METERS_PER_SECOND,
            UnitOfSpeed.MILES_PER_HOUR,
        ),
        (
            SensorDeviceClass.WIND_SPEED,
            UnitOfSpeed.KILOMETERS_PER_HOUR,
            UnitOfSpeed.MILES_PER_HOUR,
        ),
        (
            SensorDeviceClass.WIND_SPEED,
            UnitOfSpeed.FEET_PER_SECOND,
            UnitOfSpeed.MILES_PER_HOUR,
        ),
        (SensorDeviceClass.WIND_SPEED, UnitOfSpeed.KNOTS, None),
        (SensorDeviceClass.WIND_SPEED, UnitOfSpeed.MILES_PER_HOUR, None),
        (SensorDeviceClass.WIND_SPEED, "very_fast", None),
    ),
)
def test_get_us_converted_unit(
    device_class: SensorDeviceClass,
    original_unit: str,
    state_unit: str | None,
) -> None:
    """Test unit conversion rules."""
    unit_system = US_CUSTOMARY_SYSTEM
    assert unit_system.get_converted_unit(device_class, original_unit) == state_unit


UNCONVERTED_UNITS_US_SYSTEM = {
    SensorDeviceClass.ATMOSPHERIC_PRESSURE: (UnitOfPressure.INHG,),
    SensorDeviceClass.DISTANCE: (
        UnitOfLength.FEET,
        UnitOfLength.INCHES,
        UnitOfLength.MILES,
        UnitOfLength.YARDS,
    ),
    SensorDeviceClass.GAS: (UnitOfVolume.CENTUM_CUBIC_FEET, UnitOfVolume.CUBIC_FEET),
    SensorDeviceClass.PRECIPITATION: (UnitOfLength.INCHES,),
    SensorDeviceClass.PRECIPITATION_INTENSITY: (
        UnitOfVolumetricFlux.INCHES_PER_DAY,
        UnitOfVolumetricFlux.INCHES_PER_HOUR,
    ),
    SensorDeviceClass.PRESSURE: (UnitOfPressure.INHG, UnitOfPressure.PSI),
    SensorDeviceClass.SPEED: (
        UnitOfSpeed.FEET_PER_SECOND,
        UnitOfSpeed.KNOTS,
        UnitOfSpeed.MILES_PER_HOUR,
        UnitOfVolumetricFlux.INCHES_PER_DAY,
        UnitOfVolumetricFlux.INCHES_PER_HOUR,
    ),
    SensorDeviceClass.VOLUME: (
        UnitOfVolume.CENTUM_CUBIC_FEET,
        UnitOfVolume.CUBIC_FEET,
        UnitOfVolume.FLUID_OUNCES,
        UnitOfVolume.GALLONS,
    ),
    SensorDeviceClass.WATER: (
        UnitOfVolume.CENTUM_CUBIC_FEET,
        UnitOfVolume.CUBIC_FEET,
        UnitOfVolume.GALLONS,
    ),
}


@pytest.mark.parametrize(
    "device_class",
    (
        SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        SensorDeviceClass.DISTANCE,
        SensorDeviceClass.GAS,
        SensorDeviceClass.PRECIPITATION,
        SensorDeviceClass.PRECIPITATION_INTENSITY,
        SensorDeviceClass.PRESSURE,
        SensorDeviceClass.SPEED,
        SensorDeviceClass.VOLUME,
        SensorDeviceClass.WATER,
    ),
)
def test_imperial_converted_units(device_class: SensorDeviceClass) -> None:
    """Test unit conversion rules are in place for all units."""
    unit_system = US_CUSTOMARY_SYSTEM
    # Make sure excluded_units is not stale
    for unit in UNCONVERTED_UNITS_US_SYSTEM[device_class]:
        assert unit in DEVICE_CLASS_UNITS[device_class]

    for unit in DEVICE_CLASS_UNITS[device_class]:
        if unit in UNCONVERTED_UNITS_US_SYSTEM[device_class]:
            assert (device_class, unit) not in unit_system._conversions
            continue
        assert (device_class, unit) in unit_system._conversions
