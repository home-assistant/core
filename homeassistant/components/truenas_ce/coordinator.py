"""TrueNAS Controller."""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
import logging
import re
from typing import Any, TypeGuard, override

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_NAME, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import TrueNASAPI, _summarize_payload
from .apiparser import ApiValueSpec, parse_api
from .const import (
    BEHAVIOR_SKIP_DISABLED_CRONJOBS,
    CONF_BEHAVIORS,
    CONF_MONITORED_GROUPS,
    CONF_POLL_INTERVAL,
    DEFAULT_MONITORED_GROUPS,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    ERR_INVALID_KEY,
    KILOBITS_TO_KIBIBYTES_FACTOR,
    LINK_STATE_UP,
    MONITOR_GROUP_CLOUDSYNC,
    MONITOR_GROUP_CONTAINERS,
    MONITOR_GROUP_CRONJOBS,
    MONITOR_GROUP_DATASETS,
    MONITOR_GROUP_DIRECTORY_SERVICES,
    MONITOR_GROUP_REPLICATION,
    MONITOR_GROUP_RSYNC,
    MONITOR_GROUP_SNAPSHOTS,
    MONITOR_GROUP_UPS,
    MONITOR_GROUP_VMS,
    UPTIME_EPOCH_TOLERANCE_SECONDS,
)

_LOGGER = logging.getLogger(__name__)

# TrueNAS reporting (netdata) API method names.
_NETDATA_GRAPH = "reporting.netdata_graph"
_NETDATA_GRAPHS = "reporting.netdata_graphs"

# Shared by pool.query and boot.get_state (same top-level shape).
_POOL_VALS: list[ApiValueSpec] = [
    {"name": "guid", "default": 0},
    {"name": "id", "default": 0},
    {"name": "name", "default": "unknown"},
    {"name": "path", "default": "unknown"},
    {"name": "status", "default": "unknown"},
    {"name": "healthy", "type": "bool", "default": False},
    {"name": "is_decrypted", "type": "bool", "default": False},
    {"name": "size", "default": 0},
    {"name": "allocated", "default": 0},
    {"name": "free", "default": 0},
    {"name": "fragmentation", "default": 0},
    {
        "name": "autotrim",
        "source": "autotrim/parsed",
        "type": "bool",
        "default": False,
    },
    {
        "name": "scan_function",
        "source": "scan/function",
        "default": "unknown",
    },
    {"name": "scrub_state", "source": "scan/state", "default": "unknown"},
    {
        "name": "scrub_start",
        "source": "scan/start_time/$date",
        "default": 0,
        "convert": "utc_from_timestamp",
    },
    {
        "name": "scrub_end",
        "source": "scan/end_time/$date",
        "default": 0,
        "convert": "utc_from_timestamp",
    },
    {
        "name": "scrub_secs_left",
        "source": "scan/total_secs_left",
        "default": 0,
    },
]
_POOL_ENSURE_VALS: list[ApiValueSpec] = [
    {"name": "available", "default": 0.0},
    {"name": "total", "default": 0.0},
    {"name": "usage", "default": 0.0},
    {"name": "errors", "default": 0},
    {"name": "read_errors", "default": 0},
    {"name": "write_errors", "default": 0},
    {"name": "checksum_errors", "default": 0},
]

# Job-progress fields shared by the cloudsync, replication and rsync queries.
_JOB_PROGRESS_VALS: list[ApiValueSpec] = [
    {
        "name": "time_started",
        "source": "job/time_started/$date",
        "default": 0,
        "convert": "utc_from_timestamp",
    },
    {
        "name": "time_finished",
        "source": "job/time_finished/$date",
        "default": 0,
        "convert": "utc_from_timestamp",
    },
    {"name": "job_percent", "source": "job/progress/percent", "default": 0},
    {
        "name": "job_description",
        "source": "job/progress/description",
        "default": "unknown",
    },
]

# Replication overrides "state" with its own state/state field (see get_replication).
_JOB_STATUS_VALS: list[ApiValueSpec] = [
    {"name": "state", "source": "job/state", "default": "unknown"},
    *_JOB_PROGRESS_VALS,
]

# Certificate expiry monitoring (certificate.query).
_CERTIFICATE_VALS: list[ApiValueSpec] = [
    {"name": "id", "default": 0},
    {"name": "name", "default": "unknown"},
    {"name": "cert_type", "default": "unknown"},
    {"name": "common", "default": ""},
    {
        "name": "until",
        "default": None,
        "convert": "human_date_to_utc",
    },
    {"name": "expired", "type": "bool", "default": False},
    {"name": "renew_days", "default": 0},
]


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


def _median(values: list[float]) -> float:
    """Return the median of a non-empty list of numbers."""
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    mid = n // 2
    if n % 2 == 1:
        return sorted_vals[mid]
    return (sorted_vals[mid - 1] + sorted_vals[mid]) / 2


def _as_int(value: Any) -> int:
    """Return value as an int, or 0 if it is not an integer."""
    return value if isinstance(value, int) else 0


def _to_int(value: Any, default: int = 0) -> int:
    """Parse value into an int (also from strings like "48"), else default."""
    try:
        return int(value)
    except (TypeError, ValueError):  # fmt: skip
        return default


def _accumulate_vdev_errors(vdev: Any, totals: dict[str, int]) -> None:
    """Recursively accumulate leaf-device error counts (skips parents to avoid double-counting)."""
    if not isinstance(vdev, dict):
        return

    children = vdev.get("children")
    if isinstance(children, list) and children:
        for child in children:
            _accumulate_vdev_errors(child, totals)
        return

    stats = vdev.get("stats")
    if isinstance(stats, dict):
        totals["read"] += _as_int(stats.get("read_errors"))
        totals["write"] += _as_int(stats.get("write_errors"))
        totals["checksum"] += _as_int(stats.get("checksum_errors"))


def _aggregate_topology_errors(topology: Any) -> tuple[int, int, int]:
    """Sum read/write/checksum errors across all leaf vdevs of a pool topology."""
    totals = {"read": 0, "write": 0, "checksum": 0}
    if not isinstance(topology, dict):
        return 0, 0, 0

    # Categories: data, log, cache, spare, special, dedup.
    for category in topology.values():
        if isinstance(category, list):
            for vdev in category:
                _accumulate_vdev_errors(vdev, totals)

    return totals["read"], totals["write"], totals["checksum"]


# Maps the netdata graph name (reporting.netdata_graphs) to the ds["arc"] field.
_ARC_GRAPHS = {
    "demanddatahitpercentage": "data_hit_percent",
    "demandmetadatahitpercentage": "metadata_hit_percent",
    "l2architpercentage": "l2_hit_percent",
}

# Maps the netdata graph name (reporting.netdata_graphs) to the ds["ups"] field.
_UPS_GRAPHS = {
    "upscharge": "battery_charge",
    "upsruntime": "runtime_seconds",
    "upsload": "load",
    "upsvoltage": "voltage",
    "upscurrent": "current",
    "upsfrequency": "frequency",
    "upstemperature": "temperature",
}


def _netdata_mean_value(graph_data: Any) -> float | None:
    """Extract mean value from a netdata graph response, or None if malformed."""
    if not isinstance(graph_data, list) or not graph_data:
        return None

    item = graph_data[0]
    if not isinstance(item, dict):
        return None

    mean = item.get("aggregations", {}).get("mean", {})
    if not isinstance(mean, dict):
        return None

    values = [v for v in mean.values() if isinstance(v, (int, float))]
    return round(sum(values) / len(values), 2) if values else None


def _arc_value(graph_data: Any) -> float | None:
    """Return the mean value of a single-metric ARC netdata graph, if present."""
    return _netdata_mean_value(graph_data)


