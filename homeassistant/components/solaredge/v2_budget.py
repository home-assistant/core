"""Persistent conservative shared HA budget, including OAuth and setup calls."""

import asyncio
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
import math
from typing import Any

from aiosolaredge.v2 import RateLimitError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

WINDOW = timedelta(days=32)
MAX_CALLS = 1600


def retry_deadline(
    value: str | None, now: datetime, *, provider: bool = True
) -> datetime:
    """Fail closed for providers; local refusals retain their remaining delay."""
    minimum = timedelta(hours=1) if provider else timedelta()
    if value is not None:
        try:
            seconds = float(value)
            if math.isfinite(seconds) and seconds >= 0:
                return now + max(minimum, timedelta(seconds=seconds))
        except ValueError, OverflowError:
            try:
                deadline = parsedate_to_datetime(value)
                if deadline.utcoffset() is not None:
                    return max(now + minimum, deadline)
            except ValueError, TypeError, OverflowError:
                pass
    return now + WINDOW


class SolarEdgeBudget:
    """Serialize and persist every reservation before I/O, across all HA entries."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize shared durable storage and serialization lock."""
        self.store: Store[dict[str, Any]] = Store(
            hass, 1, "solaredge.v2.account_budget"
        )
        self.lock = asyncio.Lock()
        self.state: dict[str, Any] | None = None

    async def _load(self) -> dict[str, Any]:
        if self.state is None:
            self.state = await self.store.async_load() or {"calls": [], "blocked": 0}
        return self.state

    async def import_legacy(self, entry_id: str, calls: list[float]) -> None:
        """Carry old trial reservations forward once, rather than resetting quota."""
        async with self.lock:
            state = await self._load()
            imported = state.setdefault("imported_entries", [])
            if entry_id not in imported:
                state["calls"] = sorted([*state["calls"], *calls])
                imported.append(entry_id)
                await self.store.async_save(state)

    async def reserve(self) -> None:
        """Conservatively count tokens and failures even where provider cost is unknown."""
        async with self.lock:
            state = await self._load()
            now = dt_util.utcnow().timestamp()
            calls = [
                stamp
                for stamp in state["calls"]
                if stamp > now - WINDOW.total_seconds()
            ]
            if state["blocked"] > now:
                raise RateLimitError(str(state["blocked"] - now))
            if len(calls) >= MAX_CALLS:
                raise RateLimitError(str(calls[0] + WINDOW.total_seconds() - now))
            recent = [stamp for stamp in calls if stamp > now - 60]
            if len(recent) >= 10:
                # Exact local wait; never a provider-style one-hour deadline.
                raise RateLimitError(str(min(recent) + 60 - now))
            state["calls"] = [*calls, now]
            await self.store.async_save(state)

    async def pause(self, error: RateLimitError) -> None:
        """Only transport HTTP 429 supplies new account-wide provider evidence."""
        if error.http_status != 429:
            # reserve() refusals describe existing local limits, not a new response.
            return
        async with self.lock:
            state = await self._load()
            now = dt_util.utcnow()
            # Monthly exhaustion without a verifiable reset waits a whole window.
            deadline = retry_deadline(error.retry_after, now).timestamp()
            state["blocked"] = max(state["blocked"], deadline)
            state["quota"] = error.quota
            await self.store.async_save(state)


def get_budget(hass: HomeAssistant) -> SolarEdgeBudget:
    """Use one conservative pool even if an account has multiple application IDs."""
    if "solaredge_v2_budget" not in hass.data:
        hass.data["solaredge_v2_budget"] = SolarEdgeBudget(hass)
    return hass.data["solaredge_v2_budget"]
