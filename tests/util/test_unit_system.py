"""Test the unit system helper."""
from __future__ import annotations

import pytest

from homeassistant.components.sensor import SensorDeviceClass
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


def test_invalid_units():
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


def test_invalid_value():
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


def test_as_dict():
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


def test_temperature_same_unit():
    """Test no conversion happens if to unit is same as from unit."""
    assert METRIC_SYSTEM.temperature(5, METRIC_SYSTEM.temperature_unit) == 5


def test_temperature_unknown_unit():
    """Test no conversion happens if unknown unit."""
    with pytest.raises(HomeAssistantError, match="is not a recognized .* unit"):
        METRIC_SYSTEM.temperature(5, "abc")


def test_temperature_to_metric():
    """Test temperature conversion to metric system."""
    assert METRIC_SYSTEM.temperature(25, METRIC_SYSTEM.temperature_unit) == 25
    assert (
        round(METRIC_SYSTEM.temperature(80, IMPERIAL_SYSTEM.temperature_unit), 1)
        == 26.7
    )


def test_temperature_to_imperial():
    """Test temperature conversion to imperial system."""
    assert IMPERIAL_SYSTEM.temperature(77, IMPERIAL_SYSTEM.temperature_unit) == 77
    assert IMPERIAL_SYSTEM.temperature(25, METRIC_SYSTEM.temperature_unit) == 77


def test_length_unknown_unit():
    """Test length conversion with unknown from unit."""
    with pytest.raises(HomeAssistantError, match="is not a recognized .* unit"):
        METRIC_SYSTEM.length(5, "fr")


def test_length_to_metric():
    """Test length conversion to metric system."""
    assert METRIC_SYSTEM.length(100, METRIC_SYSTEM.length_unit) == 100
    assert METRIC_SYSTEM.length(5, IMPERIAL_SYSTEM.length_unit) == pytest.approx(
        8.04672
    )


def test_length_to_imperial():
    """Test length conversion to imperial system."""
    assert IMPERIAL_SYSTEM.length(100, IMPERIAL_SYSTEM.length_unit) == 100
    assert IMPERIAL_SYSTEM.length(5, METRIC_SYSTEM.length_unit) == pytest.approx(
        3.106855
    )


def test_wind_speed_unknown_unit():
    """Test wind_speed conversion with unknown from unit."""
    with pytest.raises(HomeAssistantError, match="is not a recognized .* unit"):
        METRIC_SYSTEM.length(5, "turtles")


def test_wind_speed_to_metric():
    """Test length conversion to metric system."""
    assert METRIC_SYSTEM.wind_speed(100, METRIC_SYSTEM.wind_speed_unit) == 100
    # 1 m/s is about 2.237 mph
    assert METRIC_SYSTEM.wind_speed(
        2237, IMPERIAL_SYSTEM.wind_speed_unit
    ) == pytest.approx(1000, abs=0.1)


def test_wind_speed_to_imperial():
    """Test wind_speed conversion to imperial system."""
    assert IMPERIAL_SYSTEM.wind_speed(100, IMPERIAL_SYSTEM.wind_speed_unit) == 100
    assert IMPERIAL_SYSTEM.wind_speed(
        1000, METRIC_SYSTEM.wind_speed_unit
    ) == pytest.approx(2237, abs=0.1)


def test_pressure_same_unit():
    """Test no conversion happens if to unit is same as from unit."""
    assert METRIC_SYSTEM.pressure(5, METRIC_SYSTEM.pressure_unit) == 5


def test_pressure_unknown_unit():
    """Test no conversion happens if unknown unit."""
    with pytest.raises(HomeAssistantError, match="is not a recognized .* unit"):
        METRIC_SYSTEM.pressure(5, "K")


def test_pressure_to_metric():
    """Test pressure conversion to metric system."""
    assert METRIC_SYSTEM.pressure(25, METRIC_SYSTEM.pressure_unit) == 25
    assert METRIC_SYSTEM.pressure(14.7, IMPERIAL_SYSTEM.pressure_unit) == pytest.approx(
        101352.932, abs=1e-1
    )


def test_pressure_to_imperial():
    """Test pressure conversion to imperial system."""
    assert IMPERIAL_SYSTEM.pressure(77, IMPERIAL_SYSTEM.pressure_unit) == 77
    assert IMPERIAL_SYSTEM.pressure(
        101352.932, METRIC_SYSTEM.pressure_unit
    ) == pytest.approx(14.7, abs=1e-4)


def test_accumulated_precipitation_same_unit():
    """Test no conversion happens if to unit is same as from unit."""
    assert (
        METRIC_SYSTEM.accumulated_precipitation(
            5, METRIC_SYSTEM.accumulated_precipitation_unit
        )
        == 5
    )


def test_accumulated_precipitation_unknown_unit():
    """Test no conversion happens if unknown unit."""
    with pytest.raises(HomeAssistantError, match="is not a recognized .* unit"):
        METRIC_SYSTEM.accumulated_precipitation(5, "K")


def test_accumulated_precipitation_to_metric():
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


def test_accumulated_precipitation_to_imperial():
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


