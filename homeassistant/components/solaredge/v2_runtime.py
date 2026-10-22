"""Quota-bounded Basic V2 monitoring with durable shared reservations."""

from datetime import datetime, timedelta
from typing import Any, override
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiosolaredge.monitoring import BasicMonitoring, period_start
from aiosolaredge.v2 import (
    AuthenticationError,
    InvalidResponseError,
    PermissionDeniedError,
    RateLimitError,
    Reading,
    SolarEdgeV2Error,
)

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    OAuth2TokenRequestConnectionError,
    OAuth2TokenRequestError,
    OAuth2TokenRequestReauthError,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import CONF_SITE_ID, LOGGER
from .types import SolarEdgeConfigEntry
from .v2_budget import get_budget, retry_deadline

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
        # Reuse it rather than spending an eleventh rolling-minute reservation.
        state["metadata"] = metadata
        state["due"]["metadata"] = (dt_util.utcnow() + HOUR * 168).timestamp()
        await store.async_save(state)


class SolarEdgeV2Coordinator(DataUpdateCoordinator[dict[str, Reading]]):
    """Power 2h, totals/counters 4h, lifetime daily, inventory/site weekly."""

    def __init__(
        self, hass: HomeAssistant, entry: SolarEdgeConfigEntry, oauth: OAuth2Session
    ) -> None:
        """Initialize durable cache and account-wide HA budget."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name="SolarEdge Basic V2",
            update_interval=HOUR,
        )
        self.entry_id = entry.entry_id
        self.site_id = entry.data[CONF_SITE_ID]
        self.oauth = oauth
        self.budget = get_budget(hass)
        self.api = BasicMonitoring(
            async_get_clientsession(hass), self._access_token, self.budget.reserve
        )
        self.store: Store[dict[str, Any]] = Store(
            hass, 1, f"solaredge.v2.{entry.entry_id}"
        )
        self.state: dict = {
            "calls": [],
            "next_poll": 0,
            "failures": 0,
            "readings": {},
            "failed": False,
            "due": {},
            "periods": {},
            "metadata": entry.data.get("site_metadata", {}),
            "inventory": None,
        }

    async def _access_token(self) -> str:
        await self.oauth.async_ensure_token_valid()
        return self.oauth.token["access_token"]

    @override
    async def _async_setup(self) -> None:
        if saved := await self.store.async_load():
            if "due" not in saved:
                await self.budget.import_legacy(self.entry_id, saved["calls"])
            self.state.update(saved)
            if any(
                ("_battery_" in name or name.startswith("storage_"))
                and (item["value"] is not None or name in self.state["periods"])
                for name, item in self.state["readings"].items()
            ) and not any(
                device.get("active", True)
                for device in (self.state["inventory"] or {}).get("batteries", [])
            ):
                self._invalidate_storage(dt_util.utcnow())
                await self.store.async_save(self.state)

    def _cached(self) -> dict[str, Reading]:
        now = dt_util.utcnow()
        result = {}
        zone = self.state["metadata"].get("timezone")
        active = {
            device["serialNumber"]
            for device in (self.state["inventory"] or {}).get("batteries", [])
            if device.get("active", True)
        }
        for key, item in self.state["readings"].items():
            timestamp = datetime.fromisoformat(item["timestamp"])
            value = item["value"]
            if (key.startswith("storage_") and not active) or (
                "_battery_" in key
                and not any(key.startswith(f"{serial}_battery_") for serial in active)
            ):
                value = None
            period = PERIODS.get(key, "day" if "_battery_" in key else None)
            if period and (
                not zone
                or self.state["periods"].get(key)
                != period_start(now, zone, period).isoformat()
            ):
                value = None
            if (
                timestamp > now
                or (key == "average_power" and now - timestamp > HOUR * 4)
                or (key == "lifetime_energy" and now - timestamp > HOUR * 48)
            ):
                value = None
            result[key] = Reading(value, timestamp)
        return result

    def _save_readings(self, readings: dict[str, Reading], now: datetime) -> None:
        zone = self.state["metadata"].get("timezone")
        for key, reading in readings.items():
            self.state["readings"][key] = {
                "value": reading.value,
                "timestamp": reading.timestamp.isoformat(),
            }
            period = PERIODS.get(key, "day" if "_battery_" in key else None)
            if period and zone:
                self.state["periods"][key] = period_start(now, zone, period).isoformat()

    def _invalidate_storage(self, now: datetime) -> None:
        """Drop dependent values/observation times without deleting entities."""
        names = {"storage_charge_energy", "storage_discharge_energy"}
        names.update(name for name in self.state["readings"] if "_battery_" in name)
        for name in names:
            self.state["readings"][name] = {"value": None, "timestamp": now.isoformat()}
            self.state["periods"].pop(name, None)

    async def _read_job(self, key: str, now: datetime) -> dict[str, Reading]:
        """Fetch one bounded capability group independently."""
        readings = {}
        if key == "lifetime":
            readings["lifetime_energy"] = await self.api.lifetime_energy(self.site_id)
        elif key == "power":
            readings["average_power"] = await self.api.power(self.site_id, now)
        elif key == "metadata":
            metadata = await self.api.site(self.site_id)
            if str(metadata.get("siteId")) != self.site_id:
                raise SolarEdgeV2Error("Site mismatch")
            self.state["metadata"] = safe_metadata(metadata)
        elif key == "inventory":
            inventory = await self.api.inventory(self.site_id)
            if inventory != self.state["inventory"]:
                self._invalidate_storage(now)
            self.state["inventory"] = inventory
        elif key == "storage":
            self._invalidate_storage(now)
            inventory = self.state["inventory"]
            serials = [
                device["serialNumber"]
                for device in (inventory or {}).get("batteries", [])
                if device.get("active", True)
            ]
            if not serials or not (zone := self.state["metadata"].get("timezone")):
                self._invalidate_storage(now)
            else:
                try:
                    readings = await self.api.storage_daily(
                        self.site_id, now, zone, serials
                    )
                except InvalidResponseError:
                    # Valid new membership waits for the normal inventory cadence;
                    # malformed counters also fail closed, only for storage. Neither
                    # is authorization/quota failure or grounds for extra requests.
                    self._invalidate_storage(now)
        elif zone := self.state["metadata"].get("timezone"):
            if key in ("day", "month", "year"):
                readings = await self.api.overview(self.site_id, now, zone, key)
        return readings

    @override
    async def _async_update_data(self) -> dict[str, Reading]:
        now = dt_util.utcnow()
        timestamp = now.timestamp()
        if timestamp < self.state["next_poll"]:
            if self.state["failed"] or not self.state["readings"]:
                raise UpdateFailed("SolarEdge polling paused; quota/backoff preserved")
            return self._cached()
        calls = [t for t in self.state["calls"] if t > (now - WINDOW).timestamp()]
        due = self.state["due"]
        jobs = [
            ("lifetime", 24),
            ("power", 2),
            ("metadata", 168),
            ("inventory", 168),
            ("day", 4),
            ("month", 4),
            ("year", 4),
            ("storage", 4),
        ]
        jobs = [(key, hours) for key, hours in jobs if timestamp >= due.get(key, 0)]
        self.state.pop("auth_failed_jobs", None)
        if len(calls) >= MAX_CALLS or len(calls) + len(jobs) > MAX_CALLS:
            self.state.update(
                calls=calls, failed=True, next_poll=calls[0] + WINDOW.total_seconds()
            )
            await self.store.async_save(self.state)
            raise UpdateFailed("SolarEdge local rolling credit reserve exhausted")
        # Reserve full batch/cadences before I/O; global ledger additionally counts
        # each actual request, setup validation and token refresh conservatively.
        self.state.update(
            calls=[*calls, *([timestamp] * len(jobs))],
            next_poll=(now + HOUR * 2).timestamp(),
            failed=True,
        )
        for key, hours in jobs:
            due[key] = (now + HOUR * hours).timestamp()
        await self.store.async_save(self.state)
        # Finished jobs keep their normal cadence above; only a failed or
        # unattempted job is retried, so partial batches cannot starve later jobs.
        completed: set[str] = set()

        def unfinished() -> list[str]:
            return [key for key, _ in jobs if key not in completed]

        try:
            for key, _ in jobs:
                try:
                    readings = await self._read_job(key, now)
                    self.state.setdefault("permissions", {}).pop(key, None)
                except PermissionDeniedError:
                    # An older SITE_DATA-only grant may lack DEVICE_DATA. Do not
                    # lose valid production readings or turn scope failure into reauth.
                    self.state.setdefault("permissions", {})[key] = "denied"
                    if key == "inventory":
                        self.state["inventory"] = None
                        self._invalidate_storage(now)
                    affected = {
                        "lifetime": {"lifetime_energy"},
                        "power": {"average_power"},
                    }
                    for name in list(self.state["readings"]):
                        if (
                            name in affected.get(key, set())
                            or PERIODS.get(name) == key
                            or (
                                key == "storage"
                                and ("_battery_" in name or name.startswith("storage_"))
                            )
                        ):
                            self.state["readings"][name]["value"] = None
                    completed.add(key)
                    continue
                self._save_readings(readings, now)
                completed.add(key)
                await self.store.async_save(self.state)
        except AuthenticationError, OAuth2TokenRequestReauthError:
            self.state["auth_failed_jobs"] = unfinished()
            for key in unfinished():
                due[key] = self.state["next_poll"]
            await self.store.async_save(self.state)
            raise ConfigEntryAuthFailed(
                "SolarEdge authorization must be renewed"
            ) from None
        except RateLimitError as err:
            if provider := err.http_status == 429:
                # Only an actual provider response is new account-wide evidence.
                await self.budget.pause(err)
                self.state["quota"] = err.quota
                self.state["quota_kind"] = (
                    "monthly" if err.monthly_exhausted else "throughput_or_unknown"
                )
            # A local refusal waits only for its remaining shared/local deadline,
            # measured from the refusal; it never extends or resets that deadline.
            self.state["next_poll"] = retry_deadline(
                err.retry_after,
                now if provider else dt_util.utcnow(),
                provider=provider,
            ).timestamp()
            for key in unfinished():
                due[key] = self.state["next_poll"]
            await self.store.async_save(self.state)
            raise UpdateFailed("SolarEdge quota exceeded; polling paused") from None
        except (
            SolarEdgeV2Error,
            OAuth2TokenRequestConnectionError,
            OAuth2TokenRequestError,
        ):
            self.state["failures"] += 1
            self.state["next_poll"] = (
                now + HOUR * min(24, 2 ** min(5, self.state["failures"] - 1))
            ).timestamp()
            for key in unfinished():
                due[key] = self.state["next_poll"]
            await self.store.async_save(self.state)
            raise UpdateFailed("SolarEdge read failed; polling backed off") from None
        except BaseException:
            # Cancellation or an unexpected error: keep the pre-I/O pause and
            # reservations, and retry unfinished jobs then instead of a full cadence.
            for key in unfinished():
                due[key] = self.state["next_poll"]
            self.hass.async_create_task(
                self.store.async_save(self.state), "SolarEdge V2 schedule save"
            )
            raise
        self.state.update(failures=0, failed=False)
        await self.store.async_save(self.state)
        return self._cached()