def _ups_value(graph_data: Any) -> float | None:
    """Return the mean value of a single-metric UPS netdata graph, if present."""
    return _netdata_mean_value(graph_data)


def _first_ipv4(aliases: Any) -> str:
    """Return the first IPv4 address from a virt instance alias list, else 'unknown'."""
    if isinstance(aliases, list):
        for alias in aliases:
            if isinstance(alias, dict) and alias.get("type") == "INET":
                addr = alias.get("address")
                if isinstance(addr, str) and addr:
                    return addr
    return "unknown"


# Typed alias: a TrueNAS config entry carries its coordinator as runtime_data.
type TrueNASConfigEntry = ConfigEntry[TrueNASCoordinator]


def get_truenas_coordinator(
    config_entry: ConfigEntry[Any] | None,
) -> TrueNASCoordinator | None:
    """Return the coordinator stored as ``runtime_data``, or ``None`` if unset."""
    return getattr(config_entry, "runtime_data", None)


def _unwrap_app_stats_message(msg: dict[str, Any]) -> dict[str, Any] | None:
    """Unwrap collection_update envelope; return inner params/fields dict or None."""
    params = msg.get("params")
    if (
        msg.get("method") == "collection_update"
        and isinstance(params, dict)
        and isinstance(params.get("fields"), list)
    ):
        return params
    return msg if isinstance(msg.get("fields"), list) else None


class TrueNASCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """TrueNASCoordinator Class."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize TrueNASCoordinator."""
        self.hass = hass
        self.config_entry: ConfigEntry = config_entry

        poll = int(config_entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL))
        super().__init__(
            self.hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=poll),
        )

        self.name = config_entry.data[CONF_NAME]
        self.host = config_entry.data[CONF_HOST]
        # Set by entity.register_system_device() after the first refresh.
        self.system_device_id: str | None = None

        self.ds: dict[str, dict[str, Any]] = {
            "interface": {},
            "disk": {},
            "pool": {},
            "dataset": {},
            "system_info": {},
            "service": {},
            "vm": {},
            "container": {},
            "directoryservices": {},
            "cloudsync": {},
            "replication": {},
            "rsynctask": {},
            "snapshottask": {},
            "scrub": {},
            "app": {},
            "app_stats": {},
            "cronjob": {},
            "ups": {},
            "alerts": {
                "count": 0,
                "messages": [],
                "critical": 0,
                "warning": 0,
                "info": 0,
                "disk_issues": False,
            },
        }

        self.api = TrueNASAPI(
            config_entry.data[CONF_HOST],
            config_entry.data[CONF_API_KEY],
            config_entry.data[CONF_VERIFY_SSL],
        )

        self._systemstats_errored: dict[str, datetime] = {}
        self._systemstats_error_cooldown = timedelta(minutes=10)
        self._disk_temp_graph: str | None = None
        self._ups_graphs: set[str] | None = None
        self.datasets_hass_device_id = None
        self.last_updatecheck_update = datetime(1970, 1, 1, tzinfo=UTC)

        self._is_virtual = False
        self._version_major: int = 0
        self._version_minor: int = 0
        self._unknown_system_stat_names: set[str] = set()

        self._app_stats_event_name: str | None = None
        self._app_stats_sub_id: str | None = None

    def connected(self) -> bool:
        """Return connected state."""
        return self.api.connected()

    def _is_group_monitored(self, group: str) -> bool:
        """Return True when the given sensor group is enabled in options."""
        config_entry = getattr(self, "config_entry", None)
        if config_entry is None:
            return True
        monitored = getattr(config_entry, "options", {}).get(
            CONF_MONITORED_GROUPS, DEFAULT_MONITORED_GROUPS
        )
        return group in monitored

    def set_optimistic_running(self, data_path: str, object_id: Any) -> None:
        """Optimistically mark a task RUNNING in-memory; next poll re-syncs to TrueNAS."""
        group = self.ds.get(data_path)
        if isinstance(group, dict) and isinstance(group.get(object_id), dict):
            group[object_id]["state"] = "RUNNING"
            self.async_update_listeners()
        else:
            _LOGGER.debug(
                "set_optimistic_running: no '%s' object with id %r to mark RUNNING",
                data_path,
                object_id,
            )

    async def async_run_task(self, method: str, object_id: Any, data_path: str) -> None:
        """Trigger a task's run method, then optimistically mark it RUNNING.

        Raises:
            HomeAssistantError: if ``api.error`` is set. ``query()`` swallows
                errors and returns None, so the return value alone can't
                distinguish a failure from a normal null response.
        """
        await self.api.query(method, [object_id])
        if self.api.error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="run_task_failed",
                translation_placeholders={
                    "host": self.host,
                    "error": str(self.api.error),
                },
            )
        self.set_optimistic_running(data_path, object_id)

    async def _async_ensure_connected(self) -> None:
        """Connect if needed, raising the appropriate coordinator error on failure."""
        if self.api.connected():
            return

        try:
            connected = await self.api.connect()
        except Exception as e:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="connection_error",
                translation_placeholders={"host": self.host, "error": str(e)},
            ) from e

        if not connected:
            if self.api.error == ERR_INVALID_KEY:
                # Bronze scope has no reauth flow (quality_scale.yaml); degrade
                # to UpdateFailed instead of ConfigEntryAuthFailed.
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="invalid_api_key",
                    translation_placeholders={"host": self.host},
                )
            _LOGGER.error("TrueNAS connection failed (error code: %s)", self.api.error)
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="connection_error",
                translation_placeholders={
                    "host": self.host,
                    "error": str(self.api.error),
                },
            )

    @override
    async def _async_update_data(self) -> dict[str, Any]:
        """Update TrueNAS data."""

        await self._async_ensure_connected()

        # This Bronze-scope PR ships sensor entities only; get_service/get_vm/
        # get_container/get_cronjob poll data no entity here consumes yet, so
        # they're left out until the platforms exposing them follow up.
        jobs = [
            self.get_systemstats,
            self.get_disk,
            self.get_dataset,
            self.get_directoryservices,
            self.get_cloudsync,
            self.get_replication,
            self.get_rsync,
            self.get_snapshottask,
            self.get_scrub,
            self.get_app,
            self.get_app_stats,
            self.get_alerts,
            self.get_certificates,
            self.get_arc,
            self.get_smb,
            self.get_ups,
        ]

        if self.api.connected():

            async def _run_job(job: Callable[[], Awaitable[None]]) -> None:
                try:
                    await job()
                except Exception:
                    _LOGGER.exception(
                        "Error running TrueNAS job %s", getattr(job, "__name__", job)
                    )

            # Must run before the concurrent jobs: get_systemstats reads
            # ds["interface"]/_is_virtual, which this populates.
            await _run_job(self.get_systeminfo)

            # Fail fast so setup retries instead of crashing in
            # register_system_device(), which indexes "hostname" right after.
            if "hostname" not in self.ds["system_info"]:
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="system_info_unavailable",
                    translation_placeholders={"host": self.host},
                )

            await asyncio.gather(*(_run_job(job) for job in jobs))

            # get_pool relies on dataset data, so run it after gather completes
            if self.api.connected():
                await _run_job(self.get_pool)

        now = dt_util.utcnow().replace(microsecond=0)
        delta = now - self.last_updatecheck_update
        if self.api.connected() and delta.total_seconds() > 60 * 60 * 12:
            await self.get_updatecheck()
            self.last_updatecheck_update = now

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
                    {"name": "smb_connections", "default": 0},
                ],
            )
        else:
            _LOGGER.debug(
                "Skipping system_info update due to invalid/empty API response: %r",
                raw_system_info,
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
        await self._query_interfaces()

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
        self.ds["interface"] = parse_api(
            data=self.ds["interface"],
            source=await self.api.query("interface.query"),
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

    async def get_updatecheck(self) -> None:
        """Check for updates using the new 25.10/26.04 API structure."""
        update_data = await self.api.query("update.status")

        # Initialize default values to prevent invalid entity IDs
        self.ds.setdefault("system_info", {})
        self.ds["system_info"].setdefault("update_available", False)
        self.ds["system_info"].setdefault("update_state", "IDLE")
        if "update_version" not in self.ds["system_info"] or self.ds["system_info"][
            "update_version"
        ] in [None, "unknown", ""]:
            self.ds["system_info"]["update_version"] = self.ds["system_info"].get(
                "version", "up-to-date"
            )

        if not isinstance(update_data, dict):
            _LOGGER.warning(
                "TrueNAS update status returned malformed data: %s",
                update_data,
            )
            self._reset_update_status(status="IDLE")
            return

        if not update_data:
            self._reset_update_status()
            return

        status_obj = update_data.get("status")

        if isinstance(status_obj, dict):
            raw_status = status_obj.get("state") or status_obj.get("status")
            if isinstance(raw_status, str):
                self.ds["system_info"]["update_state"] = raw_status

        new_version_obj = (
            status_obj.get("new_version") if isinstance(status_obj, dict) else None
        )

        if isinstance(new_version_obj, dict) and new_version_obj.get("version"):
            self._updatecheck_process_new_version(new_version_obj)
        else:
            self._reset_update_status()

    def _updatecheck_process_new_version(self, new_version_obj: dict[str, Any]) -> None:
        """Process new version data for updatecheck."""
        self.ds["system_info"]["update_version"] = new_version_obj["version"]
        self.ds["system_info"]["update_available"] = True

        manifest = new_version_obj.get("manifest", {})
        self.ds["system_info"]["update_date"] = manifest.get("date")
        self.ds["system_info"]["update_profile"] = manifest.get("profile")
        self.ds["system_info"]["update_train"] = manifest.get("train")
        self.ds["system_info"]["update_filename"] = manifest.get("filename")

        _LOGGER.debug("TrueNAS Update found: %s", new_version_obj["version"])

    def _reset_update_status(self, status: str | None = None) -> None:
        """Reset update status to idle/up-to-date."""
        self.ds["system_info"]["update_available"] = False
        if status is not None:
            self.ds["system_info"]["update_state"] = status
        self.ds["system_info"]["update_version"] = self.ds["system_info"].get(
            "version", "up-to-date"
        )
        self.ds["system_info"]["update_date"] = None
        self.ds["system_info"]["update_profile"] = None
        self.ds["system_info"]["update_train"] = None
        self.ds["system_info"]["update_filename"] = None

    async def get_systemstats(self) -> None:
        """Get system statistics."""
        report_epoch = int(dt_util.utcnow().replace(microsecond=0).timestamp())
        graph_names = self._select_stat_graph_names()
        if not graph_names:
            return

        # Window matches the poll interval (min 5s) so RX/TX reflect current traffic.
        poll = int(
            self.config_entry.options.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)
        )
        window = max(poll, 5)
        graph_query = {
            "start": report_epoch - window - 2,
            "end": report_epoch - 2,
            "aggregate": True,
        }
        tmp_graph = await self._fetch_stat_graphs(graph_names, graph_query)
        if not tmp_graph:
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
        """Query each stat graph, returning combined data and tracking failures."""
        reporting_path = _NETDATA_GRAPH
        tmp_graph: list[Any] = []
        failed_graphs: list[str] = []

        for graph_name in graph_names:
            graph_data = await self.api.query(
                reporting_path,
                params=[graph_name, graph_query],
            )
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
        info = self.ds["system_info"]
        for tmp_load in arr:
            if t == "cpu":
                info[f"cpu_{tmp_load}"] = 0.0
            else:
                info[tmp_load] = 0.0

    async def get_service(self) -> None:
        """Get service info from TrueNAS."""
        service_names = {
            "afp": "AFP",
            "cifs": "SMB",
            "dynamicdns": "Dynamic DNS",
            "ftp": "FTP",
            "iscsitarget": "iSCSI",
            "lldp": "LLDP",
            "nfs": "NFS",
            "openvpn_client": "OpenVPN Client",
            "openvpn_server": "OpenVPN Server",
            "rsync": "Rsync",
            "s3": "S3",
            "snmp": "SNMP",
            "ssh": "SSH",
            "tftp": "TFTP",
            "ups": "UPS",
            "webdav": "WebDAV",
        }

        self.ds["service"] = parse_api(
            data=self.ds["service"],
            source=await self.api.query("service.query"),
            key="id",
            vals=[
                {"name": "id", "default": 0},
                {"name": "service", "default": "unknown"},
                {"name": "name", "default": ""},
                {"name": "enable", "type": "bool", "default": False},
                {"name": "state", "default": "unknown"},
            ],
            ensure_vals=[
                {"name": "running", "type": "bool", "default": False},
                {"name": "display_name", "default": "unknown"},
            ],
        )

        for uid, vals in self.ds["service"].items():
            self.ds["service"][uid]["running"] = vals["state"] == "RUNNING"
            name = vals.get("name")
            if not name or name == "unknown":
                name = service_names.get(
                    vals.get("service"), vals.get("service", "unknown")
                )
            self.ds["service"][uid]["display_name"] = name

    async def get_pool(self) -> None:
        """Get pools from TrueNAS."""
        raw_pools = await self.api.query("pool.query")
        self.ds["pool"] = parse_api(
            data=self.ds["pool"],
            source=raw_pools,
            key="guid",
            vals=_POOL_VALS,
            ensure_vals=_POOL_ENSURE_VALS,
        )
        if not self.api.connected():
            return

        self._apply_pool_errors(raw_pools)
        await self._add_boot_pool()

        # Looked up by mountpoint (primary) or dataset id (fallback) to find
        # each pool's root dataset for capacity derivation.
        dataset_by_mountpoint: dict[str, dict[str, Any]] = {
            dataset["mountpoint"]: dataset
            for dataset in self.ds["dataset"].values()
            if isinstance(dataset.get("mountpoint"), str)
            and dataset["mountpoint"] not in ("", "unknown")
        }

        _LOGGER.debug(
            "get_pool: processing %d pool(s); dataset mountpoints=%s",
            len(self.ds["pool"]),
            sorted(dataset_by_mountpoint),
        )

        for uid, vals in self.ds["pool"].items():
            root_dataset = dataset_by_mountpoint.get(vals.get("path"))
            match_source = "mountpoint"
            if root_dataset is None:
                root_dataset = self.ds["dataset"].get(vals.get("name"))
                match_source = "name" if root_dataset is not None else "pool-fallback"

            _LOGGER.debug(
                "get_pool: pool=%s path=%s match=%s "
                "dataset(available=%s, used=%s) pool(free=%s, size=%s, allocated=%s)",
                vals.get("name"),
                vals.get("path"),
                match_source,
                root_dataset.get("available") if root_dataset else None,
                root_dataset.get("used") if root_dataset else None,
                vals.get("free"),
                vals.get("size"),
                vals.get("allocated"),
            )

            self._apply_pool_capacity(uid, vals, root_dataset)

            # pool.query reports fragmentation as a percentage string (e.g. "48").
            self.ds["pool"][uid]["fragmentation"] = _to_int(vals.get("fragmentation"))

    async def _add_boot_pool(self) -> None:
        """Add the boot-pool to the pool data (not included in ``pool.query``)."""
        raw_boot = await self.api.query("boot.get_state")
        if not isinstance(raw_boot, dict) or not raw_boot:
            return

        # boot.get_state carries no guid/id; use the pool name as a stable key.
        raw_boot.setdefault("guid", raw_boot.get("name", "boot-pool"))
        raw_boot.setdefault("id", raw_boot.get("name", "boot-pool"))
        self.ds["pool"] = parse_api(
            data=self.ds["pool"],
            source=raw_boot,
            key="guid",
            vals=_POOL_VALS,
            ensure_vals=_POOL_ENSURE_VALS,
            prune=False,
        )
        self._apply_pool_errors([raw_boot])

    def _apply_pool_capacity(
        self, uid: str, vals: dict[str, Any], root_dataset: dict[str, Any] | None
    ) -> None:
        """Set available/total/usage for a pool from its root dataset, if any.

        Prefers the root dataset's figures (matches the TrueNAS UI, including
        for raidz parity layouts); falls back to the pool's own free/size.
        """
        if root_dataset:
            available = root_dataset.get("available") or 0
            used = root_dataset.get("used") or 0
            total = available + used
            self.ds["pool"][uid]["size"] = total
            self.ds["pool"][uid]["allocated"] = used
        else:
            available = vals.get("free") or 0
            total = vals.get("size") or (
                (vals.get("allocated") or 0) + (vals.get("free") or 0)
            )

        self.ds["pool"][uid]["available"] = available
        self.ds["pool"][uid]["total"] = total
        self.ds["pool"][uid]["usage"] = (
            round((total - available) / total * 100) if total > 0 else 0
        )

        _LOGGER.debug(
            "get_pool: pool uid=%s -> available=%s total=%s usage=%s%%",
            uid,
            available,
            total,
            self.ds["pool"][uid]["usage"],
        )

    def _apply_pool_errors(self, raw_pools: Any) -> None:
        """Aggregate read/write/checksum errors from each pool's topology."""
        if not isinstance(raw_pools, list):
            return

        for raw_pool in raw_pools:
            if not isinstance(raw_pool, dict):
                continue
            uid = raw_pool.get("guid")
            if uid not in self.ds["pool"]:
                continue

            read, write, checksum = _aggregate_topology_errors(raw_pool.get("topology"))
            pool = self.ds["pool"][uid]
            pool["read_errors"] = read
            pool["write_errors"] = write
            pool["checksum_errors"] = checksum
            pool["errors"] = read + write + checksum

            if pool["errors"]:
                _LOGGER.debug(
                    "get_pool: pool=%s errors read=%s write=%s checksum=%s",
                    raw_pool.get("name"),
                    read,
                    write,
                    checksum,
                )

    async def get_dataset(self) -> None:
        """Get datasets from TrueNAS."""
        if not self._is_group_monitored(MONITOR_GROUP_DATASETS):
            self.ds["dataset"] = {}
            return
        self.ds["dataset"] = parse_api(
            data={},
            source=await self.api.query("pool.dataset.query"),
            key="id",
            vals=[
                {"name": "id", "default": "unknown"},
                {"name": "type", "default": "unknown"},
                {"name": "name", "default": "unknown"},
                {"name": "pool", "default": "unknown"},
                {"name": "mountpoint", "default": "unknown"},
                {"name": "comments", "source": "comments/parsed", "default": ""},
                {
                    "name": "deduplication",
                    "source": "deduplication/parsed",
                    "type": "bool",
                    "default": False,
                },
                {
                    "name": "atime",
                    "source": "atime/parsed",
                    "type": "bool",
                    "default": False,
                },
                {
                    "name": "casesensitivity",
                    "source": "casesensitivity/parsed",
                    "default": "unknown",
                },
                {"name": "checksum", "source": "checksum/parsed", "default": "unknown"},
                {
                    "name": "exec",
                    "source": "exec/parsed",
                    "type": "bool",
                    "default": False,
                },
                {"name": "sync", "source": "sync/parsed", "default": "unknown"},
                {
                    "name": "compression",
                    "source": "compression/parsed",
                    "default": "unknown",
                },
                {
                    "name": "compressratio",
                    "source": "compressratio/parsed",
                    "default": "unknown",
                },
                {"name": "quota", "source": "quota/parsed", "default": "unknown"},
                {"name": "copies", "source": "copies/parsed", "default": 0},
                {
                    "name": "readonly",
                    "source": "readonly/parsed",
                    "type": "bool",
                    "default": False,
                },
                {"name": "recordsize", "source": "recordsize/parsed", "default": 0},
                {
                    "name": "encryption_algorithm",
                    "source": "encryption_algorithm/parsed",
                    "default": "unknown",
                },
                {
                    "name": "encryption_key_format",
                    "source": "key_format/parsed",
                    "default": "unknown",
                },
                {"name": "encrypted", "type": "bool", "default": False},
                {"name": "locked", "type": "bool", "default": False},
                {"name": "used", "source": "used/parsed", "default": 0},
                {"name": "available", "source": "available/parsed", "default": 0},
            ],
        )

        if len(self.ds["dataset"]) == 0:
            return

    async def get_disk(self) -> None:
        """Get disks from TrueNAS."""
        self.ds["disk"] = parse_api(
            data=self.ds["disk"],
            source=await self.api.query("disk.query"),
            key="identifier",
            vals=[
                {"name": "name", "default": "unknown"},
                {"name": "devname", "default": "unknown"},
                {"name": "serial", "default": "unknown"},
                {"name": "size", "default": "unknown"},
                {"name": "hddstandby", "default": "unknown"},
                {"name": "hddstandby_force", "type": "bool", "default": False},
                {"name": "advpowermgmt", "default": "unknown"},
                {"name": "acousticlevel", "default": "unknown"},
                {"name": "model", "default": "unknown"},
                {"name": "rotationrate", "default": "unknown"},
                {"name": "type", "default": "unknown"},
                {"name": "zfs_guid", "default": "unknown"},
                {"name": "identifier", "default": "unknown"},
            ],
            ensure_vals=[
                {"name": "temperature", "default": None},
            ],
        )

        await self._update_disk_temperatures()

    async def _update_disk_temperatures(self) -> None:
        """Update disk temperatures from netdata and fallback to API."""
        netdata_temps = await self._disk_temps_from_netdata()

        if netdata_temps:
            disk_map = self._build_disk_name_map()
            self._apply_netdata_temps(netdata_temps, disk_map)

        if fallback_disks := [
            uid
            for uid, vals in self.ds["disk"].items()
            if vals.get("temperature") is None or netdata_temps is None
        ]:
            await self._fallback_disk_temperatures(fallback_disks, bool(netdata_temps))

    def _build_disk_name_map(self) -> dict[str, str]:
        """Build a mapping from disk name/identifier to uid."""
        disk_map: dict[str, str] = {}
        for uid, vals in self.ds["disk"].items():
            for key in (
                vals.get("identifier"),
                vals.get("devname"),
                vals.get("name"),
            ):
                if key:
                    if key not in disk_map:
                        disk_map[key] = uid
                    elif disk_map[key] != uid:
                        _LOGGER.debug(
                            "Disk mapping collision: key '%s' resolves "
                            "to both %s and %s",
                            key,
                            disk_map[key],
                            uid,
                        )
        return disk_map

    def _apply_netdata_temps(
        self, netdata_temps: dict[str, float], disk_map: dict[str, str]
    ) -> None:
        """Apply netdata temperatures to the matching disks."""
        for disk_name, temp in netdata_temps.items():
            if disk_name in disk_map:
                self.ds["disk"][disk_map[disk_name]]["temperature"] = round(temp, 2)

    async def _fallback_disk_temperatures(
        self, missing_disks: list[str], has_netdata: bool
    ) -> None:
        """Fetch fallback temperatures from API and map them to missing disks."""
        # An empty list (not a dict) returns temperatures for all disks; a
        # dict/empty mapping is rejected on TrueNAS 25.10+.
        disk_names: list[str] = []
        for uid in missing_disks:
            name = self.ds["disk"].get(uid, {}).get("name")
            if name and name != "unknown":
                disk_names.append(name)

        temps = await self.api.query(
            "disk.temperatures",
            params=[disk_names],
        )

        if self._is_valid_disk_temperature_payload(temps):
            for uid in missing_disks:
                self._map_single_disk_api_temp(uid, temps)
        elif not has_netdata:
            _LOGGER.warning(
                "Failed to update disk temperatures from API 'disk.temperatures': %s",
                temps,
            )

    def _is_valid_disk_temperature_payload(
        self, temps: Any
    ) -> TypeGuard[dict[str, Any]]:
        """Validate the shape of the disk temperature API payload."""
        return isinstance(temps, dict)

    def _map_single_disk_api_temp(self, uid: str, temps: dict[str, Any]) -> None:
        """Map a single disk's temperature from the API payload."""
        vals = self.ds["disk"][uid]
        candidate_keys: list[str] = []
        for key in ("name", "devname", "identifier"):
            value = vals.get(key)
            if isinstance(value, str) and value:
                candidate_keys.append(value)

        matched_temp = next(
            (temps[key] for key in candidate_keys if key in temps), None
        )

        if matched_temp is None:
            _LOGGER.debug(
                "No matching temperature entry in 'disk.temperatures' "
                "for disk uid=%s (candidates: %s)",
                uid,
                candidate_keys,
            )
        elif isinstance(matched_temp, (int, float)):
            self.ds["disk"][uid]["temperature"] = matched_temp
        else:
            _LOGGER.debug(
                "Invalid temperature value %r for disk uid=%s",
                matched_temp,
                uid,
            )

    async def _disk_temps_from_netdata(self) -> dict[str, float] | None:
        """Return disk temperatures from netdata graphs when available."""
        if self._disk_temp_graph is None:
            self._disk_temp_graph = await self._discover_disk_temp_graph()

        if not self._disk_temp_graph:
            return None

        report_epoch = int(dt_util.utcnow().replace(microsecond=0).timestamp())
        graph_query = {
            "start": report_epoch - 90,
            "end": report_epoch - 30,
            "aggregate": True,
        }
        graph_data = await self.api.query(
            _NETDATA_GRAPH,
            params=[self._disk_temp_graph, graph_query],
        )
        if not isinstance(graph_data, list):
            return None

        temps: dict[str, float] = {}
        for entry in graph_data:
            self._collect_disk_temp(entry, temps)

        return temps or None

    async def _discover_disk_temp_graph(self) -> str:
        """Find the netdata graph name that reports disk temperatures."""
        graphs = await self.api.query(_NETDATA_GRAPHS)
        if not isinstance(graphs, list):
            return ""

        for graph in graphs:
            name = str(graph.get("name", ""))
            title = str(graph.get("title", "")).lower()
            vertical = str(graph.get("vertical_label", "")).lower()
            if ("disk" in name or "disk" in title) and (
                "temp" in name or "temp" in title or "celsius" in vertical
            ):
                return name

        return ""

    def _collect_disk_temp(
        self, entry: dict[str, Any], temps: dict[str, float]
    ) -> None:
        """Extract a single disk's median temperature into temps."""
        identifier = entry.get("identifier")
        mean = entry.get("aggregations", {}).get("mean", {})
        if not identifier or not isinstance(mean, dict) or not mean:
            return

        # Discard readings outside sane bounds; median reduces outlier impact.
        if valid_means := [
            v
            for v in mean.values()
            if isinstance(v, (int, float)) and 0.0 <= v <= 100.0
        ]:
            temps[str(identifier)] = _median(valid_means)

    async def get_vm(self) -> None:
        """Get VMs from TrueNAS."""
        if not self._is_group_monitored(MONITOR_GROUP_VMS):
            self.ds["vm"] = {}
            return
        self.ds["vm"] = parse_api(
            data=self.ds["vm"],
            source=await self.api.query("vm.query"),
            key="id",
            vals=[
                {"name": "id", "default": 0},
                {"name": "name", "default": "unknown"},
                {"name": "type", "default": "unknown"},
                {"name": "cpu", "source": "vcpus", "default": 0},
                {"name": "memory", "default": 0},
                {"name": "autostart", "type": "bool", "default": False},
                {"name": "image", "source": "description", "default": "unknown"},
                {"name": "status", "source": "status/state", "default": "unknown"},
            ],
            ensure_vals=[
                {"name": "running", "type": "bool", "default": False},
            ],
        )

        for uid, vals in self.ds["vm"].items():
            # Only null memory is substituted with 0 (avoids a TypeError on
            # division); other invalid types should still surface.
            memory = vals.get("memory")
            if memory is None:
                memory = 0
            self.ds["vm"][uid]["memory"] = round(memory / 1024)
            self.ds["vm"][uid]["running"] = vals["status"] == "RUNNING"

    async def get_container(self) -> None:
        """Get virt CONTAINER instances (Incus) from TrueNAS; VM instances go via get_vm."""
        if not self._is_group_monitored(MONITOR_GROUP_CONTAINERS):
            self.ds["container"] = {}
            return

        instances = await self.api.query("virt.instance.query")
        if isinstance(instances, list):
            containers = [
                inst
                for inst in instances
                if isinstance(inst, dict) and inst.get("type") == "CONTAINER"
            ]
        else:
            _LOGGER.debug(
                "virt.instance.query returned %s (expected list); no containers",
                type(instances).__name__,
            )
            containers = []

        self.ds["container"] = parse_api(
            data=self.ds["container"],
            source=containers,
            key="id",
            vals=[
                {"name": "id", "default": "unknown"},
                {"name": "name", "default": "unknown"},
                {"name": "type", "default": "unknown"},
                {"name": "cpu", "default": 0},
                {"name": "memory", "default": 0},
                {"name": "autostart", "type": "bool", "default": False},
                {"name": "image", "source": "image/description", "default": "unknown"},
                {"name": "status", "default": "unknown"},
                {"name": "aliases", "default": []},
            ],
            ensure_vals=[
                {"name": "running", "type": "bool", "default": False},
                {"name": "ip_address", "default": "unknown"},
            ],
        )

        for uid, vals in self.ds["container"].items():
            # cpu is a possibly-null string (e.g. "1"); normalize to int.
            self.ds["container"][uid]["cpu"] = _to_int(vals.get("cpu"))
            # Container memory is reported in bytes and may be null; show MiB.
            memory = vals.get("memory")
            if not isinstance(memory, (int, float)):
                memory = 0
            self.ds["container"][uid]["memory"] = round(memory / 1048576)
            self.ds["container"][uid]["running"] = vals.get("status") == "RUNNING"
            self.ds["container"][uid]["ip_address"] = _first_ipv4(vals.get("aliases"))

    async def get_directoryservices(self) -> None:
        """Get Directory Services (AD/LDAP/IPA) status; only surfaced when configured+enabled."""
        if not self._is_group_monitored(MONITOR_GROUP_DIRECTORY_SERVICES):
            self.ds["directoryservices"] = {}
            return

        config = await self.api.query("directoryservices.config")
        if (
            not isinstance(config, dict)
            or not config.get("service_type")
            or not config.get("enable")
        ):
            self.ds["directoryservices"] = {}
            return

        status = await self.api.query("directoryservices.status")
        status = status if isinstance(status, dict) else {}

        # Merge config + status into one source row so parse_api can pull both.
        merged = dict(config)
        merged["status"] = status.get("status", "unknown")
        merged["status_msg"] = status.get("status_msg")

        self.ds["directoryservices"] = parse_api(
            data=self.ds["directoryservices"],
            source=[merged],
            key="id",
            vals=[
                {"name": "id", "default": 1},
                {"name": "type", "source": "service_type", "default": "unknown"},
                {"name": "enable", "type": "bool", "default": False},
                {
                    "name": "account_cache",
                    "source": "enable_account_cache",
                    "type": "bool",
                    "default": False,
                },
                {
                    "name": "dns_updates",
                    "source": "enable_dns_updates",
                    "type": "bool",
                    "default": False,
                },
                {"name": "kerberos_realm", "default": "unknown"},
                {
                    "name": "domain",
                    "source": "configuration/domain",
                    "default": "unknown",
                },
                {
                    "name": "site",
                    "source": "configuration/site",
                    "default": "unknown",
                },
                {"name": "status", "default": "unknown"},
                {"name": "status_msg", "default": None},
            ],
            ensure_vals=[
                {"name": "healthy", "type": "bool", "default": False},
            ],
        )

        for uid, vals in self.ds["directoryservices"].items():
            self.ds["directoryservices"][uid]["healthy"] = (
                vals.get("status") == "HEALTHY"
            )

    async def get_alerts(self) -> None:
        """Get alerts from TrueNAS."""
        alerts = await self.api.query("alert.list")
        if not isinstance(alerts, list):
            _LOGGER.warning(
                "Unexpected response from alert.list (expected list, got %s)",
                type(alerts).__name__,
            )
            # Keep the last known alert state instead of reporting a false
            # "no active alerts" on a permission/transport error.
            return

        active_alerts = [alert for alert in alerts if not alert.get("dismissed", False)]

        disk_issues = False
        for alert in active_alerts:
            klass = str(alert.get("klass", "")).lower()
            title = str(alert.get("title", "")).lower()
            if "disk" in klass or "pool" in klass or "smart" in title:
                disk_issues = True
                break

        self.ds["alerts"] = {
            "count": len(active_alerts),
            "messages": [
                alert.get("formatted", "Unknown alert") for alert in active_alerts
            ],
            "critical": sum(a.get("level") == "CRITICAL" for a in active_alerts),
            "warning": sum(a.get("level") == "WARNING" for a in active_alerts),
            "info": sum(a.get("level") == "INFO" for a in active_alerts),
            "disk_issues": disk_issues,
            "uuids": [a.get("uuid") for a in active_alerts if a.get("uuid")],
        }

    async def get_certificates(self) -> None:
        """Get TrueNAS certificates, keyed by ``name`` since renewal changes ``id`` (#61)."""
        certificates = await self.api.query("certificate.query")
        self.ds["certificate"] = parse_api(
            data={},
            source=certificates,
            key="name",
            vals=_CERTIFICATE_VALS,
        )
        now = dt_util.utcnow()
        for cert in self.ds["certificate"].values():
            if not isinstance(cert, dict):
                continue
            until = cert.get("until")
            cert["days_until_expiry"] = (
                max(0, (until - now).days) if isinstance(until, datetime) else None
            )

    async def get_arc(self) -> None:
        """Get ZFS ARC hit ratio from netdata graphs."""
        self.ds["arc"] = {}
        report_epoch = int(dt_util.utcnow().replace(microsecond=0).timestamp())
        graph_query = {
            "start": report_epoch - 300,
            "end": report_epoch,
            "aggregate": True,
        }

        for graph_name, field_name in _ARC_GRAPHS.items():
            graph_data = await self.api.query(
                _NETDATA_GRAPH,
                params=[graph_name, graph_query],
            )
            if graph_data is None:
                self.ds["arc"][field_name] = None
                continue

            value = _arc_value(graph_data)
            self.ds["arc"][field_name] = value

    async def get_smb(self) -> None:
        """Get active SMB connections."""
        smb_status = await self.api.query("smb.status")

        if isinstance(smb_status, list):
            self.ds["system_info"]["smb_connections"] = len(smb_status)
        elif isinstance(smb_status, dict) and "sessions" in smb_status:
            self.ds["system_info"]["smb_connections"] = len(
                smb_status.get("sessions", [])
            )
        # else: query failed/unexpected shape -- keep the last known count
        # instead of reporting a false "0 connections".

    async def get_ups(self) -> None:
        """Get UPS readings from the netdata UPS graphs, if a UPS is present."""
        if not self._is_group_monitored(MONITOR_GROUP_UPS):
            self.ds["ups"] = {}
            return
        if self._ups_graphs is None:
            discovered = await self._discover_ups_graphs()
            if discovered is None:
                return  # discovery failed; retry on the next update
            self._ups_graphs = discovered

        if not self._ups_graphs:
            return

        report_epoch = int(dt_util.utcnow().replace(microsecond=0).timestamp())
        graph_query = {
            "start": report_epoch - 90,
            "end": report_epoch - 30,
            "aggregate": True,
        }

        ups: dict[str, float] = {}
        for graph_name, field in _UPS_GRAPHS.items():
            if graph_name not in self._ups_graphs:
                continue
            graph_data = await self.api.query(
                _NETDATA_GRAPH,
                params=[graph_name, graph_query],
            )
            value = _ups_value(graph_data)
            if value is not None:
                ups[field] = value

        self.ds["ups"] = ups

    async def _discover_ups_graphs(self) -> set[str] | None:
        """Return available UPS netdata graph names, or None if the fetch failed (retried later)."""
        graphs = await self.api.query(_NETDATA_GRAPHS)
        if not isinstance(graphs, list):
            return None

        return {
            name
            for graph in graphs
            if (name := str(graph.get("name", ""))) in _UPS_GRAPHS
        }

    async def get_cloudsync(self) -> None:
        """Get cloudsync from TrueNAS."""
        if not self._is_group_monitored(MONITOR_GROUP_CLOUDSYNC):
            self.ds["cloudsync"] = {}
            return
        self.ds["cloudsync"] = parse_api(
            data=self.ds["cloudsync"],
            source=await self.api.query("cloudsync.query"),
            key="id",
            vals=[
                {"name": "id", "default": "unknown"},
                {"name": "description", "default": "unknown"},
                {"name": "direction", "default": "unknown"},
                {"name": "path", "default": "unknown"},
                {"name": "enabled", "type": "bool", "default": False},
                {"name": "transfer_mode", "default": "unknown"},
                {"name": "snapshot", "type": "bool", "default": False},
                *_JOB_STATUS_VALS,
            ],
        )

    async def get_replication(self) -> None:
        """Get replication from TrueNAS."""
        if not self._is_group_monitored(MONITOR_GROUP_REPLICATION):
            self.ds["replication"] = {}
            return
        self.ds["replication"] = parse_api(
            data=self.ds["replication"],
            source=await self.api.query("replication.query"),
            key="id",
            vals=[
                {"name": "id", "default": 0},
                {"name": "name", "default": "unknown"},
                {"name": "source_datasets", "default": "unknown"},
                {"name": "target_dataset", "default": "unknown"},
                {"name": "recursive", "type": "bool", "default": False},
                {"name": "enabled", "type": "bool", "default": False},
                {"name": "direction", "default": "unknown"},
                {"name": "transport", "default": "unknown"},
                {"name": "auto", "type": "bool", "default": False},
                {"name": "retention_policy", "default": "unknown"},
                # WebUI-shown state; the last job is often null (#34).
                {"name": "state", "source": "state/state", "default": "unknown"},
                # Fallback only; dropped below once used.
                {"name": "job_state", "source": "job/state", "default": "unknown"},
                *_JOB_PROGRESS_VALS,
            ],
        )

        for vals in self.ds["replication"].values():
            if vals.get("state", "unknown") == "unknown":
                vals["state"] = vals.get("job_state", "unknown")
            vals.pop("job_state", None)

    async def get_rsync(self) -> None:
        """Get rsync tasks from TrueNAS."""
        if not self._is_group_monitored(MONITOR_GROUP_RSYNC):
            self.ds["rsynctask"] = {}
            return
        self.ds["rsynctask"] = parse_api(
            data=self.ds["rsynctask"],
            source=await self.api.query("rsynctask.query"),
            key="id",
            vals=[
                {"name": "id", "default": 0},
                {"name": "path", "default": "unknown"},
                {"name": "desc", "default": "unknown"},
                {"name": "remotehost", "default": "unknown"},
                {"name": "remotemodule", "default": "unknown"},
                {"name": "direction", "default": "unknown"},
                {"name": "mode", "default": "unknown"},
                {"name": "enabled", "type": "bool", "default": False},
                *_JOB_STATUS_VALS,
            ],
        )

    async def get_snapshottask(self) -> None:
        """Get snapshot tasks from TrueNAS."""
        if not self._is_group_monitored(MONITOR_GROUP_SNAPSHOTS):
            self.ds["snapshottask"] = {}
            return
        self.ds["snapshottask"] = parse_api(
            data=self.ds["snapshottask"],
            source=await self.api.query("pool.snapshottask.query"),
            key="id",
            vals=[
                {"name": "id", "default": 0},
                {"name": "dataset", "default": "unknown"},
                {"name": "recursive", "type": "bool", "default": False},
                {"name": "lifetime_value", "default": 0},
                {"name": "lifetime_unit", "default": "unknown"},
                {"name": "enabled", "type": "bool", "default": False},
                {"name": "naming_schema", "default": "unknown"},
                {"name": "allow_empty", "type": "bool", "default": False},
                {"name": "vmware_sync", "type": "bool", "default": False},
                {"name": "schedule", "default": {}},
                {"name": "state", "source": "state/state", "default": "unknown"},
                {
                    "name": "datetime",
                    "source": "state/datetime/$date",
                    "default": 0,
                    "convert": "utc_from_timestamp",
                },
            ],
        )

    async def get_scrub(self) -> None:
        """Get pool scrub tasks from TrueNAS."""
        self.ds["scrub"] = parse_api(
            data=self.ds["scrub"],
            source=await self.api.query("pool.scrub.query"),
            key="id",
            vals=[
                {"name": "id", "default": None},
                {"name": "pool_name", "default": ""},
                {"name": "enabled", "type": "bool", "default": False},
            ],
        )

    async def get_app(self) -> None:
        """Get Apps from TrueNAS."""
        self.ds["app"] = parse_api(
            data=self.ds["app"],
            source=await self.api.query("app.query"),
            key="id",
            vals=[
                {"name": "id", "default": 0},
                {"name": "name", "default": "unknown"},
                {"name": "human_version", "default": "unknown"},
                {"name": "version", "default": "unknown"},
                {"name": "latest_version", "default": "unknown"},
                {"name": "custom_app", "type": "bool", "default": False},
                {
                    "name": "update_available",
                    "source": "upgrade_available",
                    "type": "bool",
                    "default": False,
                },
                {
                    "name": "image_updates_available",
                    "type": "bool",
                    "default": False,
                },
                {
                    "name": "portal",
                    "source": "portals/Web UI",
                    "default": "unknown",
                },
                {"name": "state", "default": "unknown"},
            ],
            ensure_vals=[
                {"name": "running", "type": "bool", "default": False},
            ],
        )

        for vals in self.ds["app"].values():
            vals["running"] = vals["state"] == "RUNNING"
            # image_updates_available only counts for custom apps; otherwise a
            # chart-up-to-date catalog app could show a phantom update (#31).
            vals["update_available"] = bool(vals.get("update_available")) or (
                bool(vals.get("custom_app"))
                and bool(vals.get("image_updates_available"))
            )

        await self._clear_finished_app_updates()

    async def _clear_finished_app_updates(self) -> None:
        """Reset update_jobid once an app's upgrade job is no longer running."""
        for vals in self.ds["app"].values():
            job_id = vals.get("update_jobid")
            if not job_id:
                continue

            jobs = await self.api.query("core.get_jobs", params=[[["id", "=", job_id]]])
            state = None
            if isinstance(jobs, list) and jobs and isinstance(jobs[0], dict):
                state = jobs[0].get("state")
            if state not in ("RUNNING", "WAITING"):
                vals["update_jobid"] = 0

    # Subscription lifecycle:
    #   UNSUBSCRIBED: _app_stats_sub_id is None.
    #   SUBSCRIBED:   _app_stats_sub_id and _app_stats_event_name are set together.
    #   stop_app_stats clears both, unconditionally.
    #   get_app_stats re-enters start_app_stats when is_subscribed returns False.
    def _set_app_stats_subscription(
        self, sub_id: str | None, event_name: str | None
    ) -> None:
        """Atomically set the app.stats subscription metadata."""
        self._app_stats_sub_id = sub_id
        self._app_stats_event_name = event_name

    def _clear_app_stats_subscription(self) -> None:
        """Clear the app.stats subscription metadata."""
        self._app_stats_sub_id = None
        self._app_stats_event_name = None

    def _get_app_identifier(self, app: dict[str, Any]) -> str | None:
        """Return the app identifier: ``name``, falling back to legacy ``app_name``."""
        name = app.get("name")
        if isinstance(name, str) and name:
            return name
        app_name = app.get("app_name")
        return app_name if isinstance(app_name, str) and app_name else None

    async def start_app_stats(self) -> None:
        """Initialize the app.stats subscription."""
        if not self._is_group_monitored(MONITOR_GROUP_CONTAINERS):
            _LOGGER.debug("start_app_stats: containers group not monitored, skipping")
            await self._stop_app_stats_if_active()
            self.ds["app_stats"] = {}
            return

        if not self.api.connected():
            _LOGGER.debug("start_app_stats: API not connected, skipping")
            return

        event_name = self._resolve_app_stats_event_name()
        await self._maybe_teardown_changed_app_stats_subscription(event_name)
        await self._maybe_clear_inactive_app_stats_subscription()

        if not self._app_stats_sub_id:
            _LOGGER.debug(
                "start_app_stats: no active subscription, subscribing to %s",
                event_name,
            )
            await self._subscribe_to_app_stats(event_name)
        else:
            _LOGGER.debug(
                "start_app_stats: subscription already active (%s)",
                self._app_stats_sub_id,
            )

    async def _stop_app_stats_if_active(self) -> None:
        """Stop app.stats subscription only if one is currently active."""
        if self._app_stats_sub_id:
            await self.stop_app_stats(force=True)

    def _resolve_app_stats_event_name(self) -> str:
        """Compute the app.stats event name from the current poll interval."""
        try:
            poll = int(
                getattr(self.config_entry, "options", {}).get(
                    CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL
                )
            )
        except (ValueError, TypeError):  # fmt: skip
            poll = DEFAULT_POLL_INTERVAL
        interval = max(poll, 2)
        return f'app.stats:{{"interval": {interval}}}'

    async def _maybe_teardown_changed_app_stats_subscription(
        self, event_name: str
    ) -> None:
        """Tear down the existing subscription if the event definition changed."""
        if self._app_stats_event_name and self._app_stats_event_name != event_name:
            await self.stop_app_stats(force=True)

    async def _maybe_clear_inactive_app_stats_subscription(self) -> None:
        """Clear local subscription state if the existing sub is no longer active."""
        if self._app_stats_sub_id and not await self.api.is_subscribed(
            self._app_stats_sub_id
        ):
            self._clear_app_stats_subscription()

    async def _subscribe_to_app_stats(self, event_name: str) -> None:
        """Attempt to establish a new app.stats subscription."""
        try:
            sub_id, queue = await self.api.subscribe_events(event_name)
            if sub_id and queue is not None:
                self._set_app_stats_subscription(sub_id, event_name)
                _LOGGER.debug("TrueNAS app.stats subscription established: %s", sub_id)
            else:
                _LOGGER.debug(
                    "TrueNAS app.stats subscription failed: no sub_id/queue returned"
                )
        except Exception:
            _LOGGER.exception("Failed to establish app.stats subscription")

    async def get_app_stats(self) -> None:
        """Process buffered app.stats events and update state."""
        if not self._is_group_monitored(MONITOR_GROUP_CONTAINERS):
            _LOGGER.debug(
                "get_app_stats: containers group not monitored, clearing app_stats"
            )
            if self._app_stats_sub_id:
                await self.stop_app_stats(force=True)
            self.ds["app_stats"] = {}
            return

        if not self._app_stats_sub_id or not await self.api.is_subscribed(
            self._app_stats_sub_id
        ):
            _LOGGER.debug(
                "get_app_stats: no active subscription, re-entering start_app_stats"
            )
            await self.start_app_stats()
            if not self._app_stats_sub_id:
                _LOGGER.debug(
                    "get_app_stats: subscription not established, skipping event fetch"
                )
                return

        if not self.api.connected():
            return

        if not self.ds.get("app"):
            return

        messages = await self.api.get_subscription_events(self._app_stats_sub_id)
        self._process_app_stats_messages(messages)

        current_app_names = self._collect_current_app_names()
        self._prune_stale_app_stats(current_app_names)

    def _process_app_stats_messages(self, messages: list[dict[str, Any]]) -> None:
        """Append/update app_stats entries from buffered WebSocket messages."""
        _LOGGER.debug("Processing %d app.stats messages", len(messages))
        for msg in messages:
            params = _unwrap_app_stats_message(msg)
            if params is None:
                _LOGGER.debug(
                    "Skipping app.stats message with no unwrappable fields: %s",
                    _summarize_payload(msg),
                )
                continue
            fields_list = params.get("fields", [])
            if not isinstance(fields_list, list):
                _LOGGER.debug(
                    "Skipping app.stats message with non-list fields: %s",
                    _summarize_payload(msg),
                )
                continue
            for app in fields_list:
                self._upsert_app_stats_entry(app)

    @staticmethod
    def _coerce_float(value: Any) -> float | None:
        """Defensively coerce a value to float, returning None on invalid/missing."""
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):  # fmt: skip
            return None

    def _upsert_app_stats_entry(self, app: object) -> None:
        """Validate and store one app.stats entry."""
        if not isinstance(app, dict):
            _LOGGER.debug("Skipping non-dict app.stats entry: %r", app)
            return
        app_name = self._get_app_identifier(app)
        if not isinstance(app_name, str) or not app_name:
            _LOGGER.debug(
                "Skipping app.stats entry with missing/invalid app_name: %r",
                app,
            )
            return

        blkio_raw = app.get("blkio")
        if isinstance(blkio_raw, dict):
            blkio_read = self._coerce_float(blkio_raw.get("read"))
            blkio_write = self._coerce_float(blkio_raw.get("write"))
        else:
            blkio_read = blkio_write = None

        networks = app.get("networks", [])
        if not isinstance(networks, list):
            networks = []
        else:
            networks = [
                net
                for net in networks
                if isinstance(net, dict) and bool(net.get("interface_name"))
            ]

        cpu_usage = self._coerce_float(app.get("cpu_usage"))
        memory = self._coerce_float(app.get("memory"))

        self.ds["app_stats"][str(app_name)] = {
            "app_name": app_name,
            "cpu_usage": cpu_usage,
            "memory": memory,
            "blkio_read": blkio_read,
            "blkio_write": blkio_write,
            "networks": networks,
        }

    def _collect_current_app_names(self) -> set[str]:
        """App names currently present in the app data."""
        current_app_names: set[str] = set()
        for vals in self.ds["app"].values():
            if isinstance(vals, dict):
                name = self._get_app_identifier(vals)
                if isinstance(name, str) and name:
                    current_app_names.add(name)
        return current_app_names

    def _prune_stale_app_stats(self, current_app_names: set[str]) -> None:
        """Remove cached app_stats entries whose app no longer exists."""
        if stale := [
            name for name in self.ds["app_stats"] if name not in current_app_names
        ]:
            _LOGGER.debug("Pruning stale app_stats entries: %s", stale)
            for app_name in stale:
                del self.ds["app_stats"][app_name]

    # force=True default: metadata clears on unload even if API is disconnected.
    async def stop_app_stats(self, force: bool = True) -> None:
        """Stop the app.stats subscription on unload."""
        if self._app_stats_sub_id and self.api.connected():
            try:
                await self.api.unsubscribe_events(self._app_stats_sub_id)
            except Exception as exc:  # noqa: BLE001 - unload cleanup must never raise
                _LOGGER.debug(
                    "TrueNAS failed to unsubscribe app.stats %s (%s)",
                    self._app_stats_sub_id,
                    exc,
                )
            self._app_stats_sub_id = None
            self._app_stats_event_name = None
        elif force:
            self._app_stats_sub_id = None
            self._app_stats_event_name = None

    async def get_cronjob(self) -> None:
        """Get cronjobs from TrueNAS."""
        if not self._is_group_monitored(MONITOR_GROUP_CRONJOBS):
            self.ds["cronjob"] = {}
            return
        self.ds["cronjob"] = parse_api(
            data=self.ds["cronjob"],
            source=await self.api.query("cronjob.query"),
            key="id",
            vals=[
                {"name": "id", "default": 0},
                {"name": "enabled", "type": "bool", "default": False},
                {"name": "command", "default": "unknown"},
                {"name": "description", "default": ""},
                {"name": "user", "default": "unknown"},
                {"name": "schedule", "default": {}},
                {"name": "stdout", "type": "bool", "default": False},
                {"name": "stderr", "type": "bool", "default": False},
            ],
            ensure_vals=[
                {"name": "display_name", "default": ""},
            ],
        )

        behaviors = self.config_entry.options.get(CONF_BEHAVIORS)
        if behaviors is not None:
            skip_disabled = BEHAVIOR_SKIP_DISABLED_CRONJOBS in behaviors
        else:
            skip_disabled = self.config_entry.options.get(
                "cronjob_skip_disabled",
                self.config_entry.data.get("cronjob_skip_disabled", True),
            )

        # Rebuilt (not mutated in place) to drop disabled entries while iterating.
        filtered_cronjobs: dict[str, Any] = {}
        for uid, vals in self.ds["cronjob"].items():
            if skip_disabled and not vals.get("enabled", True):
                continue

            description = (vals.get("description") or "").strip()
            command = (vals.get("command") or "").strip()
            if description:
                display_name = description
            elif command:
                display_name = command
            else:
                display_name = f"Cronjob {uid}"

            vals["display_name"] = display_name
            filtered_cronjobs[uid] = vals

        self.ds["cronjob"] = filtered_cronjobs
