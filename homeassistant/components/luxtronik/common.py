"""Support for Luxtronik classes."""
from typing import Any

from .const import CONF_CALCULATIONS, CONF_PARAMETERS, CONF_VISIBILITIES, LOGGER
from .coordinator import LuxtronikCoordinatorData


def get_sensor_data(
    sensors: LuxtronikCoordinatorData,
    luxtronik_key: str,
) -> Any:
    """Get sensor data."""
    key = luxtronik_key.split(".")
    return _get_key_value(sensors, key[0], key[1])


def _get_key_value(
    sensors: LuxtronikCoordinatorData | None,
    group: str,
    sensor_id: str,
) -> Any:
    if sensors is None:
        return None
    if group == CONF_PARAMETERS:
        sensor = sensors.parameters.get(sensor_id)
    elif group == CONF_CALCULATIONS:
        sensor = sensors.calculations.get(sensor_id)
    elif group == CONF_VISIBILITIES:
        sensor = sensors.visibilities.get(sensor_id)
    else:
        raise NotImplementedError
    if sensor is None:
        LOGGER.warning(
            "Get_sensor %s returns None",
            sensor_id,
        )

        return None
    return sensor.value
