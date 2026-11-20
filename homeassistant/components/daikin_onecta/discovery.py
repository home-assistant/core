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


def scalar_platform(
    name: str, characteristic: Characteristic, management_point_type: str
) -> Platform | None:
    """Return the platform that exposes a scalar characteristic, if any."""
    values = characteristic.values or []
    if characteristic.settable and "on" in values and "off" in values:
        return Platform.SWITCH if name in SWITCH_KEYS else None
    if name in BINARY_SENSOR_KEYS and (
        characteristic.values is None
        or is_read_only_on_off_value(characteristic.settable, characteristic.values)
    ):
        return Platform.BINARY_SENSOR
    if name in SENSOR_KEYS and not (
        name in {"operationMode", "airPurificationMode"}
        and management_point_type in CONTROL_MANAGEMENT_POINT_TYPES
    ):
        return Platform.SENSOR
    return None


def scalar_characteristics_for_platform(
    point: ManagementPoint, platform: Platform
) -> Iterator[tuple[str, Characteristic]]:
    """Yield scalar characteristics exposed by one platform."""
    return (
        (name, characteristic)
        for name, characteristic in point.scalar_characteristics().items()
        if scalar_platform(name, characteristic, point.management_point_type)
        is platform
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
