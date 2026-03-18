"""Standalone data fetching logic for SunSynk (no Home Assistant dependency)."""

from __future__ import annotations

from datetime import UTC, date, datetime
import logging
import time
from typing import Any

import httpx
from sunsynk_api_client import SunSynk
from sunsynk_api_client.errors import SunSynkDefaultError
from sunsynk_api_client.models import WriteInverterSettingsRequestBody

from .auth import AuthResult, async_authenticate
from .const import SunSynkApiError

# Add TRACE level (below DEBUG=10)
TRACE = 5
logging.addLevelName(TRACE, "TRACE")


def _trace(logger: logging.Logger, msg: str, *args: Any) -> None:
    if logger.isEnabledFor(TRACE):
        logger.log(TRACE, msg, *args)


_LOGGER = logging.getLogger(__name__)

# Error tracking categories matching Node-RED implementation
ERROR_CATEGORIES = ("Bearer", "Events", "Updates", "Flow", "InvList", "InvParam")


class ErrorTracker:
    """Track API errors by category."""

    def __init__(self) -> None:
        """Initialize error tracker."""
        self._errors: dict[str, dict[str, Any]] = {
            cat: {"count": 0, "payload": "", "date": ""} for cat in ERROR_CATEGORIES
        }

    def record(self, category: str, error: Exception) -> None:
        """Record an error in the given category."""
        entry = self._errors.get(category)
        if entry is None:
            return
        entry["count"] += 1
        entry["payload"] = str(error)[:16]
        entry["date"] = datetime.now().isoformat()

    def as_dict(self) -> dict[str, dict[str, Any]]:
        """Return a copy of all error data."""
        return {k: dict(v) for k, v in self._errors.items()}


# Buffer in seconds before token expiry to trigger re-authentication
_TOKEN_EXPIRY_BUFFER = 60


class TokenManager:
    """Manages caching and refreshing of SunSynk auth tokens."""

    def __init__(
        self,
        email: str,
        password: str,
        region_idx: int,
        async_client: httpx.AsyncClient | None = None,
    ) -> None:
        """Initialise the token manager."""
        _LOGGER.debug("TokenManager init: email=%s region_idx=%d", email, region_idx)
        self._email = email
        self._password = password
        self._region_idx = region_idx
        self._async_client = async_client
        self._auth_result: AuthResult | None = None
        self._token_obtained_at: float = 0

    async def async_get_token(self) -> str:
        """Return a valid access token, refreshing if necessary."""
        expired = self._is_token_expired()
        _LOGGER.debug(
            "async_get_token: auth_result_present=%s expired=%s",
            self._auth_result is not None,
            expired,
        )
        if self._auth_result is None or expired:
            _LOGGER.debug("Obtaining new SunSynk auth token")
            self._auth_result = await async_authenticate(
                self._email, self._password, self._region_idx, self._async_client
            )
            self._token_obtained_at = time.monotonic()
            _LOGGER.debug(
                "Token obtained: token_type=%s expires_in=%d",
                self._auth_result.token_type,
                self._auth_result.expires_in,
            )
            _trace(_LOGGER, "Token value: %s", self._auth_result.access_token)
        return self._auth_result.access_token

    def _is_token_expired(self) -> bool:
        """Check if the cached token has expired (with buffer)."""
        if self._auth_result is None:
            return True
        elapsed = time.monotonic() - self._token_obtained_at
        threshold = self._auth_result.expires_in - _TOKEN_EXPIRY_BUFFER
        expired = elapsed >= threshold
        _LOGGER.debug(
            "_is_token_expired: elapsed=%.1fs threshold=%.1fs expired=%s",
            elapsed,
            threshold,
            expired,
        )
        return expired


async def _async_fetch_successful(
    fetch_coro: Any,
    error_tracker: ErrorTracker | None = None,
    error_category: str | None = None,
) -> Any | None:
    """Await a fetch coroutine and return its data if successful."""
    try:
        res = await fetch_coro
    except (SunSynkDefaultError, httpx.HTTPError) as err:
        _LOGGER.debug("_async_fetch_successful: exception: %s", err)
        if error_tracker and error_category:
            error_tracker.record(error_category, err)
        return None
    _LOGGER.debug(
        "_async_fetch_successful: success=%s",
        res.success if res else None,
    )
    if res and res.success:
        _trace(_LOGGER, "_async_fetch_successful data: %s", res.data)
        return res.data
    if res and not res.success:
        _LOGGER.debug("_async_fetch_successful: non-success response: %s", res)
    return None


