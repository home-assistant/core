"""Discover entity-producing capabilities without comparing live state values."""

from collections.abc import Iterator

from daikin_onecta.models import Characteristic, EnergyAggregate, ManagementPoint

from homeassistant.const import Platform

from .const import ENERGY_AGGREGATE_PERIODS
from .entity_metadata import BINARY_SENSOR_KEYS, SENSOR_KEYS, SWITCH_KEYS
from .utils import is_read_only_on_off_value

CONTROL_MANAGEMENT_POINT_TYPES = frozenset(
    {
        "climateControl",
        "climateControlMainZone",
        "domesticHotWaterFlowThrough",
        "domesticHotWaterTank",
    }
)
CLIMATE_CONTROL_MANAGEMENT_POINT_TYPES = frozenset(
    {"climateControl", "climateControlMainZone"}
)


def has_air_purifier_power_control(point: ManagementPoint) -> bool:
    """Return whether the point supports the Home Assistant air-purifier fan."""
    if point.management_point_type != "climateControl":
        return False
    air_purification = point.air_purification
    return (
        air_purification is not None
        and air_purification.power is not None
        and air_purification.power.settable
    )


def scalar_platform(
    name: str,
    characteristic: Characteristic,
    management_point_type: str,
    *,
    air_purifier_power_settable: bool = False,
) -> Platform | None:
    """Return the platform that exposes a scalar characteristic, if any."""
    values = characteristic.values or []
    if characteristic.settable and set(values) == {"on", "off"}:
        if (
            name == "econoMode"
            and management_point_type in CLIMATE_CONTROL_MANAGEMENT_POINT_TYPES
        ):
            return None
        return Platform.SWITCH if name in SWITCH_KEYS else None
    if name in BINARY_SENSOR_KEYS and (
        characteristic.values is None
        or is_read_only_on_off_value(characteristic.settable, characteristic.values)
    ):
        return Platform.BINARY_SENSOR
    if name in SENSOR_KEYS and not (
        name == "airPurificationMode"
        and management_point_type in CONTROL_MANAGEMENT_POINT_TYPES
        and air_purifier_power_settable
    ):
        return Platform.SENSOR
    return None


def scalar_platform_for_point(
    point: ManagementPoint,
    name: str,
    characteristic: Characteristic | None = None,
) -> Platform | None:
    """Return the Home Assistant platform for a point's scalar characteristic."""
    if characteristic is None:
        characteristic = point.scalar_characteristic(name)
    if characteristic is None:
        return None
    # These controls belong to their typed entity even when Daikin reports them
    # as read-only while the gateway is offline.
    if name in {"onOffMode", "powerfulMode"} and (
        (
            point.management_point_type == "climateControl"
            and point.climate_control is not None
        )
        or (
            point.management_point_type
            in {"domesticHotWaterFlowThrough", "domesticHotWaterTank"}
            and point.domestic_hot_water is not None
        )
    ):
        return None
    return scalar_platform(
        name,
        characteristic,
        point.management_point_type,
        air_purifier_power_settable=has_air_purifier_power_control(point),
    )


def scalar_characteristics_for_platform(
    point: ManagementPoint, platform: Platform
) -> Iterator[tuple[str, Characteristic]]:
    """Yield scalar characteristics exposed by one platform."""
    return (
        (name, characteristic)
        for name, characteristic in point.scalar_characteristics().items()
        if scalar_platform_for_point(point, name, characteristic) is platform
    )


def energy_description_key(aggregate: EnergyAggregate) -> str | None:
    """Return the sensor description key for a supported energy aggregate."""
    if (period := ENERGY_AGGREGATE_PERIODS.get(aggregate.period)) is None:
        return None
    description = (
        f"{aggregate.operation_mode.capitalize()}{period.label}"
        f"{aggregate.source.capitalize()}{aggregate.data_type.capitalize()}"
    )
    return description if description in SENSOR_KEYS else None
