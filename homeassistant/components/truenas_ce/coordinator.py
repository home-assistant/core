"""TrueNAS Controller."""

import asyncio
from collections.abc import Awaitable, Callable, Hashable
from datetime import UTC, datetime, timedelta
import logging
import re
from typing import Any, override

from aiotruenas import TrueNASState

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

# TrueNAS reporting (netdata) API method name used by get_systemstats().
_NETDATA_GRAPH = "reporting.netdata_graph"

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


def _as_str_keyed(data: dict[Hashable, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Convert a TrueNASState endpoint map's uid-typed keys to str for self.ds.

    ``TrueNASState`` types object ids as ``Hashable`` (some uids, e.g. cronjob
    ids, are ints at the API level); ``self.ds`` has always been str-keyed
    end to end here, so convert at the boundary rather than widening self.ds's
    declared type for every not-yet-migrated endpoint.
    """
    return {str(uid): values for uid, values in data.items()}


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
        # Normalized TrueNAS domain state (aiotruenas.domain.state.TrueNASState),
        # incrementally taking over the parse_api(...) normalization this
        # coordinator used to do inline. Endpoints not yet migrated still
        # compute their own self.ds[...] entries directly below.
        self.state = TrueNASState(self.api.client)

        self._systemstats_errored: dict[str, datetime] = {}
        self._systemstats_error_cooldown = timedelta(minutes=10)
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
        """Optimistically mark a task RUNNING in-memory; next poll re-syncs to TrueNAS.

        ``object_id`` is looked up as a str: callers pass the object's raw
        ``id`` field, which for migrated endpoints (e.g. rsynctask,
        replication, snapshottask, scrub) is still int-typed at the API
        level, while ``self.ds`` is str-keyed end to end (see
        ``_as_str_keyed``) -- the original ``object_id`` is left untouched
        for the middleware call in ``async_run_task``.
        """
        group = self.ds.get(data_path)
        uid = str(object_id)
        if isinstance(group, dict) and isinstance(group.get(uid), dict):
            group[uid]["state"] = "RUNNING"
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
        """Check for pending updates via the aiotruenas domain layer.

        ``TrueNASState.get_update()`` returns a standalone flat map (its
        "no update pending" resting state already matches this coordinator's
        prior defaults: ``update_state="IDLE"``, ``update_version=
        "up-to-date"``); merged into ``system_info`` here so the update
        sensors' data paths are unchanged. Falls back to the current running
        version, matching the previous local default, when no update is
        pending and ``system_info`` already has one.
        """
        update = await self.state.get_update()
        if update["update_version"] == "up-to-date" and self.ds["system_info"].get(
            "version"
        ):
            update = {**update, "update_version": self.ds["system_info"]["version"]}
        self.ds["system_info"].update(update)
        if update["update_available"]:
            _LOGGER.debug("TrueNAS Update found: %s", update["update_version"])

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
        """Query services via the aiotruenas domain layer."""
        self.ds["service"] = _as_str_keyed(await self.state.get_service())

    async def get_pool(self) -> None:
        """Refresh pool state via the aiotruenas domain layer.

        ``TrueNASState.get_pool()`` refreshes and derives pool capacity from
        its own, internally-fetched dataset snapshot (including the
        boot-pool merge and per-pool error aggregation this coordinator used
        to do inline), so this no longer reads/writes ``self.ds["dataset"]``
        -- that key remains exclusively owned by ``get_dataset()`` below,
        which is gated by the "datasets" monitored group independently of
        pool monitoring.
        """
        self.ds["pool"] = _as_str_keyed(await self.state.get_pool())

    async def get_dataset(self) -> None:
        """Query datasets via the aiotruenas domain layer."""
        if not self._is_group_monitored(MONITOR_GROUP_DATASETS):
            self.ds["dataset"] = {}
            return
        self.ds["dataset"] = _as_str_keyed(await self.state.get_dataset())

    async def get_disk(self) -> None:
        """Get disks via the aiotruenas domain layer.

        Includes netdata/API-fallback temperature enrichment.
        """
        self.ds["disk"] = _as_str_keyed(await self.state.get_disk())

    async def get_vm(self) -> None:
        """Query VMs via the aiotruenas domain layer."""
        if not self._is_group_monitored(MONITOR_GROUP_VMS):
            self.ds["vm"] = {}
            return
        self.ds["vm"] = _as_str_keyed(await self.state.get_vm())

    async def get_container(self) -> None:
        """Get container instances via the aiotruenas domain layer.

        ``TrueNASState.get_container()`` dispatches internally between
        ``container.query`` (TrueNAS 26.0+) and ``virt.instance.query``
        (legacy, filtered to CONTAINER-type instances -- VM-type instances
        go via ``get_vm()``) based on its own version detection.
        """
        if not self._is_group_monitored(MONITOR_GROUP_CONTAINERS):
            self.ds["container"] = {}
            return
        self.ds["container"] = _as_str_keyed(await self.state.get_container())

    async def get_directoryservices(self) -> None:
        """Get Directory Services (AD/LDAP/IPA) status via the domain layer.

        Gating on whether the group is monitored stays here (an HA
        options-flow concern); ``TrueNASState.get_directoryservices()``
        always queries and normalizes, returning an empty map when no
        directory service is configured/enabled.
        """
        if not self._is_group_monitored(MONITOR_GROUP_DIRECTORY_SERVICES):
            self.ds["directoryservices"] = {}
            return
        self.ds["directoryservices"] = _as_str_keyed(
            await self.state.get_directoryservices()
        )

    async def get_alerts(self) -> None:
        """Query and aggregate alerts via the aiotruenas domain layer."""
        self.ds["alerts"] = await self.state.get_alerts()

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
        """Get ZFS ARC hit ratio via the aiotruenas domain layer."""
        self.ds["arc"] = await self.state.get_arc()

    async def get_smb(self) -> None:
        """Get active SMB connections via the aiotruenas domain layer.

        ``TrueNASState.get_smb()`` returns a standalone ``{"connections": N}``
        map; merged into ``system_info`` here so the ``smb_connections``
        sensor's data path is unchanged.
        """
        smb = await self.state.get_smb()
        if "connections" in smb:
            self.ds["system_info"]["smb_connections"] = smb["connections"]

    async def get_ups(self) -> None:
        """Get UPS readings via the aiotruenas domain layer, if a UPS is present."""
        if not self._is_group_monitored(MONITOR_GROUP_UPS):
            self.ds["ups"] = {}
            return
        self.ds["ups"] = await self.state.get_ups()

    async def get_cloudsync(self) -> None:
        """Query cloudsync tasks via the aiotruenas domain layer."""
        if not self._is_group_monitored(MONITOR_GROUP_CLOUDSYNC):
            self.ds["cloudsync"] = {}
            return
        self.ds["cloudsync"] = _as_str_keyed(await self.state.get_cloudsync())

    async def get_replication(self) -> None:
        """Query replication tasks via the aiotruenas domain layer."""
        if not self._is_group_monitored(MONITOR_GROUP_REPLICATION):
            self.ds["replication"] = {}
            return
        self.ds["replication"] = _as_str_keyed(await self.state.get_replication())

    async def get_rsync(self) -> None:
        """Query rsync tasks via the aiotruenas domain layer."""
        if not self._is_group_monitored(MONITOR_GROUP_RSYNC):
            self.ds["rsynctask"] = {}
            return
        self.ds["rsynctask"] = _as_str_keyed(await self.state.get_rsync())

    async def get_snapshottask(self) -> None:
        """Get snapshot tasks via the aiotruenas domain layer."""
        if not self._is_group_monitored(MONITOR_GROUP_SNAPSHOTS):
            self.ds["snapshottask"] = {}
            return
        self.ds["snapshottask"] = _as_str_keyed(await self.state.get_snapshottask())

    async def get_scrub(self) -> None:
        """Get pool scrub tasks via the aiotruenas domain layer."""
        self.ds["scrub"] = _as_str_keyed(await self.state.get_scrub())

    _APP_UPDATE_JOB_FIELDS = ("update_jobid",)
    _APP_UPDATE_JOB_DEFAULTS: dict[str, Any] = {"update_jobid": 0}

    async def get_app(self) -> None:
        """Query apps via the aiotruenas domain layer, then track update jobs.

        Update-job tracking (``update_jobid``) is not part of the domain
        layer's normalization -- ``TrueNASState`` returns its own
        internally-cached dict on every call, which never carries this
        field, so an in-progress job's tracking state is carried forward by
        hand from the previous ``self.ds["app"]`` snapshot instead of being
        lost (reset to "no job running") on every poll.
        """
        previous = self.ds["app"]
        self.ds["app"] = _as_str_keyed(await self.state.get_app())
        for uid, vals in self.ds["app"].items():
            carried = previous.get(uid, {})
            for field in self._APP_UPDATE_JOB_FIELDS:
                vals[field] = carried.get(field, self._APP_UPDATE_JOB_DEFAULTS[field])

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
        """Get cronjobs via the aiotruenas domain layer.

        ``TrueNASState.get_cronjob()`` already derives ``display_name``; the
        "skip disabled" filter stays here since it is an HA options-flow
        behavior, not TrueNAS normalization.
        """
        if not self._is_group_monitored(MONITOR_GROUP_CRONJOBS):
            self.ds["cronjob"] = {}
            return
        cronjobs = _as_str_keyed(await self.state.get_cronjob())

        behaviors = self.config_entry.options.get(CONF_BEHAVIORS)
        if behaviors is not None:
            skip_disabled = BEHAVIOR_SKIP_DISABLED_CRONJOBS in behaviors
        else:
            skip_disabled = self.config_entry.options.get(
                "cronjob_skip_disabled",
                self.config_entry.data.get("cronjob_skip_disabled", True),
            )

        self.ds["cronjob"] = {
            uid: vals
            for uid, vals in cronjobs.items()
            if not skip_disabled or vals.get("enabled", True)
        }
