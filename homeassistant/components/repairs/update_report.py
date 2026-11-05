"""Compare the run before a Home Assistant update with the current run."""

from datetime import datetime, timedelta
from operator import itemgetter
from typing import Any, TypedDict

from awesomeversion import AwesomeVersion
import probatio

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STOP,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    __version__,
)
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DATA_UPDATE_REPORT, DOMAIN, UPDATE_REPORT_ISSUE_ID

STORAGE_KEY = "repairs.update_report"
STORAGE_VERSION = 1
# Integrations that poll a cloud service can take minutes to come up.
STARTUP_GRACE = timedelta(minutes=5)
# Fallback for runs that end without a clean stop.
SNAPSHOT_INTERVAL = timedelta(hours=6)

_UNHEALTHY_STATES = {STATE_UNAVAILABLE, STATE_UNKNOWN}


class RunSnapshot(TypedDict):
    """What a run of Home Assistant looked like."""

    version: str
    created: str
    # domain -> {entry_id: title}, only entries that were loaded
    config_entries: dict[str, dict[str, str]]
    # platform -> {registry id: entity_id}, only enabled entities
    entities: dict[str, dict[str, str]]
    # registry ids of entities without a state or unavailable/unknown
    unhealthy: list[str]
    # (domain, issue_id) of active issues that are not ignored
    issues: list[list[str]]


class StoredData(TypedDict):
    """Stored snapshots."""

    baseline: RunSnapshot | None
    last: RunSnapshot | None


class UpdateReport:
    """Keep a snapshot of every run and the baseline from before an update."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the update report."""
        self.hass = hass
        self.baseline: RunSnapshot | None = None
        self._last: RunSnapshot | None = None
        self._store: Store[StoredData] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._unsub_grace: CALLBACK_TYPE | None = None

    async def async_load(self) -> None:
        """Load the snapshots; the last run of another version is the baseline."""
        if (stored := await self._store.async_load()) is None:
            return
        self.baseline = stored["baseline"]
        self._last = stored["last"]
        if self._last is not None and self._last["version"] != __version__:
            self.baseline = self._last

    @callback
    def async_start(self) -> None:
        """Take snapshots once startup has settled."""

        @callback
        def _async_started(hass: HomeAssistant) -> None:
            self._unsub_grace = async_call_later(
                hass, STARTUP_GRACE, self._async_startup_settled
            )
            hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self._async_stop)

        async_at_started(self.hass, _async_started)

    @callback
    def _async_startup_settled(self, _now: datetime) -> None:
        self._unsub_grace = None
        self._async_save_snapshot()
        self._async_update_issue(create=True)
        async_track_time_interval(
            self.hass,
            self._async_interval,
            SNAPSHOT_INTERVAL,
            cancel_on_shutdown=True,
        )

    @callback
    def _async_interval(self, _now: datetime) -> None:
        self._async_save_snapshot()
        self._async_update_issue(create=False)

    @callback
    def _async_stop(self, _event: Event) -> None:
        # A run stopped during the grace period never becomes the baseline.
        if self._unsub_grace is not None:
            self._unsub_grace()
            self._unsub_grace = None
            return
        self._async_save_snapshot()

    @callback
    def _async_save_snapshot(self) -> None:
        snapshot = async_take_snapshot(self.hass)
        if self._last is not None and _without_created(self._last) == _without_created(
            snapshot
        ):
            return
        self._last = snapshot
        self._async_save()

    @callback
    def _async_save(self) -> None:
        data: StoredData = {"baseline": self.baseline, "last": self._last}
        self._store.async_delay_save(lambda: data, 0)

    @callback
    def _async_update_issue(self, *, create: bool) -> None:
        """Raise, refresh or remove the issue announcing the report."""
        if (report := self.async_get_report()) is None or not (
            counts := _counts(report)
        ):
            ir.async_delete_issue(self.hass, DOMAIN, UPDATE_REPORT_ISSUE_ID)
            return
        if not create and not ir.async_get(self.hass).async_get_issue(
            DOMAIN, UPDATE_REPORT_ISSUE_ID
        ):
            return
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            UPDATE_REPORT_ISSUE_ID,
            is_fixable=True,
            is_persistent=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=UPDATE_REPORT_ISSUE_ID,
            translation_placeholders={
                "from_version": report["from_version"],
                "to_version": report["to_version"],
                **{key: str(count) for key, count in counts.items()},
            },
        )

    @callback
    def async_get_report(self) -> dict[str, Any] | None:
        """Return what got worse since the baseline, if there is one."""
        if self.baseline is None:
            return None
        return async_diff(self.hass, self.baseline)

    @callback
    def async_dismiss(self) -> None:
        """Forget the baseline."""
        self.baseline = None
        self._async_save()
        ir.async_delete_issue(self.hass, DOMAIN, UPDATE_REPORT_ISSUE_ID)


