"""TrueNAS Controller."""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
import hashlib
import logging
import re
from typing import Any, override

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_NAME, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import TrueNASAPI
from .apiparser import parse_api
from .const import (
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    ERR_INVALID_KEY,
    KILOBITS_TO_KIBIBYTES_FACTOR,
    LINK_STATE_UP,
    UPTIME_EPOCH_TOLERANCE_SECONDS,
)

_LOGGER = logging.getLogger(__name__)

# hass.data[DOMAIN] key for the cross-instance _connection_failing marker; see
# TrueNASCoordinator._set_connection_failing.
_DATA_CONNECTION_FAILING = "connection_failing_by_entry"


def _connection_fingerprint(config_entry: ConfigEntry) -> str:
    """Fingerprint the connection-identifying parts of config_entry.data.

    Stored alongside the persisted _connection_failing marker (see
    _seed_connection_failing) so the marker self-invalidates when the user
    reconfigures the entry to a different host/API key, instead of relying
    on the marker being explicitly cleared. That reliance would be broken:
    Home Assistant's own ConfigEntry.async_unload returns early WITHOUT
    calling this integration's async_unload_entry whenever the entry isn't
    currently ConfigEntryState.LOADED -- which is exactly the state
    (SETUP_RETRY) a reconfigure-while-unreachable happens from, so
    clear_persisted_connection_failing would never run for the one case
    this whole mechanism is meant to protect. The API key is hashed rather
    than stored so it isn't duplicated in hass.data in recoverable form.
    CONF_VERIFY_SSL is included alongside host/API key: it changes how the
    connection is actually established, so flipping it while the host stays
    unreachable should also get a fresh ERROR diagnostic rather than
    silently inheriting the previous setting's dedup state.
    """
    raw = (
        f"{config_entry.data[CONF_HOST]}|{config_entry.data[CONF_API_KEY]}"
        f"|{config_entry.data[CONF_VERIFY_SSL]}"
    )
    return hashlib.sha256(raw.encode()).hexdigest()


