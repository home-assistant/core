"""Utility functions for here_weather."""

from typing import Optional

from homeassistant.const import (
    CONF_UNIT_SYSTEM_METRIC,
    LENGTH_CENTIMETERS,
    LENGTH_INCHES,
    LENGTH_KILOMETERS,
    LENGTH_MILES,
    PRESSURE_INHG,
    PRESSURE_MBAR,
    SPEED_KILOMETERS_PER_HOUR,
    SPEED_MILES_PER_HOUR,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)


def convert_unit_of_measurement_if_needed(unit_system, unit_of_measurement: str) -> str:
    """Convert the unit of measurement to imperial if configured."""
    if unit_system != CONF_UNIT_SYSTEM_METRIC:
        if unit_of_measurement == TEMP_CELSIUS:
            unit_of_measurement = TEMP_FAHRENHEIT
        elif unit_of_measurement == LENGTH_CENTIMETERS:
            unit_of_measurement = LENGTH_INCHES
        elif unit_of_measurement == SPEED_KILOMETERS_PER_HOUR:
            unit_of_measurement = SPEED_MILES_PER_HOUR
        elif unit_of_measurement == PRESSURE_MBAR:
            unit_of_measurement = PRESSURE_INHG
        elif unit_of_measurement == LENGTH_KILOMETERS:
            unit_of_measurement = LENGTH_MILES
    return unit_of_measurement


def get_attribute_from_here_data(
    here_data: list, attribute_name: str, sensor_number: int = 0
) -> Optional[str]:
    """Extract and convert data from HERE response or None if not found."""
    if here_data is None:
        return None
    try:
        state = here_data[sensor_number][attribute_name]
        state = convert_asterisk_to_none(state)
        return state
    except KeyError:
        return None


def convert_asterisk_to_none(state: str) -> str:
    """Convert HERE API representation of None."""
    if state == "*":
        state = None
    return state
