"""Common methods."""

from .const import BINARY_SENSOR_NAME_PREFIX


def generate_entity_name(user_name: str) -> str:
    """Generate name."""

    return f"{BINARY_SENSOR_NAME_PREFIX}{user_name.lower().capitalize()}"