def _seed_connection_failing(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> str | None:
    """Read the persisted connection-failure marker for config_entry, if any.

    Returns the last-seen TrueNAS ERR_* code, so a coordinator recreated by a
    Home Assistant setup retry not only remembers *that* it was failing (see
    TrueNASCoordinator._connection_failing) but *why* (see
    TrueNASCoordinator._connection_failing_error) -- letting it re-log ERROR
    once if the failure reason changes mid-outage, instead of silently
    freezing on whatever error was first seen. Returns None both when never
    failing and when the persisted marker's fingerprint no longer matches
    config_entry's current host/API key -- see _connection_fingerprint --
    since that means the previous failure was against a different,
    now-irrelevant target. A genuine HA restart also sees None, since
    hass.data is wiped with the process.
    """
    # entry.runtime_data is instance-scoped and gets wiped on the very
    # teardown/recreate cycle this marker is meant to survive -- see the
    # docstring above.
    # pylint: disable-next=home-assistant-use-runtime-data
    by_entry = hass.data.get(DOMAIN, {}).get(_DATA_CONNECTION_FAILING, {})
    marker = by_entry.get(config_entry.entry_id)
    if marker is None or marker[0] != _connection_fingerprint(config_entry):
        return None
    return marker[1]  # type: ignore[no-any-return]


def clear_persisted_connection_failing(hass: HomeAssistant, entry_id: str) -> None:
    """Drop entry_id's persisted _connection_failing marker, if any.

    Best-effort hygiene call from async_unload_entry, for the entries it
    does run for (unloading a currently-LOADED entry): frees the marker a
    little sooner than waiting for the next successful reconnect or an HA
    restart. NOT relied upon for correctness -- see _connection_fingerprint
    for why a reconfigure away from a stuck SETUP_RETRY entry bypasses
    async_unload_entry entirely, and is instead handled by the fingerprint
    check in _seed_connection_failing.
    """
    # Same cross-instance-persistence reasoning as _seed_connection_failing.
    # pylint: disable-next=home-assistant-use-runtime-data
    hass.data.get(DOMAIN, {}).get(_DATA_CONNECTION_FAILING, {}).pop(entry_id, None)


# TrueNAS reporting (netdata) API method name used by get_systemstats().
_NETDATA_GRAPH = "reporting.netdata_graph"


def _stat_name_similar(a: str, b: str) -> bool:
    """Return True if two stat graph names look like near-misses of each other."""
    a_l, b_l = a.lower(), b.lower()
    if a_l == b_l:
        return False
    if a_l.replace("_", "") == b_l.replace("_", ""):
        return True
    if (
        a_l.startswith(b_l)
        or a_l.endswith(b_l)
        or b_l.startswith(a_l)
        or b_l.endswith(a_l)
    ):
        return True
    return abs(len(a_l) - len(b_l)) <= 2 and a_l[:3] == b_l[:3]


# Typed alias: a TrueNAS config entry carries its coordinator as runtime_data.
type TrueNASConfigEntry = ConfigEntry[TrueNASCoordinator]


def get_truenas_coordinator(
    config_entry: ConfigEntry[Any] | None,
) -> TrueNASCoordinator | None:
    """Return the coordinator stored as ``runtime_data``, or ``None`` if unset."""
    return getattr(config_entry, "runtime_data", None)


# Maps each coordinator job to the self.ds key(s) it owns, for
# is_data_path_failing(). get_systemstats is deliberately omitted: it only
# enriches fields get_systeminfo already owns, so including it would wrongly
# mark unrelated entities unavailable on a netdata-graph-only failure (see
# _record_failed_graphs for its own tracking). _query_interfaces is tracked
# under its own name (though called from inside get_systeminfo) so an
# interface-only failure doesn't also mark system_info unavailable; the
# reverse still applies "interface" to get_systeminfo, since a system.info
# failure means interface data wasn't refreshed this poll either.
_JOB_DATA_PATHS: dict[str, tuple[str, ...]] = {
    "get_systeminfo": ("system_info", "interface"),
    "_query_interfaces": ("interface",),
}


class TrueNASCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """TrueNASCoordinator Class."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize TrueNASCoordinator."""
        self.hass = hass
        self.config_entry: ConfigEntry = config_entry

        super().__init__(
            self.hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_POLL_INTERVAL),
        )

        self.name = config_entry.data[CONF_NAME]
        self.host = config_entry.data[CONF_HOST]
        # Set by entity.register_system_device() after the first refresh.
        self.system_device_id: str | None = None

        self.ds: dict[str, dict[str, Any]] = {
            "interface": {},
            "system_info": {},
        }

        self.api = TrueNASAPI(
            config_entry.data[CONF_HOST],
            config_entry.data[CONF_API_KEY],
            config_entry.data[CONF_VERIFY_SSL],
        )

        self._systemstats_errored: dict[str, datetime] = {}
        self._systemstats_error_cooldown = timedelta(minutes=10)

        # Per-job failure tracking (name -> currently failing) for
        # entity-unavailable/log-when-unavailable; see _note_job_outcome.
        self._job_failing: dict[str, bool] = {}

        # ERR_* code of the last failed _async_ensure_connected attempt,
        # deduped so a persistently unreachable host logs one ERROR instead
        # of one every poll. Seeded from hass.data (see
        # _set_connection_failing) so it survives a ConfigEntryNotReady
        # setup-retry recreating this coordinator, not just re-set to None.
        self._connection_failing_error: str | None = _seed_connection_failing(
            hass, config_entry
        )
        # Derived from the error above rather than a second seeded field: a
        # persisted failure always carries the ERR_* code that caused it, so
        # "was failing" and "has a remembered error" are the same fact.
        self._connection_failing: bool = self._connection_failing_error is not None

        self._is_virtual = False
        self._version_major: int = 0
        self._version_minor: int = 0
        self._unknown_system_stat_names: set[str] = set()

    def connected(self) -> bool:
        """Return connected state."""
        return self.api.connected()

    def _note_job_outcome(self, job_name: str, *, failed: bool) -> bool:
        """Track a job's OK<->failing transition, logging only on change.

        Returns True only on the poll where a job first starts failing (or
        on its very first run), so the caller can emit a one-off traceback;
        every repeated failure returns False and stays silent. Logs an
        info-level recovery message once the job succeeds again.
        """
        was_failing = self._job_failing.get(job_name, False)
        if failed:
            self._job_failing[job_name] = True
            return not was_failing
        if was_failing:
            _LOGGER.info(
                "TrueNAS job %s recovered; its entities are available again",
                job_name,
            )
            self._job_failing[job_name] = False
        return False

    def is_data_path_failing(self, data_path: str) -> bool:
        """Return True if any job owning this ds key is currently failing."""
        return any(
            self._job_failing.get(job_name, False)
            for job_name, data_paths in _JOB_DATA_PATHS.items()
            if data_path in data_paths
        )

    async def _async_ensure_connected(self) -> None:
        """Connect if needed, raising the appropriate coordinator error on failure.

        Deduped like _note_job_outcome: a persistently unreachable host logs
        one ERROR (or one per distinct ERR_* code) instead of one every poll,
        plus an INFO line on recovery -- see _connection_failing_error.
        """
        if self.api.connected():
            self._note_connection_recovered()
            return

        try:
            connected = await self.api.connect(quiet=self._connection_failing)
        except Exception as e:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="connection_error",
                translation_placeholders={"host": self.host, "error": str(e)},
            ) from e

        if connected:
            self._note_connection_recovered()
            return

        if self.api.error == ERR_INVALID_KEY:
            # Bronze scope has no reauth flow (quality_scale.yaml); degrade
            # to UpdateFailed instead of ConfigEntryAuthFailed.
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_api_key",
                translation_placeholders={"host": self.host},
            )
        if self._connection_failing:
            if self.api.error != self._connection_failing_error:
                # Surface a fresh ERROR when the cause changes mid-outage
                # (e.g. connection_refused -> certificate_verify_failed),
                # instead of staying pinned to DEBUG at the first code seen.
                _LOGGER.error(
                    "TrueNAS connection failure changed (error code: %s -> %s)",
                    self._connection_failing_error,
                    self.api.error,
                )
                self._set_connection_failing(True, self.api.error)
            else:
                _LOGGER.debug(
                    "TrueNAS connection still failing (error code: %s)",
                    self.api.error,
                )
        else:
            _LOGGER.error("TrueNAS connection failed (error code: %s)", self.api.error)
            self._set_connection_failing(True, self.api.error)
        raise UpdateFailed(
            translation_domain=DOMAIN,
            translation_key="connection_error",
            translation_placeholders={
                "host": self.host,
                "error": str(self.api.error),
            },
        )

    def _set_connection_failing(self, value: bool, error: str | None = None) -> None:
        """Set _connection_failing/_connection_failing_error and mirror into hass.data.

        The mirror is what lets the dedup -- and the last known ERR_* code,
        see _connection_failing_error -- survive a TrueNASCoordinator
        recreated by a Home Assistant setup retry -- see _connection_failing.
        Keyed by config_entry.entry_id so multiple TrueNAS instances don't
        share dedup state, and validated against a fingerprint of the
        current host/API key (see _connection_fingerprint) so a later
        reconfigure to a different target can't be misread as still-failing.
        Cleared entirely on recovery rather than left as a stale entry,
        keeping hass.data free of long-lived clutter for entries that never
        fail again. ``error`` is required whenever ``value`` is True -- see
        the call sites in _async_ensure_connected.
        """
        self._connection_failing = value
        self._connection_failing_error = error if value else None
        # Same cross-instance-persistence reasoning as _seed_connection_failing.
        # pylint: disable-next=home-assistant-use-runtime-data
        by_entry = self.hass.data.setdefault(DOMAIN, {}).setdefault(
            _DATA_CONNECTION_FAILING, {}
        )
        if value:
            by_entry[self.config_entry.entry_id] = (
                _connection_fingerprint(self.config_entry),
                error,
            )
        else:
            by_entry.pop(self.config_entry.entry_id, None)

    def _note_connection_recovered(self) -> None:
        """Log recovery once and clear the dedup flag; see _async_ensure_connected."""
        if self._connection_failing:
            _LOGGER.info("TrueNAS connection recovered")
            self._set_connection_failing(False)

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        """Update TrueNAS data."""

        await self._async_ensure_connected()

        # Only the system_info/interface domains are collected.
        jobs = [
            self.get_systemstats,
        ]

        if self.api.connected():

            async def _run_job(job: Callable[[], Awaitable[None]]) -> None:
                name = getattr(job, "__name__", str(job))
                try:
                    await job()
                except Exception:
                    if self._note_job_outcome(name, failed=True):
                        _LOGGER.exception(
                            "TrueNAS job %s failed; its entities will go unavailable",
                            name,
                        )
                else:
                    # Only count a clean return as success while still
                    # connected -- a job that bailed out early on a mid-job
                    # disconnect must not log a spurious "recovered" line.
                    if self.api.connected():
                        self._note_job_outcome(name, failed=False)

            # Must run before the concurrent jobs: get_systemstats reads
            # ds["interface"]/_is_virtual, which this populates.
            await _run_job(self.get_systeminfo)

            # ensure_vals only backfills "unknown" when the key is absent --
            # an explicit null/"" hostname must be rejected too.
            hostname = self.ds["system_info"].get("hostname", "unknown")
            if not isinstance(hostname, str) or not hostname or hostname == "unknown":
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="system_info_unavailable",
                    translation_placeholders={"host": self.host},
                )

            await asyncio.gather(*(_run_job(job) for job in jobs))

        if not self.api.connected():
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="disconnected",
                translation_placeholders={"host": self.host},
            )

        return self.ds

    async def get_systeminfo(self) -> None:
        """Get system info from TrueNAS."""
        raw_system_info = await self.api.query("system.info")

        if isinstance(raw_system_info, dict):
            self.ds["system_info"] = parse_api(
                data=self.ds["system_info"],
                source=raw_system_info,
                vals=[
                    {"name": "version", "default": "unknown"},
                    {"name": "hostname", "default": "unknown"},
                    {"name": "uptime_seconds", "default": 0},
                    {"name": "system_serial", "default": "unknown"},
                    {"name": "system_product", "default": "unknown"},
                    {"name": "system_manufacturer", "default": "unknown"},
                    {"name": "physmem", "default": 0},
                ],
                ensure_vals=[
                    {"name": "uptimeEpoch", "default": 0},
                    {"name": "cpu_temperature", "default": None},
                    {"name": "load_shortterm", "default": 0.0},
                    {"name": "load_midterm", "default": 0.0},
                    {"name": "load_longterm", "default": 0.0},
                    {"name": "cpu_usage", "default": 0.0},
                    {"name": "cache_size-arc_value", "default": 0.0},
                    {"name": "memory-free_value", "default": 0.0},
                    {"name": "memory-total_value", "default": 0.0},
                    {"name": "memory-usage_percent", "default": 0},
                    {"name": "update_available", "type": "bool", "default": False},
                    {"name": "update_progress", "default": 0},
                    {"name": "update_jobid", "default": 0},
                    {"name": "update_state", "default": "unknown"},
                    {"name": "update_version", "default": "unknown"},
                ],
            )
        else:
            # No usable system.info payload: signal failure so _run_job marks
            # system_info/interface entities unavailable instead of serving
            # stale data indefinitely (entity-unavailable / log-when-unavailable).
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="system_info_unavailable",
                translation_placeholders={"host": self.host},
            )

        if not self.api.connected():
            return

        # Ensure update_version is not unknown if no update is available
        if not self.ds["system_info"].get("update_available"):
            self.ds["system_info"]["update_version"] = self.ds["system_info"].get(
                "version", "unknown"
            )

        await self._handle_update_job()
        if not self.api.connected():
            return

        self._parse_version()
        self._detect_virtualization()
        self._update_uptime()

        # Tracked as its own job (not re-raised) so a lone interface.query
        # failure only marks "interface" entities unavailable instead of
        # also taking down the ten unrelated system_info entities above,
        # which are already known-fresh at this point in the same poll.
        try:
            await self._query_interfaces()
        except UpdateFailed:
            if self._note_job_outcome("_query_interfaces", failed=True):
                _LOGGER.exception(
                    "TrueNAS job %s failed; its entities will go unavailable",
                    "_query_interfaces",
                )
        else:
            self._note_job_outcome("_query_interfaces", failed=False)

    async def _handle_update_job(self) -> None:
        """Refresh progress/state for a running update job, if any."""
        if not self.ds["system_info"].get("update_jobid"):
            return

        self.ds["system_info"] = parse_api(
            data=self.ds["system_info"],
            source=await self.api.query(
                "core.get_jobs",
                params=[[["id", "=", self.ds["system_info"].get("update_jobid")]]],
            ),
            vals=[
                {
                    "name": "update_progress",
                    "source": "progress/percent",
                    "default": 0,
                },
                {
                    "name": "update_state",
                    "source": "state",
                    "default": "unknown",
                },
            ],
        )
        if not self.api.connected():
            return

        if self.ds["system_info"].get("update_state") != "RUNNING" or not self.ds[
            "system_info"
        ].get("update_available"):
            self.ds["system_info"]["update_progress"] = 0
            self.ds["system_info"]["update_jobid"] = 0
            self.ds["system_info"]["update_state"] = "unknown"

    def _parse_version(self) -> None:
        """Parse major/minor version numbers from the reported version string."""
        version_str = str(self.ds["system_info"].get("version", "") or "")
        clean_version = version_str.replace("TrueNAS-", "").replace("SCALE-", "")

        # Bounded quantifier avoids unbounded backtracking (Sonar S5852).
        if match := re.search(r"(\d{1,9})\.(\d{1,9})", clean_version):
            self._version_major = int(match[1])
            self._version_minor = int(match[2])
        elif clean_version:
            _LOGGER.debug(
                "Failed to parse TrueNAS version from string: %s", version_str
            )

    def supports_update_run(self) -> bool:
        """Return True if the "update.run" API method is available (TrueNAS 25.10+)."""
        return (self._version_major, self._version_minor) >= (25, 10)

    def _detect_virtualization(self) -> None:
        """Detect whether TrueNAS is running virtualized."""
        self._is_virtual = self.ds["system_info"].get("system_manufacturer") in [
            "QEMU",
            "VMware, Inc.",
            "Microsoft Corporation",
            "Xen",
        ] or self.ds["system_info"].get("system_product") in [
            "VirtualBox",
            "Virtual Machine",
        ]

    def _update_uptime(self) -> None:
        """Update the uptime epoch, using a tolerance to avoid sensor jitter."""
        uptime_seconds = self.ds["system_info"].get("uptime_seconds", 0)
        if uptime_seconds <= 0:
            return

        now = dt_util.utcnow().replace(microsecond=0)
        now_epoch = int(now.timestamp())
        new_uptime_epoch = now_epoch - int(uptime_seconds)

        old_uptime_epoch = self.ds["system_info"].get("uptimeEpoch", 0)
        if (
            old_uptime_epoch == 0
            or abs(new_uptime_epoch - old_uptime_epoch) > UPTIME_EPOCH_TOLERANCE_SECONDS
        ):
            self.ds["system_info"]["uptimeEpoch"] = new_uptime_epoch
        else:
            self.ds["system_info"]["uptimeEpoch"] = old_uptime_epoch

    async def _query_interfaces(self) -> None:
        """Query network interfaces from TrueNAS."""
        raw_interfaces = await self.api.query("interface.query")
        if not isinstance(raw_interfaces, list):
            if not self.api.connected():
                # Connection dropped mid-query; _async_update_data's own
                # "disconnected" error covers this poll, so don't also
                # misattribute it as an interface-specific failure. Logged at
                # DEBUG so a genuinely malformed response that happens to
                # coincide with a disconnect isn't entirely untraceable.
                _LOGGER.debug(
                    "interface.query returned %r while disconnected; skipping "
                    "interface_unavailable for this poll",
                    raw_interfaces,
                )
                return
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="interface_unavailable",
                translation_placeholders={"host": self.host},
            )
        self.ds["interface"] = parse_api(
            data=self.ds["interface"],
            source=raw_interfaces,
            key="id",
            vals=[
                {"name": "id", "default": "unknown"},
                {"name": "name", "default": "unknown"},
                {"name": "description", "default": "unknown"},
                {"name": "mtu", "default": "unknown"},
                {
                    "name": "link_state",
                    "source": "state/link_state",
                    "default": "unknown",
                },
                {
                    "name": "active_media_type",
                    "source": "state/active_media_type",
                    "default": "unknown",
                },
                {
                    "name": "active_media_subtype",
                    "source": "state/active_media_subtype",
                    "default": "unknown",
                },
                {
                    "name": "link_address",
                    "source": "state/link_address",
                    "default": "unknown",
                },
            ],
            ensure_vals=[
                {"name": "rx", "default": 0},
                {"name": "tx", "default": 0},
            ],
        )

        for interface in self.ds["interface"].values():
            interface["link_up"] = interface.get("link_state") == LINK_STATE_UP

    async def get_systemstats(self) -> None:
        """Get system statistics."""
        report_epoch = int(dt_util.utcnow().replace(microsecond=0).timestamp())
        graph_names = self._select_stat_graph_names()
        if not graph_names:
            return

        # Window matches the fixed poll interval (min 5s) so RX/TX reflect current traffic.
        window = max(DEFAULT_POLL_INTERVAL, 5)
        graph_query = {
            "start": report_epoch - window - 2,
            "end": report_epoch - 2,
            "aggregate": True,
        }
        tmp_graph = await self._fetch_stat_graphs(graph_names, graph_query)
        if not tmp_graph:
            # Every graph fetch failed; _fetch_stat_graphs already logged the
            # transition and armed the cooldown, so just keep last-known values.
            return

        for item in tmp_graph:
            if isinstance(item, dict):
                self._process_system_stat(item)

    def _select_stat_graph_names(self) -> list[str]:
        """Build the list of stat graphs to query, honoring the error cooldown."""
        graph_names = ["load", "cputemp", "cpu", "arcsize", "memory"]

        if self.ds["interface"]:
            graph_names.append("interface")

        # Possible future config option: some hypervisors do pass through CPU
        # temps, and users may want cputemp polling on VMs anyway.
        if self._is_virtual and "cputemp" in graph_names:
            graph_names.remove("cputemp")

        now = dt_util.utcnow()
        self._systemstats_errored = {
            name: ts
            for name, ts in self._systemstats_errored.items()
            if now - ts < self._systemstats_error_cooldown
        }

        return [
            graph_name
            for graph_name in graph_names
            if graph_name not in self._systemstats_errored
        ]

    async def _fetch_stat_graphs(
        self, graph_names: list[str], graph_query: dict[str, Any]
    ) -> list[Any]:
        """Query each stat graph concurrently, returning combined data and tracking failures."""
        reporting_path = _NETDATA_GRAPH
        results = await asyncio.gather(
            *(
                self.api.query(reporting_path, params=[graph_name, graph_query])
                for graph_name in graph_names
            )
        )

        tmp_graph: list[Any] = []
        failed_graphs: list[str] = []
        for graph_name, graph_data in zip(graph_names, results, strict=True):
            if isinstance(graph_data, list):
                tmp_graph.extend(graph_data)
            else:
                failed_graphs.append(graph_name)

        self._record_failed_graphs(failed_graphs)
        return tmp_graph

    def _record_failed_graphs(self, failed_graphs: list[str]) -> None:
        """Record failed graphs, logging only newly failed ones to avoid spam."""
        if not failed_graphs:
            return

        # Log only newly-failed transitions to avoid spamming every update.
        newly_failed_graphs: list[str] = []
        now = dt_util.utcnow()
        for graph_name in failed_graphs:
            if graph_name not in self._systemstats_errored:
                newly_failed_graphs.append(graph_name)
            self._systemstats_errored[graph_name] = now

        if newly_failed_graphs:
            _LOGGER.warning(
                "TrueNAS %s failed to fetch graphs: %s",
                self.host,
                newly_failed_graphs,
            )

    def _process_system_stat(self, item: dict[str, Any]) -> None:
        """Process a single system statistic item."""
        name = item.get("name")
        if not name:
            return

        if name == "cputemp":
            self._process_cputemp(item)
        elif name == "load":
            self._systemstats_process(
                ("shortterm", "midterm", "longterm"), item, "load"
            )
        elif name == "cpu":
            self._systemstats_process("cpu", item, "cpu")
            cpu_cpu = self.ds["system_info"].get("cpu_cpu", 0.0)
            self.ds["system_info"]["cpu_usage"] = round(cpu_cpu, 2)
        elif name == "interface":
            tmp_etc = item["identifier"]
            if tmp_etc in self.ds["interface"]:
                self._process_system_stat_interface(item, tmp_etc)
        elif name == "memory":
            self._process_memory_stat(item)
        elif name == "arcsize":
            # netdata exposes the ARC value under the "size" series, not "arc_size".
            self._systemstats_process("size", item, "arcsize")
        else:
            self._handle_unknown_stat(name)

    def _process_cputemp(self, item: dict[str, Any]) -> None:
        """Store the CPU temperature from a cputemp graph item."""
        mean_vals = item.get("aggregations", {}).get("mean", {})
        valid_means = [v for v in mean_vals.values() if isinstance(v, (int, float))]
        self.ds["system_info"]["cpu_temperature"] = (
            round(max(valid_means), 2) if valid_means else None
        )

    def _process_memory_stat(self, item: dict[str, Any]) -> None:
        """Store memory totals and usage percentage from a memory graph item."""
        self.ds["system_info"]["memory-total_value"] = round(
            self.ds["system_info"].get("physmem", 0)
        )

        self._systemstats_process("available", item, "memory")
        total_mem = self.ds["system_info"].get("memory-total_value", 0.0)
        free_mem = self.ds["system_info"].get("memory-free_value", 0.0)
        if total_mem > 0:
            self.ds["system_info"]["memory-usage_percent"] = round(
                100 * (float(total_mem) - float(free_mem)) / float(total_mem)
            )

    def _handle_unknown_stat(self, name: str) -> None:
        """Log an unknown stat graph name once to surface potential API changes."""
        if name in self._unknown_system_stat_names:
            return

        self._unknown_system_stat_names.add(name)
        _LOGGER.warning(
            "TrueNAS %s returned unknown system stat graph name '%s'; "
            "this may indicate a TrueNAS API change or misconfiguration",
            self.host,
            name,
        )

        known_names = {"cputemp", "load", "cpu", "interface", "memory", "arcsize"}
        if near_misses := [k for k in known_names if _stat_name_similar(name, k)]:
            _LOGGER.debug(
                "Unknown system stat graph name '%s' from TrueNAS %s "
                "is similar to known names: %s",
                name,
                self.host,
                ", ".join(sorted(near_misses)),
            )

    def _process_system_stat_interface(
        self, item: dict[str, Any], tmp_etc: str
    ) -> None:
        """Process interface system statistics."""
        tmp_arr = ("rx", "tx")
        legend = item.get("legend")
        if not isinstance(legend, list):
            for tmp_load in tmp_arr:
                self.ds["interface"][tmp_etc][tmp_load] = 0.0
            return

        item["legend"] = [
            tmp.replace("received", "rx").replace("sent", "tx")
            for tmp in legend
            if isinstance(tmp, str)
        ]

        aggregations = item.get("aggregations")
        if isinstance(aggregations, dict) and isinstance(
            aggregations.get("mean"), dict
        ):
            aggregations["mean"] = {
                k.replace("received", "rx").replace("sent", "tx"): v
                for k, v in aggregations["mean"].items()
                if isinstance(k, str)
            }

            for tmp_var in item["legend"]:
                if tmp_var in tmp_arr:
                    tmp_val = aggregations["mean"].get(tmp_var) or 0.0
                    self.ds["interface"][tmp_etc][tmp_var] = round(
                        (tmp_val * KILOBITS_TO_KIBIBYTES_FACTOR), 2
                    )

        else:
            for tmp_load in tmp_arr:
                self.ds["interface"][tmp_etc][tmp_load] = 0.0

    def _systemstats_process(
        self, arr: str | tuple[str, ...], graph: dict[str, Any], t: str
    ) -> None:
        arr = (arr,) if isinstance(arr, str) else tuple(arr)
        aggregations = graph.get("aggregations")
        legend = graph.get("legend")

        if not (isinstance(aggregations, dict) and isinstance(legend, list)):
            self._store_stat_defaults(t, arr)
            return

        mean_data = aggregations.get("mean")
        for tmp_var in legend:
            if tmp_var not in arr:
                continue
            tmp_val = (
                mean_data.get(tmp_var) if isinstance(mean_data, dict) else 0.0
            ) or 0.0
            self._store_stat_value(t, tmp_var, tmp_val)

    def _store_stat_value(self, t: str, tmp_var: str, tmp_val: float) -> None:
        """Store a single processed statistic value under the right key."""
        info = self.ds["system_info"]
        if t == "arcsize":
            info["cache_size-arc_value"] = round(tmp_val, 2)
        elif t == "cpu":
            info[f"cpu_{tmp_var}"] = round(tmp_val, 2)
        elif t == "load":
            info[f"load_{tmp_var}"] = round(tmp_val, 2)
        elif t == "memory":
            if tmp_var == "available":
                info["memory-free_value"] = round(tmp_val)
        else:
            info[tmp_var] = round(tmp_val, 2)

    def _store_stat_defaults(self, t: str, arr: tuple[str, ...]) -> None:
        """Store zeroed defaults when a statistic graph has no aggregations."""
        for tmp_var in arr:
            self._store_stat_value(t, tmp_var, 0.0)
