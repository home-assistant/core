"""DataUpdateCoordinator for the blanco integration."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from datetime import UTC, datetime, timedelta
import logging
import re
from typing import Any, Never
from zoneinfo import ZoneInfo

from blanco_smart_home_api_client import (
    BlancoApiClient,
    BlancoApiError,
    BlancoConnectionError,
    BlancoErrorType,
    BlancoLogLevel,
    BlancoTokenExpiredError,
    BlancoWaterType,
    HttpStatus,
    StatTotalItem,
    blanco_log,
)

from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMeanType as _StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import async_add_external_statistics
from homeassistant.config_entries import ConfigEntry, ConfigEntryAuthFailed
from homeassistant.const import UnitOfVolume, __version__ as HA_VERSION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_BACKFILL_DONE,
    CONF_DEV_ID,
    CONF_DEV_TYPE,
    CONF_LAST_ACTION_TS,
    CONF_LAST_DISPENSING_ML,
    CONF_TOKEN,
    CONF_TOKEN_TYPE,
    CONF_WATER_TOTALS_ML,
    DOMAIN,
)
from .definitions import BlancoDeviceType, BlancoTimeRange

_LOGGER = logging.getLogger(__name__)

# StatisticMeanType.NONE signals a sum-only statistic (no mean is computed).
# Available since HA 2025.4; the integration requires HA 2026.1+.
_METADATA_MEAN: dict[str, Any] = {"mean_type": _StatisticMeanType.NONE}

UPDATE_INTERVAL = timedelta(seconds=30)
"""Poll interval for the BLANCO device data endpoints."""

REQUEST_PAGE_SIZE = 300
"""Number of action events requested per API call (backfill pages and incremental polls)."""

_ACTIONS_504_LIMIT: int = 3
"""Consecutive HTTP 504 responses on /actions before _last_action_ts is advanced to now."""

_STATS_WATER_PARAM: dict[BlancoDeviceType, str] = {
    BlancoDeviceType.AIO: "disp_wtr_amt",
    BlancoDeviceType.SODA: "disp_wtr_amt",
    BlancoDeviceType.AQUA: "wtr_flow",
}
"""Maps device types that support /stats water aggregation to their API parameter name."""

# HA statistic_id regex: ^(?!.+__)(?!_)[\da-z_]+(?<!_):(?!_)[\da-z_]+(?<!_)$
# Rules: only [a-z0-9_], no leading/trailing underscore, no double underscore.
_STAT_ID_NON_ALNUM = re.compile(r"[^a-z0-9]+")  # matches any non-alphanumeric run
_STAT_ID_MULTI_US = re.compile(r"_+")  # collapses consecutive underscores


def _actions_error(status: HttpStatus, context: str = "") -> Never:
    """Raise BlancoConnectionError for a failed /actions response.

    Called instead of raising directly so that no ``raise`` statement
    appears in the body of the surrounding ``try`` block (TRY301).
    """
    suffix = f" {context}" if context else ""
    raise BlancoConnectionError(f"Actions endpoint returned HTTP {status}{suffix}")


def _stat_id_part(value: str) -> str:
    """Return *value* as a valid statistic_id segment ([a-z0-9_], no leading/trailing underscores).

    Non-alphanumeric characters (including existing underscores that are part
    of a run with invalid chars) are replaced by a single underscore; the
    result is then stripped of any leading/trailing underscores.  Falls back
    to "device" when the sanitised string is empty.
    """
    # Replace every run of non-alphanumeric characters with one underscore,
    # then collapse any remaining consecutive underscores.
    sanitized = _STAT_ID_NON_ALNUM.sub("_", value.lower())
    sanitized = _STAT_ID_MULTI_US.sub("_", sanitized)
    sanitized = sanitized.strip("_")
    return sanitized or "device"


def _compute_stats_ranges(now_utc: datetime, tz_name: str) -> list[dict[str, Any]]:
    """Return four time-range dicts (today / week / month / year) for the /stats endpoint.

    All period boundaries are computed in the local timezone given by *tz_name* and
    converted to UTC millisecond timestamps.  The UTC offset (in whole hours) is
    included in each range descriptor as required by the API.
    """
    local_now = now_utc.astimezone(ZoneInfo(tz_name))
    utc_offset_td = local_now.utcoffset()
    utc_offset: float = (
        utc_offset_td.total_seconds() / 3600 if utc_offset_td is not None else 0.0
    )

    # Midnight of the current local day.
    today_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    # ISO Monday of the current local week.
    week_start = today_start - timedelta(days=local_now.weekday())
    # First day of the current local month.
    month_start = today_start.replace(day=1)
    # First day of the current local year.
    year_start = today_start.replace(month=1, day=1)

    def _to_ms(dt: datetime) -> int:
        """Convert a timezone-aware datetime to a UTC millisecond timestamp."""
        return int(dt.timestamp() * 1000)

    now_ms = _to_ms(now_utc)
    return [
        {
            "from": _to_ms(today_start),
            "to": now_ms,
            "utc_offset": utc_offset,
            "lod": int(BlancoTimeRange.DAY),
            "iso_week": True,
        },
        {
            "from": _to_ms(week_start),
            "to": now_ms,
            "utc_offset": utc_offset,
            "lod": int(BlancoTimeRange.WEEK),
            "iso_week": True,
        },
        {
            "from": _to_ms(month_start),
            "to": now_ms,
            "utc_offset": utc_offset,
            "lod": int(BlancoTimeRange.MONTH),
            "iso_week": True,
        },
        {
            "from": _to_ms(year_start),
            "to": now_ms,
            "utc_offset": utc_offset,
            "lod": int(BlancoTimeRange.YEAR),
            "iso_week": True,
        },
    ]


def _extract_stat_water_l(total: list[StatTotalItem], param: str) -> float | None:
    """Return the aggregated value in litres for *param* from a /stats total list.

    Finds the first entry where ``par == param`` and ``val`` is numeric (int or float).
    Returns ``val / 1000`` (mL → L).  Returns ``None`` when *param* is not found or
    when ``val`` is a list (distribution result rather than a scalar total).
    """
    for item in total:
        if item.get("par") == param:
            val = item.get("val")
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                return val / 1000.0
            return None
    return None


class BlancoDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator that polls the BLANCO device system and status endpoints."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        token: str,
        token_type: str,
        dev_id: str,
        dev_type: int | None,
        serial: str,
        app_id: str,
        app_version: str = "",
        app_build: str = "",
    ) -> None:
        """Initialise the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="blanco",
            update_interval=UPDATE_INTERVAL,
        )
        self._entry = entry
        self.dev_id = dev_id
        self.serial = serial
        try:
            self.dev_type = BlancoDeviceType(dev_type) if dev_type is not None else None
        except ValueError:
            self.dev_type = BlancoDeviceType.UNDEF

        session = async_get_clientsession(hass)
        self._api = BlancoApiClient(
            session,
            app_id=app_id,
            token=token,
            token_type=token_type,
            app_version=app_version,
            app_build=app_build,
            os_version=HA_VERSION,
        )

        # Highest evt_ts (ms) seen so far — loaded from entry.data so that
        # polling resumes from the correct position after an HA restart.
        self._last_action_ts: int = entry.data.get(CONF_LAST_ACTION_TS, 0)
        # Dispensed amount (mL) of the most recently seen action event —
        # persisted so the sensor retains its value across restarts.
        self._last_dispensing_ml: int | None = entry.data.get(CONF_LAST_DISPENSING_ML)
        # Running water totals in mL per tap-state key and overall ("all").
        # Defaults are merged with any persisted values so that new keys added
        # in future versions start at 0 while existing totals are preserved.
        _defaults: dict[str, int] = {
            "all": 0,
            "still": 0,
            "medium": 0,
            "classic": 0,
            "hot": 0,
        }
        self._water_totals_ml: dict[str, int] = {
            **_defaults,
            **entry.data.get(CONF_WATER_TOTALS_ML, {}),
        }
        # Counter of consecutive HTTP 504 responses from the /actions endpoint.
        self._actions_504_count: int = 0

    @property
    def last_action_ts(self) -> int:
        """Return the highest event timestamp (ms) processed so far."""
        return self._last_action_ts

    @property
    def last_dispensing_ml(self) -> int | None:
        """Return the dispensed amount (mL) of the most recent action event."""
        return self._last_dispensing_ml

    @property
    def water_totals_ml(self) -> dict[str, int]:
        """Return a snapshot of the running per-tap-state water totals in mL."""
        return dict(self._water_totals_ml)

    def _update_water_totals(
        self, actions: list[dict[str, Any]]
    ) -> dict[str, list[StatisticData]]:
        """Add newly seen action events to the running per-type water totals.

        Events are sorted by evt_ts ascending and processed one by one.
        _last_action_ts is advanced after each individual event so that
        deduplication state is always consistent with the events actually
        processed. Events whose evt_ts is not strictly greater than
        _last_action_ts are skipped to prevent double-counting across polls.

        Returns a dict mapping each tap-state key (and "all") to a list of
        StatisticData points carrying the cumulative sum in litres at the
        exact evt_ts of each event, ready for import into the HA recorder.
        """
        new_events = sorted(
            (a for a in actions if (a.get("evt_ts") or 0) > self._last_action_ts),
            key=lambda a: a.get("evt_ts") or 0,
        )
        # Per-hour buckets: stat_key → {hour_start → latest cumulative sum in L}.
        # HA statistics require timestamps at the top of the hour, so each event
        # is bucketed into its containing hour.  When multiple events fall in the
        # same hour the last (highest) cumulative value wins, because new_events
        # is sorted ascending and we always overwrite with a larger sum.
        hourly: dict[str, dict[datetime, float]] = {}
        for action in new_events:
            ts: int | None = action.get("evt_ts")
            amt: int = action.get("disp_wtr_amt") or 0
            tap: BlancoWaterType = action.get("tap_state", BlancoWaterType.UNDEF)
            self._water_totals_ml["all"] += amt
            key = tap.name.lower() if isinstance(tap, BlancoWaterType) else "undef"
            if key in self._water_totals_ml:
                self._water_totals_ml[key] += amt
            if ts is not None:
                self._last_action_ts = ts
                # Track the most recent dispensed amount for the sensor.
                if action.get("disp_wtr_amt") is not None:
                    self._last_dispensing_ml = action["disp_wtr_amt"]
                hour_start = datetime.fromtimestamp(ts / 1000, tz=UTC).replace(
                    minute=0, second=0, microsecond=0
                )
                hourly.setdefault("all", {})[hour_start] = round(
                    self._water_totals_ml["all"] / 1000, 1
                )
                if key in self._water_totals_ml and key != "undef":
                    hourly.setdefault(key, {})[hour_start] = round(
                        self._water_totals_ml[key] / 1000, 1
                    )
        # Convert per-hour dicts to sorted StatisticData lists.
        return {
            stat_key: [
                StatisticData(start=hour, sum=total)
                for hour, total in sorted(hours.items())
            ]
            for stat_key, hours in hourly.items()
        }

    async def _async_renew_token(self) -> bool:
        """Re-authenticate using the stored dev_id and update the token in entry.data.

        Returns True if the token was successfully renewed, False otherwise.
        """
        blanco_log(_LOGGER, BlancoLogLevel.INFO, "Attempting token renewal...")
        try:
            auth = await self._api.renew_token(self._entry.data[CONF_DEV_ID])
        except BlancoApiError as err:
            blanco_log(_LOGGER, BlancoLogLevel.ERROR, "Token renewal failed: %s", err)
            return False

        new_token = auth["token"]
        new_token_type = auth["token_type"]
        # Persist renewed token in entry.data.
        self.hass.config_entries.async_update_entry(
            self._entry,
            data={
                **self._entry.data,
                CONF_TOKEN: new_token,
                CONF_TOKEN_TYPE: new_token_type,
            },
        )
        # Update authorization in api client for subsequent requests.
        self._api.update_authorization(new_token, new_token_type)
        blanco_log(_LOGGER, BlancoLogLevel.INFO, "Token successfully renewed")
        return True

    async def _async_get_with_retry(
        self,
        api_method: Callable[..., Coroutine[Any, Any, Any]],
        *args: Any,
    ) -> Any:
        """Call an api client GET method; retry once after token renewal on 401.

        Raises:
            ConfigEntryAuthFailed: When a 401 is received and token renewal fails.
            BlancoConnectionError: Propagated from the api method on network failure.
        """
        try:
            return await api_method(*args)
        except BlancoTokenExpiredError:
            blanco_log(
                _LOGGER, BlancoLogLevel.WARNING, "Token expired, attempting renewal..."
            )
            if not await self._async_renew_token():
                raise ConfigEntryAuthFailed(
                    "Token renewal failed — reauthentication required"
                ) from None
            return await api_method(*args)

    def _handle_504(self, *, is_backfill: bool) -> None:
        """Update 504 counter and advance timestamp when the limit is reached.

        When ``is_backfill`` is True the backfill-done flag is also persisted so
        that the next poll enters the incremental path instead of restarting the
        full history scan.
        """
        self._actions_504_count += 1
        suffix = " during backfill" if is_backfill else ""
        blanco_log(
            _LOGGER,
            BlancoLogLevel.WARNING,
            "Actions endpoint returned 504%s (consecutive: %d/%d)",
            suffix,
            self._actions_504_count,
            _ACTIONS_504_LIMIT,
        )
        if self._actions_504_count >= _ACTIONS_504_LIMIT:
            now_ts = int(datetime.now(tz=UTC).timestamp() * 1000)
            self._last_action_ts = now_ts
            self._actions_504_count = 0
            extra: dict[str, Any] = {CONF_LAST_ACTION_TS: now_ts}
            if is_backfill:
                extra[CONF_BACKFILL_DONE] = True
            self.hass.config_entries.async_update_entry(
                self._entry,
                data={**self._entry.data, **extra},
            )
            blanco_log(
                _LOGGER,
                BlancoLogLevel.WARNING,
                "504 limit reached — advancing _last_action_ts to %d ms%s",
                now_ts,
                ", marking backfill as done" if is_backfill else "",
            )

    async def _async_backfill_actions(self) -> dict[str, Any]:
        """Paginate through all historical action events and return the raw payload.

        Raises BlancoConnectionError if any page request fails.
        """
        blanco_log(_LOGGER, BlancoLogLevel.INFO, "Starting historical actions backfill")
        all_actions: list[dict[str, Any]] = []
        fetch_from = 0
        actions_info: dict[str, Any] = {}
        while True:
            status, page_result = await self._async_get_with_retry(
                self._api.get_device_actions,
                self.dev_id,
                fetch_from,
                REQUEST_PAGE_SIZE,
                True,
            )
            if status == HttpStatus.GATEWAY_TIMEOUT:
                self._handle_504(is_backfill=True)
                _actions_error(status, "during backfill")
            if status != HttpStatus.OK:
                _actions_error(status, "during backfill")
            actions_info = page_result.get("info", {})
            page = page_result["actions"]
            if not page:
                break
            all_actions.extend(page)
            if len(page) < REQUEST_PAGE_SIZE:
                break  # last page reached
            fetch_from = max((a.get("evt_ts") or 0) for a in page) + 1
        blanco_log(
            _LOGGER,
            BlancoLogLevel.INFO,
            "Backfill complete: %d events fetched",
            len(all_actions),
        )
        # Persist the backfill flag so this loop only runs once.
        self.hass.config_entries.async_update_entry(
            self._entry,
            data={**self._entry.data, CONF_BACKFILL_DONE: True},
        )
        return {"actions": all_actions, "info": actions_info}

    async def _async_incremental_actions(self) -> dict[str, Any]:
        """Fetch action events since the last seen timestamp.

        Raises BlancoConnectionError if the request fails.
        """
        from_ts = self._last_action_ts + 1 if self._last_action_ts > 0 else 0
        status, inc_result = await self._async_get_with_retry(
            self._api.get_device_actions,
            self.dev_id,
            from_ts,
            REQUEST_PAGE_SIZE,
            True,
        )
        if status == HttpStatus.GATEWAY_TIMEOUT:
            self._handle_504(is_backfill=False)
            _actions_error(status)
        if status != HttpStatus.OK:
            _actions_error(status)
        return dict(inc_result)

    async def _async_fetch_actions(self, prev: dict[str, Any]) -> dict[str, Any]:
        """Fetch, process, and persist action events; return the actions payload.

        On any BlancoConnectionError the previous totals are returned so that
        consumption sensors retain their last value.
        """
        try:
            if not self._entry.data.get(CONF_BACKFILL_DONE):
                actions_data = await self._async_backfill_actions()
            else:
                actions_data = await self._async_incremental_actions()

            # Reset the 504 counter on any successful /actions response.
            self._actions_504_count = 0
            prev_action_ts = self._last_action_ts
            stat_points = self._update_water_totals(actions_data["actions"])
            actions_data["totals"] = {
                k: round(v / 1000, 1) for k, v in self._water_totals_ml.items()
            }
            # Expose the last dispensed amount in mL so the sensor retains its
            # value across polls that return no new events.
            actions_data["totals"]["last"] = self._last_dispensing_ml
            # Persist running state to entry.data so it survives HA restarts.
            # Only write when new events were processed to avoid unnecessary I/O.
            if self._last_action_ts != prev_action_ts:
                self.hass.config_entries.async_update_entry(
                    self._entry,
                    data={
                        **self._entry.data,
                        CONF_LAST_ACTION_TS: self._last_action_ts,
                        CONF_WATER_TOTALS_ML: dict(self._water_totals_ml),
                        CONF_LAST_DISPENSING_ML: self._last_dispensing_ml,
                    },
                )
            # Import each dispensing event as a statistics data point.
            if stat_points and "recorder" in self.hass.config.components:
                safe_serial = _stat_id_part(self.serial)
                for stat_key, data_points in stat_points.items():
                    statistic_id = f"{DOMAIN}:{safe_serial}_water_{stat_key}"
                    metadata: StatisticMetaData = {  # type: ignore[typeddict-unknown-key]
                        **_METADATA_MEAN,
                        "has_sum": True,
                        "name": f"BLANCO Water {stat_key.capitalize()}",
                        "source": DOMAIN,
                        "statistic_id": statistic_id,
                        "unit_class": "volume",
                        "unit_of_measurement": UnitOfVolume.LITERS,
                    }
                    async_add_external_statistics(self.hass, metadata, data_points)

        except BlancoConnectionError as err:
            blanco_log(
                _LOGGER,
                BlancoLogLevel.WARNING,
                "GET /actions → %s, using previous data",
                err,
            )
            # Re-use previous totals so consumption sensors keep their last value.
            prev_actions = prev.get("actions", {})
            actions_data = {
                "actions": [],
                "info": prev_actions.get("info", {}),
                "totals": prev_actions.get(
                    "totals",
                    {k: round(v / 1000, 1) for k, v in self._water_totals_ml.items()},
                ),
            }
            actions_data["totals"]["last"] = self._last_dispensing_ml

        return actions_data

    async def _async_fetch_stats(self, water_param: str) -> dict[str, Any]:
        """Fetch /stats water totals for today/week/month/year.

        Returns a dict with a ``totals`` key; values default to None on error.
        """
        stats_data: dict[str, Any] = {
            "totals": {"today": None, "week": None, "month": None, "year": None},
        }
        try:
            ranges = _compute_stats_ranges(
                datetime.now(tz=UTC), self.hass.config.time_zone
            )
            status, stats_result = await self._async_get_with_retry(
                self._api.get_device_stats, self.dev_id, ranges
            )
            if status == HttpStatus.OK:
                for key, range_result in zip(
                    ("today", "week", "month", "year"),
                    stats_result["ranges"],
                    strict=False,
                ):
                    stats_data["totals"][key] = _extract_stat_water_l(
                        range_result["total"], water_param
                    )
            else:
                blanco_log(
                    _LOGGER,
                    BlancoLogLevel.WARNING,
                    "Stats endpoint returned HTTP %s, using None values",
                    status,
                )
        except BlancoConnectionError as err:
            blanco_log(_LOGGER, BlancoLogLevel.WARNING, "POST /stats → %s", err)
        return stats_data

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch system, status, settings, errors and actions from the BLANCO API.

        Each endpoint is fetched independently.  A failure on one endpoint is
        logged as a warning and the previous coordinator data is used as a
        fallback so that the remaining sensors continue to show current values.
        """
        # Previous coordinator data used as fallback when an endpoint fails.
        prev: dict[str, Any] = self.data or {}

        # ── /system ───────────────────────────────────────────────────────────
        try:
            status, result = await self._async_get_with_retry(
                self._api.get_device_system, self.dev_id
            )
            if status == HttpStatus.OK:
                system_data: dict[str, Any] = dict(result)
            else:
                blanco_log(
                    _LOGGER,
                    BlancoLogLevel.WARNING,
                    "System endpoint returned HTTP %s, using previous data",
                    status,
                )
                system_data = prev.get("system", {"params": {}, "info": {}})
        except BlancoConnectionError as err:
            blanco_log(
                _LOGGER,
                BlancoLogLevel.WARNING,
                "GET /system → %s, using previous data",
                err,
            )
            system_data = prev.get("system", {"params": {}, "info": {}})

        # ── /status ───────────────────────────────────────────────────────────
        try:
            status, result = await self._async_get_with_retry(
                self._api.get_device_status, self.dev_id
            )
            if status == HttpStatus.OK:
                status_data: dict[str, Any] = dict(result)
            else:
                blanco_log(
                    _LOGGER,
                    BlancoLogLevel.WARNING,
                    "Status endpoint returned HTTP %s, using previous data",
                    status,
                )
                status_data = prev.get("status", {"params": {}, "info": {}})
        except BlancoConnectionError as err:
            blanco_log(
                _LOGGER,
                BlancoLogLevel.WARNING,
                "GET /status → %s, using previous data",
                err,
            )
            status_data = prev.get("status", {"params": {}, "info": {}})

        # ── /settings ─────────────────────────────────────────────────────────
        try:
            status, result = await self._async_get_with_retry(
                self._api.get_device_settings, self.dev_id
            )
            if status == HttpStatus.OK:
                settings_data: dict[str, Any] = dict(result)
            else:
                blanco_log(
                    _LOGGER,
                    BlancoLogLevel.WARNING,
                    "Settings endpoint returned HTTP %s, using previous data",
                    status,
                )
                settings_data = prev.get("settings", {"params": {}, "info": {}})
        except BlancoConnectionError as err:
            blanco_log(
                _LOGGER,
                BlancoLogLevel.WARNING,
                "GET /settings → %s, using previous data",
                err,
            )
            settings_data = prev.get("settings", {"params": {}, "info": {}})

        # ── /errors ───────────────────────────────────────────────────────────
        try:
            status, result = await self._async_get_with_retry(
                self._api.get_device_errors, self.dev_id
            )
            if status == HttpStatus.OK:
                errors_data: dict[str, Any] = dict(result)
            else:
                blanco_log(
                    _LOGGER,
                    BlancoLogLevel.WARNING,
                    "Errors endpoint returned HTTP %s, using previous data",
                    status,
                )
                errors_data = prev.get("errors", {"errors": [], "info": {}})
        except BlancoConnectionError as err:
            blanco_log(
                _LOGGER,
                BlancoLogLevel.WARNING,
                "GET /errors → %s, using previous data",
                err,
            )
            errors_data = prev.get("errors", {"errors": [], "info": {}})

        # ── /actions ──────────────────────────────────────────────────────────
        actions_data = await self._async_fetch_actions(prev)

        # ── /stats ───────────────────────────────────────────────────────────────
        water_param = (
            _STATS_WATER_PARAM.get(self.dev_type) if self.dev_type is not None else None
        )
        stats_data = (
            await self._async_fetch_stats(water_param)
            if water_param
            else {"totals": {"today": None, "week": None, "month": None, "year": None}}
        )

        # ── repair issues ─────────────────────────────────────────────────────
        # Create a HA repair issue when the device reports active errors.
        active_errors = [
            e
            for e in errors_data.get("errors", [])
            if e.get("err_type") in (BlancoErrorType.CRITICAL, BlancoErrorType.WARNING)
        ]
        repair_issue_id = f"device_error_{self.dev_id}"
        device_name = system_data.get("params", {}).get("dev_name") or self._entry.title
        if active_errors:
            async_create_issue(
                self.hass,
                DOMAIN,
                repair_issue_id,
                is_fixable=False,
                severity=IssueSeverity.WARNING,
                translation_key="device_error",
                translation_placeholders={
                    "device_name": device_name,
                    "error_count": str(len(active_errors)),
                },
            )
        else:
            async_delete_issue(self.hass, DOMAIN, repair_issue_id)

        # ── dev_type discovery ────────────────────────────────────────────────
        # If the device type is not yet known, try to read it from any info block.
        if self.dev_type is None:
            for candidate_data in (
                system_data,
                status_data,
                settings_data,
                errors_data,
            ):
                raw = candidate_data.get("info", {}).get("dev_type")
                if raw is not None:
                    try:
                        self.dev_type = BlancoDeviceType(raw)
                    except ValueError:
                        self.dev_type = BlancoDeviceType.UNDEF
                    self.hass.config_entries.async_update_entry(
                        self._entry,
                        data={**self._entry.data, CONF_DEV_TYPE: raw},
                    )
                    blanco_log(
                        _LOGGER,
                        BlancoLogLevel.INFO,
                        "dev_type discovered from API response: %s (%s)",
                        raw,
                        self.dev_type,
                    )
                    break

        return {
            "system": system_data,
            "status": status_data,
            "settings": settings_data,
            "errors": errors_data,
            "actions": actions_data,
            "stats": stats_data,
        }
