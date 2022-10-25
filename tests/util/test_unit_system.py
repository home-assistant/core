"""Test the unit system helper."""
from __future__ import annotations

import pytest

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
    ACCUMULATED_PRECIPITATION,
    LENGTH,
    LENGTH_CENTIMETERS,
    LENGTH_FEET,
    LENGTH_INCHES,
    LENGTH_KILOMETERS,
    LENGTH_METERS,
    LENGTH_MILES,
    LENGTH_MILLIMETERS,
    LENGTH_YARD,
    MASS,
    MASS_GRAMS,
    PRESSURE,
    PRESSURE_PA,
    SPEED_FEET_PER_SECOND,
    SPEED_KILOMETERS_PER_HOUR,
    SPEED_KNOTS,
    SPEED_METERS_PER_SECOND,
    SPEED_MILES_PER_HOUR,
    TEMP_CELSIUS,
    TEMPERATURE,
    VOLUME,
    VOLUME_CUBIC_FEET,
    VOLUME_CUBIC_METERS,
    VOLUME_FLUID_OUNCE,
    VOLUME_GALLONS,
    VOLUME_LITERS,
    VOLUME_MILLILITERS,
    WIND_SPEED,
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
            accumulated_precipitation=LENGTH_MILLIMETERS,
            conversions={},
            length=LENGTH_METERS,
            mass=MASS_GRAMS,
            pressure=PRESSURE_PA,
            temperature=INVALID_UNIT,
            volume=VOLUME_LITERS,
            wind_speed=SPEED_METERS_PER_SECOND,
        )

    with pytest.raises(ValueError):
        UnitSystem(
            SYSTEM_NAME,
            accumulated_precipitation=LENGTH_MILLIMETERS,
            conversions={},
            length=INVALID_UNIT,
            mass=MASS_GRAMS,
            pressure=PRESSURE_PA,
            temperature=TEMP_CELSIUS,
            volume=VOLUME_LITERS,
            wind_speed=SPEED_METERS_PER_SECOND,
        )

    with pytest.raises(ValueError):
        UnitSystem(
            SYSTEM_NAME,
            accumulated_precipitation=LENGTH_MILLIMETERS,
            conversions={},
            length=LENGTH_METERS,
            mass=MASS_GRAMS,
            pressure=PRESSURE_PA,
            temperature=TEMP_CELSIUS,
            volume=VOLUME_LITERS,
            wind_speed=INVALID_UNIT,
        )

    with pytest.raises(ValueError):
        UnitSystem(
            SYSTEM_NAME,
            accumulated_precipitation=LENGTH_MILLIMETERS,
            conversions={},
            length=LENGTH_METERS,
            mass=MASS_GRAMS,
            pressure=PRESSURE_PA,
            temperature=TEMP_CELSIUS,
            volume=INVALID_UNIT,
            wind_speed=SPEED_METERS_PER_SECOND,
        )

    with pytest.raises(ValueError):
        UnitSystem(
            SYSTEM_NAME,
            accumulated_precipitation=LENGTH_MILLIMETERS,
            conversions={},
            length=LENGTH_METERS,
            mass=INVALID_UNIT,
            pressure=PRESSURE_PA,
            temperature=TEMP_CELSIUS,
            volume=VOLUME_LITERS,
            wind_speed=SPEED_METERS_PER_SECOND,
        )

    with pytest.raises(ValueError):
        UnitSystem(
            SYSTEM_NAME,
            accumulated_precipitation=LENGTH_MILLIMETERS,
            conversions={},
            length=LENGTH_METERS,
            mass=MASS_GRAMS,
            pressure=INVALID_UNIT,
            temperature=TEMP_CELSIUS,
            volume=VOLUME_LITERS,
            wind_speed=SPEED_METERS_PER_SECOND,
        )

    with pytest.raises(ValueError):
        UnitSystem(
            SYSTEM_NAME,
            accumulated_precipitation=INVALID_UNIT,
            conversions={},
            length=LENGTH_METERS,
            mass=MASS_GRAMS,
            pressure=PRESSURE_PA,
            temperature=TEMP_CELSIUS,
            volume=VOLUME_LITERS,
            wind_speed=SPEED_METERS_PER_SECOND,
        )


def test_invalid_value():
    """Test no conversion happens if value is non-numeric."""
    with pytest.raises(TypeError):
        METRIC_SYSTEM.length("25a", LENGTH_KILOMETERS)
    with pytest.raises(TypeError):
        METRIC_SYSTEM.temperature("50K", TEMP_CELSIUS)
    with pytest.raises(TypeError):
        METRIC_SYSTEM.wind_speed("50km/h", SPEED_METERS_PER_SECOND)
    with pytest.raises(TypeError):
        METRIC_SYSTEM.volume("50L", VOLUME_LITERS)
    with pytest.raises(TypeError):
        METRIC_SYSTEM.pressure("50Pa", PRESSURE_PA)
    with pytest.raises(TypeError):
        METRIC_SYSTEM.accumulated_precipitation("50mm", LENGTH_MILLIMETERS)


