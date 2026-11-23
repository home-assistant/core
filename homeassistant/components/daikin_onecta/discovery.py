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


def has_air_purifier_power(point: ManagementPoint | None) -> bool:
    """Return whether the management point exposes air-purifier power."""
    return _air_purifier_power(point) is not None


def _air_purifier_power(point: ManagementPoint | None) -> Characteristic[str] | None:
    """Return the air-purifier power characteristic when it is exposed."""
    if point is None or point.management_point_type != "climateControl":
        return None
    air_purification = point.air_purification
    return air_purification.power if air_purification is not None else None


def has_air_purifier_power_control(point: ManagementPoint | None) -> bool:
    """Return whether the air-purifier power characteristic is writable."""
    power = _air_purifier_power(point)
    return power is not None and power.settable


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


def scalar_platform(name: str) -> Platform | None:
    """Return the stable platform assigned to a scalar characteristic key."""
    # Platform ownership comes from the characteristic's integration metadata,
    # not its current writability, which can change with gateway or device state.
    if name in SWITCH_KEYS:
        return Platform.SWITCH
    if name in BINARY_SENSOR_KEYS:
        return Platform.BINARY_SENSOR
    if name in SENSOR_KEYS:
        return Platform.SENSOR
    return None


def scalar_platform_for_point(
    point: ManagementPoint,
    name: str,
    *,
    gateway_online: bool = True,
) -> Platform | None:
    """Return the Home Assistant platform for a point's scalar characteristic."""
    if (
        name == "airPurificationMode"
        and point.management_point_type == "climateControl"
        and (
            not gateway_online
            or (has_air_purifier_power(point) and not has_climate_entity(point))
        )
    ):
        return None
    # Keep climate power and mode characteristics on the climate entity when
    # that point produces one, rather than exposing duplicate scalar entities.
    if (
        name in {"econoMode", "onOffMode", "powerfulMode"}
        and point.management_point_type == "climateControl"
        and has_climate_entity(point)
    ):
        return None
    if name == "onOffMode" and point.management_point_type == "climateControl":
        if point.air_purification is not None:
            return None
    # Keep water-heater power controls on the typed entity.
    if name in {"onOffMode", "powerfulMode"} and (
        point.management_point_type
        in {"domesticHotWaterFlowThrough", "domesticHotWaterTank"}
        and point.domestic_hot_water is not None
    ):
        return None
    return scalar_platform(name)


def scalar_characteristics_for_platform(
    point: ManagementPoint, platform: Platform, *, gateway_online: bool = True
) -> Iterator[tuple[str, Characteristic]]:
    """Yield scalar characteristics exposed by one platform."""
    return (
        (name, characteristic)
        for name, characteristic in point.scalar_characteristics().items()
        if (
            scalar_platform_for_point(point, name, gateway_online=gateway_online)
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
