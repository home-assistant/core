"""Basic V2 cadence constants and stored-state helpers shared by the V2 flow."""

from datetime import timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

HOUR = timedelta(hours=1)
WINDOW = timedelta(days=32)
MAX_CALLS = 1500
PERIODS = {
    "energy_today": "day",
    "energy_this_month": "month",
    "energy_this_year": "year",
    "production_energy": "day",
    "purchased_energy": "day",
    "consumption_energy": "day",
    "selfconsumption_energy": "day",
    "feedin_energy": "day",
    "storage_charge_energy": "day",
    "storage_discharge_energy": "day",
}


def safe_metadata(data: dict) -> dict:
    """Allowlist metadata; never persist owner contacts, location or notes."""
    result = {
        key: data[key]
        for key in (
            "siteId",
            "name",
            "peakPower",
            "activationStatus",
            "installationDate",
            "lastUpdateTime",
        )
        if key in data
    }
    zone = (
        data.get("location", {}).get("timezone")
        if isinstance(data.get("location"), dict)
        else None
    )
    if isinstance(zone, str):
        try:
            ZoneInfo(zone)
        except ValueError, ZoneInfoNotFoundError:
            pass
        else:
            result["timezone"] = zone
    return result


async def async_repair_authorization(
    hass: HomeAssistant, entry_id: str, metadata: dict
) -> None:
    """Make only an explicitly repaired auth-failed batch eligible again.

    Never touch shared reservations/provider pauses or unrelated outage schedules.
    """
    store: Store[dict[str, Any]] = Store(hass, 1, f"solaredge.v2.{entry_id}")
    if (state := await store.async_load()) and (
        jobs := state.pop("auth_failed_jobs", None)
    ):
        state.update(next_poll=0, failed=False)
        for key in jobs:
            state["due"][key] = 0
        # The successful native flow just performed this budgeted site request.
        # Reuse it rather than spending an eleventh rolling-minute reservation;
        # it is current evidence, so an earlier metadata denial no longer applies.
        state["metadata"] = metadata
        state.get("permissions", {}).pop("metadata", None)
        state["due"]["metadata"] = (dt_util.utcnow() + HOUR * 168).timestamp()
        await store.async_save(state)