async def _async_fetch_inverter_data(
    client: SunSynk, sn: str, error_tracker: ErrorTracker
) -> dict[str, Any]:
    """Fetch all realtime data for a single inverter."""
    _LOGGER.debug("_async_fetch_inverter_data: sn=%s", sn)
    fetchers: list[tuple[str, Any]] = [
        ("output", client.inverter_data.get_inverter_output_async(sn=sn)),
        ("input", client.inverter_data.get_inverter_input_async(sn=sn)),
        ("battery", client.inverter_data.get_battery_realtime_async(sn=sn)),
        ("grid", client.inverter_data.get_grid_realtime_async(sn=sn)),
        ("load", client.inverter_data.get_load_realtime_async(sn=sn)),
        ("gen", client.inverter_data.get_gen_realtime_async(sn=sn)),
        ("settings", client.settings.read_inverter_settings_async(sn=sn)),
        (
            "temp",
            client.inverter_data.get_inverter_daily_output_async(
                sn=sn,
                date_=date.today(),
                column="dc_temp,igbt_temp",
            ),
        ),
    ]

    result: dict[str, Any] = {}
    for key, coro in fetchers:
        _LOGGER.debug("Fetching inverter data: sn=%s key=%s", sn, key)
        data = await _async_fetch_successful(coro, error_tracker, "InvParam")
        result[key] = data
        _trace(_LOGGER, "Inverter %s[%s]: %s", sn, key, data)

    return result


async def _async_fetch_system_data(
    client: SunSynk, error_tracker: ErrorTracker
) -> dict[str, Any]:
    """Fetch gateways, events, and notifications."""
    _LOGGER.debug("_async_fetch_system_data: start")
    data: dict[str, Any] = {
        "gateways": [],
        "events": {},
        "notifications": [],
    }

    _LOGGER.debug("Fetching gateways")
    gateways_res = await _async_fetch_successful(client.gateways.get_gateways_async())
    if gateways_res:
        data["gateways"] = gateways_res.infos
        _LOGGER.debug("Gateways found: %d", len(gateways_res.infos))
        _trace(_LOGGER, "Gateways: %s", gateways_res.infos)

    for event_type in (1, 2, 3):
        _LOGGER.debug("Fetching events: type=%d", event_type)
        try:
            events_res = await client.events.get_events_async(type_=event_type)
        except (SunSynkDefaultError, httpx.HTTPError) as err:
            _LOGGER.debug("Events type=%d fetch error: %s", event_type, err)
            error_tracker.record("Events", err)
            continue
        _LOGGER.debug(
            "Events type=%d: success=%s has_data=%s",
            event_type,
            events_res.success if events_res else None,
            bool(events_res and events_res.data) if events_res else False,
        )
        if events_res and events_res.success and events_res.data:
            data["events"][event_type] = events_res.data.record
            _trace(_LOGGER, "Events type=%d: %s", event_type, events_res.data.record)

    _LOGGER.debug("Fetching notifications")
    msgs_res = await _async_fetch_successful(
        client.notifications.get_messages_async(), error_tracker, "Events"
    )
    if msgs_res:
        data["notifications"] = msgs_res.infos
        _LOGGER.debug("Notifications found: %d", len(msgs_res.infos))
        _trace(_LOGGER, "Notifications: %s", msgs_res.infos)

    return data


async def _async_fetch_plant_data(
    client: SunSynk, plant: Any, error_tracker: ErrorTracker
) -> dict[str, Any]:
    """Fetch flow and inverter data for a single plant."""
    plant_id = str(plant.id)
    plant_name = getattr(plant, "name", plant_id)
    _LOGGER.debug("_async_fetch_plant_data: plant_id=%s name=%s", plant_id, plant_name)
    _trace(_LOGGER, "Plant object: %s", plant)

    plant_data: dict[str, Any] = {
        "info": plant,
        "flow": None,
        "inverters": {},
    }

    _LOGGER.debug("Fetching plant flow: plant_id=%s", plant_id)
    plant_data["flow"] = await _async_fetch_successful(
        client.plants.get_plant_flow_async(plant_id=plant_id),
        error_tracker,
        "Flow",
    )
    _LOGGER.debug(
        "Plant flow fetched: plant_id=%s has_flow=%s",
        plant_id,
        plant_data["flow"] is not None,
    )
    _trace(_LOGGER, "Plant flow: %s", plant_data["flow"])

    _LOGGER.debug("Fetching inverters for plant_id=%s", plant_id)
    try:
        inv_res = await client.inverters.get_plant_inverters_async(plant_id=plant_id)
    except Exception as err:
        _LOGGER.exception("Error fetching inverter list for plant %s", plant_id)
        error_tracker.record("InvList", err)
        return plant_data
    _LOGGER.debug(
        "Inverters response: plant_id=%s success=%s",
        plant_id,
        inv_res.success if inv_res else None,
    )

    if not inv_res or not inv_res.success or not inv_res.data:
        _LOGGER.debug("No inverters found for plant_id=%s", plant_id)
        return plant_data

    inverter_list = inv_res.data.infos or []
    _LOGGER.debug("Inverters found: plant_id=%s count=%d", plant_id, len(inverter_list))
    _trace(_LOGGER, "Inverter list: %s", inverter_list)

    for inv in inverter_list:
        if not inv.sn:
            _LOGGER.debug("Skipping inverter with no serial number")
            continue
        _LOGGER.debug("Processing inverter: sn=%s", inv.sn)
        try:
            inv_data = await _async_fetch_inverter_data(client, inv.sn, error_tracker)
        except Exception:
            _LOGGER.exception("Error fetching data for inverter %s", inv.sn)
            error_tracker.record("InvParam", Exception(f"inverter {inv.sn}"))
            inv_data = {}
        inv_data["info"] = inv
        _trace(_LOGGER, "Inverter %s info: %s", inv.sn, inv)
        plant_data["inverters"][inv.sn] = inv_data

    return plant_data