def test_properties():
    """Test the unit properties are returned as expected."""
    assert METRIC_SYSTEM.length_unit == UnitOfLength.KILOMETERS
    assert METRIC_SYSTEM.wind_speed_unit == UnitOfSpeed.METERS_PER_SECOND
    assert METRIC_SYSTEM.temperature_unit == UnitOfTemperature.CELSIUS
    assert METRIC_SYSTEM.mass_unit == UnitOfMass.GRAMS
    assert METRIC_SYSTEM.volume_unit == UnitOfVolume.LITERS
    assert METRIC_SYSTEM.pressure_unit == UnitOfPressure.PA
    assert METRIC_SYSTEM.accumulated_precipitation_unit == UnitOfLength.MILLIMETERS


@pytest.mark.parametrize(
    "unit_system, expected_flag",
    [
        (METRIC_SYSTEM, True),
        (IMPERIAL_SYSTEM, False),
    ],
)
def test_is_metric(
    caplog: pytest.LogCaptureFixture, unit_system: UnitSystem, expected_flag: bool
):
    """Test the is metric flag."""
    assert unit_system.is_metric == expected_flag
    assert (
        "Detected code that accesses the `is_metric` property of the unit system."
        in caplog.text
    )


@pytest.mark.parametrize(
    "unit_system, expected_name, expected_private_name",
    [
        (METRIC_SYSTEM, _CONF_UNIT_SYSTEM_METRIC, _CONF_UNIT_SYSTEM_METRIC),
        (IMPERIAL_SYSTEM, _CONF_UNIT_SYSTEM_IMPERIAL, _CONF_UNIT_SYSTEM_US_CUSTOMARY),
        (
            US_CUSTOMARY_SYSTEM,
            _CONF_UNIT_SYSTEM_IMPERIAL,
            _CONF_UNIT_SYSTEM_US_CUSTOMARY,
        ),
    ],
)
def test_deprecated_name(
    caplog: pytest.LogCaptureFixture,
    unit_system: UnitSystem,
    expected_name: str,
    expected_private_name: str,
) -> None:
    """Test the name is deprecated."""
    assert unit_system.name == expected_name
    assert unit_system._name == expected_private_name
    assert (
        "Detected code that accesses the `name` property of the unit system."
        in caplog.text
    )


@pytest.mark.parametrize(
    "key, expected_system",
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
    "device_class, original_unit, state_unit",
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
        (SensorDeviceClass.GAS, UnitOfVolume.CUBIC_FEET, UnitOfVolume.CUBIC_METERS),
        (SensorDeviceClass.GAS, UnitOfVolume.CUBIC_METERS, None),
        (SensorDeviceClass.GAS, "very_much", None),
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
        (SensorDeviceClass.SPEED, "very_fast", None),
        # Test volume conversion
        (SensorDeviceClass.VOLUME, UnitOfVolume.CUBIC_FEET, UnitOfVolume.CUBIC_METERS),
        (SensorDeviceClass.VOLUME, UnitOfVolume.FLUID_OUNCES, UnitOfVolume.MILLILITERS),
        (SensorDeviceClass.VOLUME, UnitOfVolume.GALLONS, UnitOfVolume.LITERS),
        (SensorDeviceClass.VOLUME, UnitOfVolume.CUBIC_METERS, None),
        (SensorDeviceClass.VOLUME, UnitOfVolume.LITERS, None),
        (SensorDeviceClass.VOLUME, UnitOfVolume.MILLILITERS, None),
        (SensorDeviceClass.VOLUME, "very_much", None),
        # Test water meter conversion
        (SensorDeviceClass.WATER, UnitOfVolume.CUBIC_FEET, UnitOfVolume.CUBIC_METERS),
        (SensorDeviceClass.WATER, UnitOfVolume.GALLONS, UnitOfVolume.LITERS),
        (SensorDeviceClass.WATER, UnitOfVolume.CUBIC_METERS, None),
        (SensorDeviceClass.WATER, UnitOfVolume.LITERS, None),
        (SensorDeviceClass.WATER, "very_much", None),
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


@pytest.mark.parametrize(
    "device_class, original_unit, state_unit",
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
        (SensorDeviceClass.GAS, UnitOfVolume.CUBIC_METERS, UnitOfVolume.CUBIC_FEET),
        (SensorDeviceClass.GAS, UnitOfVolume.CUBIC_FEET, None),
        (SensorDeviceClass.GAS, "very_much", None),
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
        (SensorDeviceClass.SPEED, "very_fast", None),
        # Test volume conversion
        (SensorDeviceClass.VOLUME, UnitOfVolume.CUBIC_METERS, UnitOfVolume.CUBIC_FEET),
        (SensorDeviceClass.VOLUME, UnitOfVolume.LITERS, UnitOfVolume.GALLONS),
        (SensorDeviceClass.VOLUME, UnitOfVolume.MILLILITERS, UnitOfVolume.FLUID_OUNCES),
        (SensorDeviceClass.VOLUME, UnitOfVolume.CUBIC_FEET, None),
        (SensorDeviceClass.VOLUME, UnitOfVolume.FLUID_OUNCES, None),
        (SensorDeviceClass.VOLUME, UnitOfVolume.GALLONS, None),
        (SensorDeviceClass.VOLUME, "very_much", None),
        # Test water meter conversion
        (SensorDeviceClass.WATER, UnitOfVolume.CUBIC_METERS, UnitOfVolume.CUBIC_FEET),
        (SensorDeviceClass.WATER, UnitOfVolume.LITERS, UnitOfVolume.GALLONS),
        (SensorDeviceClass.WATER, UnitOfVolume.CUBIC_FEET, None),
        (SensorDeviceClass.WATER, UnitOfVolume.GALLONS, None),
        (SensorDeviceClass.WATER, "very_much", None),
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
