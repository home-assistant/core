"""Diagnostics support for the ENGIE Belgium integration."""

from datetime import timedelta
import hashlib
from typing import TYPE_CHECKING, Any

from aioengiebelgium import EpexGranularity, bare_ean

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_EMAIL
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import CONF_REFRESH_TOKEN
from .coordinator import (
    BRUSSELS_TIME_ZONE,
    EngieBeEpexCoordinator,
    epex_day_available,
    epex_slots_for_day,
)

if TYPE_CHECKING:
    from . import EngieBeConfigEntry, EngieBeHouseholdCoordinators

TO_REDACT = {
    CONF_ACCESS_TOKEN,
    CONF_EMAIL,
    CONF_REFRESH_TOKEN,
    "title",
    "unique_id",
}


def _hashed_identifier(identifier: str) -> str:
    """Return a stable fingerprint that keeps households and meters apart."""
    return f"**REDACTED_{hashlib.sha256(identifier.encode()).hexdigest()[:16]}"


def _household_diagnostics(
    household: EngieBeHouseholdCoordinators,
) -> dict[str, Any]:
    """Return the diagnostics of one business agreement."""
    prices = household.prices
    slots: dict[str, dict[str, dict[str, dict[str, float]]]] = {}
    for (ean, direction, slot_code), price_slot in (
        prices.data.slots.items() if prices.data is not None else ()
    ):
        per_ean = slots.setdefault(_hashed_identifier(bare_ean(ean)), {})
        per_direction = per_ean.setdefault(direction, {})
        per_direction[slot_code] = {
            "price_value": price_slot.price_value,
            "price_value_excl_vat": price_slot.price_value_excl_vat,
        }
    return {
        "ean_count": len(prices.data.eans) if prices.data is not None else None,
        "is_dynamic": household.is_dynamic,
        "last_update_success": prices.last_update_success,
        "update_interval": str(prices.update_interval),
        "energy_types": {
            _hashed_identifier(ean): energy_type
            for ean, energy_type in prices.ean_energy_types.items()
        },
        "slots": slots,
    }


def _epex_diagnostics(epex: EngieBeEpexCoordinator) -> dict[str, Any]:
    """Return the diagnostics of the EPEX day-ahead prices."""
    data = epex.data
    all_slots = [
        slot for granularity in EpexGranularity for slot in data.slots(granularity)
    ]
    first_slot_start = min((slot.start for slot in all_slots), default=None)
    last_slot_end = max((slot.end for slot in all_slots), default=None)
    today = dt_util.now(BRUSSELS_TIME_ZONE).date()
    today_prices: dict[str, dict[str, float | None]] = {}
    for granularity in EpexGranularity:
        values = [
            slot.value_eur_per_kwh
            for slot in epex_slots_for_day(data.slots(granularity), today)
        ]
        today_prices[granularity.name] = {
            "min": min(values) if values else None,
            "max": max(values) if values else None,
        }
    return {
        "last_update_success": epex.last_update_success,
        "update_interval": str(epex.update_interval),
        "slot_counts": {
            granularity.name: len(data.slots(granularity))
            for granularity in EpexGranularity
        },
        "first_slot_start": (
            first_slot_start.isoformat() if first_slot_start is not None else None
        ),
        "last_slot_end": (
            last_slot_end.isoformat() if last_slot_end is not None else None
        ),
        "today_available": epex_day_available(data, today),
        "tomorrow_available": epex_day_available(data, today + timedelta(days=1)),
        "today_prices": today_prices,
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: EngieBeConfigEntry
) -> dict[str, Any]:
    """Return the diagnostics of a config entry."""
    if (runtime_data := getattr(entry, "runtime_data", None)) is None:
        return async_redact_data({"entry": entry.as_dict()}, TO_REDACT)
    epex = runtime_data.epex
    relations = runtime_data.relations
    return async_redact_data(
        {
            "entry": entry.as_dict(),
            "relations": {
                "last_update_success": relations.last_update_success,
                "update_interval": (
                    str(relations.update_interval)
                    if relations.update_interval is not None
                    else None
                ),
                "agreement_count": (
                    len(relations.data) if relations.data is not None else None
                ),
            },
            "households": {
                _hashed_identifier(ban): _household_diagnostics(household)
                for ban, household in runtime_data.households.items()
            },
            "epex": _epex_diagnostics(epex) if epex is not None else None,
        },
        TO_REDACT,
    )
