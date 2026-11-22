"""Discover entity-producing capabilities without comparing live state values."""

from collections.abc import Iterator

from daikin_onecta.models import Characteristic, EnergyAggregate, ManagementPoint

from homeassistant.const import Platform

from .const import (
    BINARY_SENSOR_KEYS,
    CLIMATE_SETPOINT_TYPES,
    ENERGY_AGGREGATE_PERIODS,
    SENSOR_KEYS,
    SWITCH_KEYS,
)
from .utils import is_read_only_on_off_value


def has_air_purifier_power_control(point: ManagementPoint | None) -> bool:
    """Return whether the air-purifier power characteristic is writable."""
    if point is None or point.management_point_type != "climateControl":
        return False
    air_purification = point.air_purification
    return bool(
        air_purification is not None
        and air_purification.power is not None
        and air_purification.power.settable
    )


def has_climate_entity(point: ManagementPoint) -> bool:
    """Return whether a climate-control point exposes a supported setpoint."""
    climate_control = point.climate_control
    return bool(
        climate_control is not None
        and any(
            setpoint_type in CLIMATE_SETPOINT_TYPES
            for setpoint_type in climate_control.setpoint_types
        )
    )


def scalar_platform(
    name: str,
    characteristic: Characteristic,
) -> Platform | None:
    """Return the platform that exposes a scalar characteristic, if any."""
    values = characteristic.values or []
    if characteristic.settable and set(values) == {"on", "off"}:
        return Platform.SWITCH if name in SWITCH_KEYS and name != "onOffMode" else None
    if name in BINARY_SENSOR_KEYS and (
        characteristic.values is None
        or is_read_only_on_off_value(characteristic.settable, characteristic.values)
    ):
        return Platform.BINARY_SENSOR
    if name in SENSOR_KEYS:
        return Platform.SENSOR
    return None


def scalar_platform_for_point(
    point: ManagementPoint,
    name: str,
    characteristic: Characteristic | None = None,
    *,
    gateway_online: bool = True,
) -> Platform | None:
    """Return the Home Assistant platform for a point's scalar characteristic."""
    if characteristic is None:
        characteristic = point.scalar_characteristic(name)
    if characteristic is None:
        return None
    if (
        name == "airPurificationMode"
        and point.management_point_type == "climateControl"
        and (not gateway_online or has_air_purifier_power_control(point))
    ):
        return None
    # Econo mode is already exposed as a preset only on climate points that
    # also produce a climate entity; otherwise retain the scalar switch.
    if (
        name in {"econoMode", "onOffMode", "powerfulMode"}
        and point.management_point_type == "climateControl"
        and has_climate_entity(point)
    ):
        return None
    if (
        name in {"onOffMode", "powerfulMode"}
        and point.management_point_type == "climateControl"
        and point.air_purification is None
        and not gateway_online
    ):
        return Platform.SWITCH if name in SWITCH_KEYS else None
    if name == "onOffMode" and point.management_point_type == "climateControl":
        if point.air_purification is not None:
            return None
        if characteristic.settable and set(characteristic.values or []) == {
            "on",
            "off",
        }:
            return Platform.SWITCH
    # These controls belong to their typed entity even when Daikin reports them
    # as read-only while the gateway is offline.
    if name in {"onOffMode", "powerfulMode"} and (
        point.management_point_type
        in {"domesticHotWaterFlowThrough", "domesticHotWaterTank"}
        and point.domestic_hot_water is not None
    ):
        return None
    return scalar_platform(name, characteristic)


def scalar_characteristics_for_platform(
    point: ManagementPoint, platform: Platform, *, gateway_online: bool = True
) -> Iterator[tuple[str, Characteristic]]:
    """Yield scalar characteristics exposed by one platform."""
    return (
        (name, characteristic)
        for name, characteristic in point.scalar_characteristics().items()
        if (
            scalar_platform_for_point(
                point, name, characteristic, gateway_online=gateway_online
            )
            is platform
        )
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
