"""Utility functions for here_weather."""

from homeassistant.const import CONF_UNIT_SYSTEM_METRIC


def convert_unit_of_measurement_if_needed(unit_system, unit_of_measurement: str) -> str:
    """Convert the unit of measurement to imperial if configured."""
    if unit_system != CONF_UNIT_SYSTEM_METRIC:
        if unit_of_measurement == "°C":
            unit_of_measurement = "°F"
        elif unit_of_measurement == "cm":
            unit_of_measurement = "in"
        elif unit_of_measurement == "km/h":
            unit_of_measurement = "mph"
        elif unit_of_measurement == "mbar":
            unit_of_measurement = "in"
        elif unit_of_measurement == "km":
            unit_of_measurement = "mi"
    return unit_of_measurement


def get_attribute_from_here_data(
    here_data: list, attribute_name: str, sensor_number: int = 0
) -> str:
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