def test_as_dict():
    """Test that the as_dict() method returns the expected dictionary."""
    expected = {
        LENGTH: LENGTH_KILOMETERS,
        WIND_SPEED: SPEED_METERS_PER_SECOND,
        TEMPERATURE: TEMP_CELSIUS,
        VOLUME: VOLUME_LITERS,
        MASS: MASS_GRAMS,
        PRESSURE: PRESSURE_PA,
        ACCUMULATED_PRECIPITATION: LENGTH_MILLIMETERS,
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
    assert METRIC_SYSTEM.length_unit == LENGTH_KILOMETERS
    assert METRIC_SYSTEM.wind_speed_unit == SPEED_METERS_PER_SECOND
    assert METRIC_SYSTEM.temperature_unit == TEMP_CELSIUS
    assert METRIC_SYSTEM.mass_unit == MASS_GRAMS
    assert METRIC_SYSTEM.volume_unit == VOLUME_LITERS
    assert METRIC_SYSTEM.pressure_unit == PRESSURE_PA
    assert METRIC_SYSTEM.accumulated_precipitation_unit == LENGTH_MILLIMETERS


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
        # Test distance conversion
        (SensorDeviceClass.DISTANCE, LENGTH_FEET, LENGTH_METERS),
        (SensorDeviceClass.DISTANCE, LENGTH_INCHES, LENGTH_MILLIMETERS),
        (SensorDeviceClass.DISTANCE, LENGTH_MILES, LENGTH_KILOMETERS),
        (SensorDeviceClass.DISTANCE, LENGTH_YARD, LENGTH_METERS),
        (SensorDeviceClass.DISTANCE, LENGTH_KILOMETERS, None),
        (SensorDeviceClass.DISTANCE, "very_long", None),
        # Test gas meter conversion
        (SensorDeviceClass.GAS, VOLUME_CUBIC_FEET, VOLUME_CUBIC_METERS),
        (SensorDeviceClass.GAS, VOLUME_CUBIC_METERS, None),
        (SensorDeviceClass.GAS, "very_much", None),
        # Test speed conversion
        (SensorDeviceClass.SPEED, SPEED_FEET_PER_SECOND, SPEED_KILOMETERS_PER_HOUR),
        (SensorDeviceClass.SPEED, SPEED_MILES_PER_HOUR, SPEED_KILOMETERS_PER_HOUR),
        (SensorDeviceClass.SPEED, SPEED_KILOMETERS_PER_HOUR, None),
        (SensorDeviceClass.SPEED, SPEED_KNOTS, None),
        (SensorDeviceClass.SPEED, SPEED_METERS_PER_SECOND, None),
        (SensorDeviceClass.SPEED, "very_fast", None),
        # Test volume conversion
        (SensorDeviceClass.VOLUME, VOLUME_CUBIC_FEET, VOLUME_CUBIC_METERS),
        (SensorDeviceClass.VOLUME, VOLUME_FLUID_OUNCE, VOLUME_MILLILITERS),
        (SensorDeviceClass.VOLUME, VOLUME_GALLONS, VOLUME_LITERS),
        (SensorDeviceClass.VOLUME, VOLUME_CUBIC_METERS, None),
        (SensorDeviceClass.VOLUME, VOLUME_LITERS, None),
        (SensorDeviceClass.VOLUME, VOLUME_MILLILITERS, None),
        (SensorDeviceClass.VOLUME, "very_much", None),
        # Test water meter conversion
        (SensorDeviceClass.WATER, VOLUME_CUBIC_FEET, VOLUME_CUBIC_METERS),
        (SensorDeviceClass.WATER, VOLUME_GALLONS, VOLUME_LITERS),
        (SensorDeviceClass.WATER, VOLUME_CUBIC_METERS, None),
        (SensorDeviceClass.WATER, VOLUME_LITERS, None),
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
        # Test distance conversion
        (SensorDeviceClass.DISTANCE, LENGTH_CENTIMETERS, LENGTH_INCHES),
        (SensorDeviceClass.DISTANCE, LENGTH_KILOMETERS, LENGTH_MILES),
        (SensorDeviceClass.DISTANCE, LENGTH_METERS, LENGTH_FEET),
        (SensorDeviceClass.DISTANCE, LENGTH_MILLIMETERS, LENGTH_INCHES),
        (SensorDeviceClass.DISTANCE, LENGTH_MILES, None),
        (SensorDeviceClass.DISTANCE, "very_long", None),
        # Test gas meter conversion
        (SensorDeviceClass.GAS, VOLUME_CUBIC_METERS, VOLUME_CUBIC_FEET),
        (SensorDeviceClass.GAS, VOLUME_CUBIC_FEET, None),
        (SensorDeviceClass.GAS, "very_much", None),
        # Test speed conversion
        (SensorDeviceClass.SPEED, SPEED_METERS_PER_SECOND, SPEED_MILES_PER_HOUR),
        (SensorDeviceClass.SPEED, SPEED_KILOMETERS_PER_HOUR, SPEED_MILES_PER_HOUR),
        (SensorDeviceClass.SPEED, SPEED_FEET_PER_SECOND, None),
        (SensorDeviceClass.SPEED, SPEED_KNOTS, None),
        (SensorDeviceClass.SPEED, SPEED_MILES_PER_HOUR, None),
        (SensorDeviceClass.SPEED, "very_fast", None),
        # Test volume conversion
        (SensorDeviceClass.VOLUME, VOLUME_CUBIC_METERS, VOLUME_CUBIC_FEET),
        (SensorDeviceClass.VOLUME, VOLUME_LITERS, VOLUME_GALLONS),
        (SensorDeviceClass.VOLUME, VOLUME_MILLILITERS, VOLUME_FLUID_OUNCE),
        (SensorDeviceClass.VOLUME, VOLUME_CUBIC_FEET, None),
        (SensorDeviceClass.VOLUME, VOLUME_FLUID_OUNCE, None),
        (SensorDeviceClass.VOLUME, VOLUME_GALLONS, None),
        (SensorDeviceClass.VOLUME, "very_much", None),
        # Test water meter conversion
        (SensorDeviceClass.WATER, VOLUME_CUBIC_METERS, VOLUME_CUBIC_FEET),
        (SensorDeviceClass.WATER, VOLUME_LITERS, VOLUME_GALLONS),
        (SensorDeviceClass.WATER, VOLUME_CUBIC_FEET, None),
        (SensorDeviceClass.WATER, VOLUME_GALLONS, None),
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
