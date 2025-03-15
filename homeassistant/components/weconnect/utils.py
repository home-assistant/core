"""Utility functions for the WeConnect integration."""

from typing import Any

from weconnect.elements.range_status import RangeStatus
from weconnect.weconnect import Vehicle

from .const import ELECTRIC_ENGINE, FUEL_ENGINES


def get_domain(vehicle: Vehicle, *args: Any) -> Any:
    """Get the domain from the Vehicle object."""
    domain = vehicle.domains
    for name in args:
        if name not in domain:
            return None

        domain = domain[name]

    return domain


def get_fuel_engine(vehicle: Vehicle) -> RangeStatus.Engine | None:
    """Get the RangeStatus.Engine object for the fuel engine."""
    if (domain := get_domain(vehicle, "fuelStatus", "rangeStatus")) is None:
        return None
    if domain.primaryEngine.type.value in FUEL_ENGINES:
        return domain.primaryEngine
    if (
        secondaryEngine := domain.secondaryEngine
    ) is not None and secondaryEngine.type.value in FUEL_ENGINES:
        return secondaryEngine
    return None


def get_electric_engine(vehicle: Vehicle) -> RangeStatus.Engine | None:
    """Get the RangeStatus.Engine object for the electric engine."""
    if (domain := get_domain(vehicle, "fuelStatus", "rangeStatus")) is None:
        return None
    if domain.primaryEngine.type.value == ELECTRIC_ENGINE:
        return domain.primaryEngine
    if (
        secondaryEngine := domain.secondaryEngine
    ) is not None and secondaryEngine.type.value == ELECTRIC_ENGINE:
        return secondaryEngine
    return None