def _without_created(snapshot: RunSnapshot) -> dict[str, Any]:
    return {key: value for key, value in snapshot.items() if key != "created"}


def _counts(report: dict[str, Any]) -> dict[str, int]:
    """Return the number of changes per group, empty if nothing changed."""
    counts = {
        "config_entries": len(report["config_entries"]),
        "entities": len(report["entities_unavailable"])
        + len(report["entities_renamed"])
        + len(report["entities_removed"]),
        "issues": len(report["issues"]),
    }
    return counts if any(counts.values()) else {}


@callback
def _async_is_unhealthy(hass: HomeAssistant, entity_id: str) -> bool:
    return (
        state := hass.states.get(entity_id)
    ) is None or state.state in _UNHEALTHY_STATES


@callback
def _async_active_issues(hass: HomeAssistant) -> list[tuple[str, str]]:
    return [
        key
        for key, issue in ir.async_get(hass).issues.items()
        if issue.active
        and issue.dismissed_version is None
        and key != (DOMAIN, UPDATE_REPORT_ISSUE_ID)
    ]


@callback
def async_take_snapshot(hass: HomeAssistant) -> RunSnapshot:
    """Return a snapshot of the running instance."""
    config_entries: dict[str, dict[str, str]] = {}
    for entry in hass.config_entries.async_entries():
        if entry.state is ConfigEntryState.LOADED:
            config_entries.setdefault(entry.domain, {})[entry.entry_id] = entry.title

    entities: dict[str, dict[str, str]] = {}
    unhealthy: list[str] = []
    for entity_entry in er.async_get(hass).entities.values():
        if entity_entry.disabled_by is not None:
            continue
        entities.setdefault(entity_entry.platform, {})[entity_entry.id] = (
            entity_entry.entity_id
        )
        if _async_is_unhealthy(hass, entity_entry.entity_id):
            unhealthy.append(entity_entry.id)

    return {
        "version": __version__,
        "created": dt_util.utcnow().isoformat(),
        "config_entries": config_entries,
        "entities": entities,
        "unhealthy": unhealthy,
        "issues": [list(key) for key in _async_active_issues(hass)],
    }