async def async_fetch_all_data(
    token_manager: TokenManager,
    region_idx: int,
    error_tracker: ErrorTracker | None = None,
    plant_ignore_list: set[str] | None = None,
    async_client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Fetch all data from SunSynk asynchronously."""
    _LOGGER.debug("async_fetch_all_data: region_idx=%d", region_idx)

    if error_tracker is None:
        error_tracker = ErrorTracker()

    try:
        token = await token_manager.async_get_token()
    except Exception as err:
        error_tracker.record("Bearer", err)
        raise

    async with SunSynk(
        bearer_auth=token,
        server_idx=region_idx,
        async_client=async_client,
    ) as client:
        _LOGGER.debug("SunSynk client created, fetching plants")
        plants_res = await client.plants.get_plants_async()
        _LOGGER.debug(
            "Plants response: success=%s",
            plants_res.success if plants_res else None,
        )

        if not plants_res or not plants_res.success or not plants_res.data:
            raise SunSynkApiError("Failed to fetch plants from SunSynk")

        plant_list = plants_res.data.infos or []
        _LOGGER.debug("Plants found: count=%d", len(plant_list))
        _trace(_LOGGER, "Plant list: %s", plant_list)

        data = await _async_fetch_system_data(client, error_tracker)
        data["plants"] = {}
        for plant in plant_list:
            plant_id_str = str(plant.id)
            if plant_ignore_list and plant_id_str in plant_ignore_list:
                _LOGGER.debug(
                    "Skipping ignored plant: id=%s name=%s",
                    plant.id,
                    getattr(plant, "name", "?"),
                )
                continue
            _LOGGER.debug(
                "Processing plant: id=%s name=%s", plant.id, getattr(plant, "name", "?")
            )
            data["plants"][plant.id] = await _async_fetch_plant_data(
                client, plant, error_tracker
            )

    data["errors"] = error_tracker.as_dict()
    data["last_update"] = datetime.now(tz=UTC)

    _LOGGER.debug(
        "async_fetch_all_data complete: plants=%d gateways=%d notifications=%d",
        len(plant_list),
        len(data["gateways"]),
        len(data["notifications"]),
    )
    return data


async def async_write_settings(
    token_manager: TokenManager,
    region_idx: int,
    sn: str,
    settings: dict[str, str],
    error_tracker: ErrorTracker | None = None,
    async_client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Write settings to an inverter asynchronously. Returns response dict with code/msg."""
    _LOGGER.debug("async_write_settings: sn=%s settings=%s", sn, settings)

    if error_tracker is None:
        error_tracker = ErrorTracker()

    try:
        token = await token_manager.async_get_token()
    except Exception as err:
        error_tracker.record("Bearer", err)
        raise

    async with SunSynk(
        bearer_auth=token,
        server_idx=region_idx,
        async_client=async_client,
    ) as client:
        try:
            resp = await client.settings.write_inverter_settings_async(
                sn=sn,
                body=WriteInverterSettingsRequestBody(**settings),
            )
        except Exception as err:
            _LOGGER.exception("Error writing settings for inverter %s", sn)
            error_tracker.record("Updates", err)
            raise

    code = getattr(resp, "code", None)
    msg = getattr(resp, "msg", None)
    _LOGGER.debug("async_write_settings result: code=%s msg=%s", code, msg)
    return {"code": code, "msg": msg}
