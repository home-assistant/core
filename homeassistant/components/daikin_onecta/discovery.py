"""Discover entity-producing capabilities without comparing live state values."""

from daikin_onecta.models import GatewayDevice, ManagementPoint

from .const import SENSORY_DATA_SENSOR_TYPES
from .entity_descriptions import SENSOR_DESCRIPTIONS

_CONTROL_MANAGEMENT_POINT_TYPES = {
    "domesticHotWaterTank",
    "domesticHotWaterFlowThrough",
    "climateControl",
    "climateControlMainZone",
}


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
    if (firmware := point.firmware) is not None and firmware.has_installed_version:
        keys.add("firmware")

    for name, characteristic in point.scalar_characteristics().items():
        values = characteristic.values or []
        if (
            characteristic.value is not None
            and characteristic.settable
            and "on" in values
            and "off" in values
        ):
            if not (
                name in {"onOffMode", "powerfulMode"}
                and point.management_point_type in _CONTROL_MANAGEMENT_POINT_TYPES
            ):
                keys.add(f"switch:{name}")
        elif isinstance(characteristic.value, bool) and not values:
            if characteristic.values is None:
                keys.add(f"binary_sensor:{name}")
        elif name in SENSOR_DESCRIPTIONS and characteristic.value is not None:
            if not (
                name == "operationMode"
                and point.management_point_type in _CONTROL_MANAGEMENT_POINT_TYPES
            ):
                keys.add(f"sensor:{name}")

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
