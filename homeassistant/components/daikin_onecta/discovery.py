"""Discover entity-producing capabilities without comparing live state values."""

from daikin_onecta.models import Characteristic, GatewayDevice, ManagementPoint

from homeassistant.const import Platform

from .const import CONTROL_MANAGEMENT_POINT_TYPES, SENSORY_DATA_SENSOR_TYPES
from .entity_descriptions import (
    BINARY_SENSOR_DESCRIPTIONS,
    SENSOR_DESCRIPTIONS,
    SWITCH_DESCRIPTIONS,
)
from .utils import is_read_only_on_off_value


def scalar_platform(
    name: str, characteristic: Characteristic, management_point_type: str
) -> Platform | None:
    """Return the platform that exposes a scalar characteristic, if any."""
    values = characteristic.values or []
    if characteristic.settable and "on" in values and "off" in values:
        return Platform.SWITCH if name in SWITCH_DESCRIPTIONS else None
    if name in BINARY_SENSOR_DESCRIPTIONS and (
        characteristic.values is None
        or is_read_only_on_off_value(characteristic.settable, characteristic.values)
    ):
        return Platform.BINARY_SENSOR
    if name in SENSOR_DESCRIPTIONS and not (
        name == "operationMode"
        and management_point_type in CONTROL_MANAGEMENT_POINT_TYPES
    ):
        return Platform.SENSOR
    return None


def management_point_entity_keys(point: ManagementPoint) -> set[str]:
    """Return the entities a management point can expose during platform setup."""
    keys: set[str] = set()
    if (climate := point.climate_control) is not None:
        keys.update(f"climate:{target}" for target in climate.setpoint_types)
    if point.domestic_hot_water is not None:
        keys.add("water_heater")
    if (
        (purification := point.air_purification) is not None
        and purification.power is not None
        and purification.power.settable
    ):
        keys.add("fan")
    if point.schedule_state is not None:
        keys.add("schedule")
    if point.firmware is not None:
        keys.add("firmware")

    for name, characteristic in point.scalar_characteristics().items():
        if (
            platform := scalar_platform(
                name, characteristic, point.management_point_type
            )
        ) is not None:
            keys.add(f"{platform}:{name}")

    keys.update(
        f"sensory:{name}"
        for name in SENSORY_DATA_SENSOR_TYPES
        if point.sensory_characteristic(name) is not None
    )
    periods = {"day": "Daily", "week": "Weekly", "month": "Monthly", "year": "Yearly"}
    for aggregate in point.energy_aggregates:
        if (period := periods.get(aggregate.period)) is None:
            continue
        description = (
            f"{aggregate.operation_mode.capitalize()}{period}"
            f"{aggregate.source.capitalize()}{aggregate.data_type.capitalize()}"
        )
        if description in SENSOR_DESCRIPTIONS:
            keys.add(f"energy:{description}")
    return keys


def gateway_entity_keys(device: GatewayDevice) -> set[tuple[str, str | None, str]]:
    """Return gateway, management-point, and supported entity identities."""
    keys: set[tuple[str, str | None, str]] = {(device.id, None, "gateway")}
    for point in device.management_points:
        keys.add((device.id, point.embedded_id, point.management_point_type))
        keys.update(
            (device.id, point.embedded_id, key)
            for key in management_point_entity_keys(point)
        )
    return keys