@callback
def async_diff(hass: HomeAssistant, baseline: RunSnapshot) -> dict[str, Any]:
    """Return what got worse compared to the baseline run."""
    config_entries: list[dict[str, str | None]] = []
    for domain, titles in baseline["config_entries"].items():
        for entry_id, title in titles.items():
            if (entry := hass.config_entries.async_get_entry(entry_id)) is None:
                config_entries.append(
                    {
                        "entry_id": entry_id,
                        "domain": domain,
                        "title": title,
                        "state": None,
                        "reason": None,
                    }
                )
            elif (
                entry.disabled_by is None and entry.state is not ConfigEntryState.LOADED
            ):
                config_entries.append(
                    {
                        "entry_id": entry_id,
                        "domain": entry.domain,
                        "title": entry.title,
                        "state": entry.state.value,
                        "reason": entry.reason,
                    }
                )
    failed_entry_ids = {entry["entry_id"] for entry in config_entries}

    entity_registry = er.async_get(hass)
    old_unhealthy = set(baseline["unhealthy"])
    removed: list[dict[str, str]] = []
    renamed: list[dict[str, str]] = []
    unavailable: list[dict[str, str | None]] = []
    for platform, entity_ids in baseline["entities"].items():
        for registry_id, old_entity_id in entity_ids.items():
            if (
                entity_entry := entity_registry.entities.get_entry(registry_id)
            ) is None:
                removed.append({"entity_id": old_entity_id, "platform": platform})
                continue
            entity_id = entity_entry.entity_id
            if entity_id != old_entity_id:
                renamed.append(
                    {
                        "old_entity_id": old_entity_id,
                        "entity_id": entity_id,
                        "platform": platform,
                    }
                )
            # Entities of a failed config entry are covered by the entry.
            if (
                registry_id in old_unhealthy
                or entity_entry.disabled_by is not None
                or entity_entry.config_entry_id in failed_entry_ids
                or not _async_is_unhealthy(hass, entity_id)
            ):
                continue
            unavailable.append(
                {
                    "entity_id": entity_id,
                    "platform": platform,
                    "state": state.state
                    if (state := hass.states.get(entity_id))
                    else None,
                }
            )

    old_issues = {(domain, issue_id) for domain, issue_id in baseline["issues"]}
    issues = [
        {"domain": domain, "issue_id": issue_id}
        for domain, issue_id in _async_active_issues(hass)
        if (domain, issue_id) not in old_issues
    ]

    by_entity_id = itemgetter("entity_id")
    return {
        "from_version": baseline["version"],
        "to_version": __version__,
        "created": baseline["created"],
        "config_entries": sorted(config_entries, key=itemgetter("domain", "title")),
        "entities_unavailable": sorted(unavailable, key=by_entity_id),
        "entities_renamed": sorted(renamed, key=by_entity_id),
        "entities_removed": sorted(removed, key=by_entity_id),
        "issues": sorted(issues, key=itemgetter("domain", "issue_id")),
        "upcoming": _async_upcoming(hass),
    }


@callback
def _async_upcoming(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Return issues of set up integrations that break in a future version."""
    upcoming = [
        {
            "domain": issue.domain,
            "issue_id": issue.issue_id,
            "issue_domain": issue.issue_domain,
            "breaks_in_ha_version": issue.breaks_in_ha_version,
            "dismissed": issue.dismissed_version is not None,
        }
        for issue in ir.async_get(hass).issues.values()
        if issue.active
        and issue.breaks_in_ha_version
        and (issue.issue_domain or issue.domain) in hass.config.components
    ]
    return sorted(
        upcoming,
        key=lambda issue: (
            AwesomeVersion(issue["breaks_in_ha_version"]),
            issue["domain"],
            issue["issue_id"],
        ),
    )


async def async_setup(hass: HomeAssistant) -> None:
    """Set up the update report."""
    update_report = hass.data[DATA_UPDATE_REPORT] = UpdateReport(hass)
    await update_report.async_load()
    update_report.async_start()
    websocket_api.async_register_command(hass, ws_update_report)
    websocket_api.async_register_command(hass, ws_dismiss_update_report)


@websocket_api.require_admin
@websocket_api.websocket_command({probatio.Required("type"): "repairs/update_report"})
@callback
def ws_update_report(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return what changed since the run before the last update."""
    connection.send_result(msg["id"], hass.data[DATA_UPDATE_REPORT].async_get_report())


@websocket_api.require_admin
@websocket_api.websocket_command(
    {probatio.Required("type"): "repairs/update_report/dismiss"}
)
@callback
def ws_dismiss_update_report(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Forget the run before the last update."""
    hass.data[DATA_UPDATE_REPORT].async_dismiss()
    connection.send_result(msg["id"])
