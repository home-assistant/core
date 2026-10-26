"""Shared helpers for the ENGIE Belgium automation triggers and conditions."""

from collections.abc import Callable, Iterable
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from aioengiebelgium import EpexGranularity
import probatio

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID, CONF_ABOVE, CONF_BELOW
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import DOMAIN
from .coordinator import (
    BRUSSELS_TIME_ZONE,
    EngieBeEpexCoordinator,
    EngieBeEpexData,
    epex_slot_covering,
    epex_slots_cover_day,
    epex_slots_for_day,
)

if TYPE_CHECKING:
    from . import EngieBeRuntimeData

DEVICE_IDS_SCHEMA: dict[probatio.Marker, Any] = {
    probatio.Required(ATTR_DEVICE_ID): probatio.All(
        probatio.EnsureList(), probatio.Length(min=1), [cv.string]
    ),
}

THRESHOLD_SCHEMA: dict[probatio.Marker, Any] = {
    probatio.Optional(CONF_ABOVE): probatio.Coerce(float),
    probatio.Optional(CONF_BELOW): probatio.Coerce(float),
}


def validate_threshold(options: dict[str, Any]) -> dict[str, Any]:
    """Require at least one bound and a range that is not empty."""
    above = options.get(CONF_ABOVE)
    below = options.get(CONF_BELOW)
    if above is None and below is None:
        raise probatio.Invalid("Set above, below or both")
    if above is not None and below is not None and above >= below:
        raise probatio.Invalid("Above must be lower than below")
    return options


def price_in_range(price: float, above: float | None, below: float | None) -> bool:
    """Return True when the price is above the lower and below the upper bound."""
    return (above is None or price > above) and (below is None or price < below)


@callback
def async_validate_device_ids(hass: HomeAssistant, device_ids: Iterable[str]) -> None:
    """Raise when a device does not belong to ENGIE Belgium."""
    for device_id in device_ids:
        _, entry = dr.async_get_device_and_config_entry_for_domain(
            hass, device_id, domain=DOMAIN
        )
        if entry is None:
            raise probatio.Invalid(f"Device {device_id} is not an ENGIE Belgium device")


@callback
def async_get_device_epex(
    hass: HomeAssistant, device_id: str
) -> EngieBeEpexCoordinator | None:
    """Return the EPEX coordinator when the device has a dynamic tariff."""
    device, entry = dr.async_get_device_and_config_entry_for_domain(
        hass, device_id, domain=DOMAIN
    )
    if device is None or entry is None or entry.state is not ConfigEntryState.LOADED:
        return None
    runtime_data: EngieBeRuntimeData = entry.runtime_data
    if runtime_data.epex is None:
        return None
    if not any(
        (household := runtime_data.households.get(ban)) is not None
        and household.is_dynamic
        for domain, ban in device.identifiers
        if domain == DOMAIN
    ):
        return None
    return runtime_data.epex


def epex_price_at(
    data: EngieBeEpexData, granularity: EpexGranularity, moment: datetime
) -> float | None:
    """Return the EPEX price of the slot that covers the moment."""
    slot = epex_slot_covering(data.slots(granularity), moment)
    return None if slot is None else slot.value_eur_per_kwh


def epex_current_price(
    data: EngieBeEpexData, granularity: EpexGranularity, now: datetime
) -> float | None:
    """Return the EPEX price of the current slot."""
    return epex_price_at(data, granularity, now)


def epex_next_price(
    data: EngieBeEpexData, granularity: EpexGranularity, now: datetime
) -> float | None:
    """Return the EPEX price of the slot after the current one."""
    return epex_price_at(data, granularity, now + timedelta(minutes=granularity.value))


def epex_extreme_price_today(
    data: EngieBeEpexData,
    granularity: EpexGranularity,
    now: datetime,
    choose: Callable[[Iterable[float]], float],
) -> float | None:
    """Return the lowest or highest EPEX price of today in Brussels."""
    today = now.astimezone(BRUSSELS_TIME_ZONE).date()
    slots = data.slots(granularity)
    if not epex_slots_cover_day(slots, today, granularity):
        return None
    return choose(slot.value_eur_per_kwh for slot in epex_slots_for_day(slots, today))
