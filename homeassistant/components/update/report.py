"""Report the repair issues that appeared after a Home Assistant Core update."""

from datetime import datetime, timedelta
from operator import itemgetter
from typing import TYPE_CHECKING, Any, TypedDict

import probatio

from homeassistant.components import automation, script, websocket_api
from homeassistant.const import __version__
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HassJob,
    HomeAssistant,
    callback,
)
from homeassistant.helpers import (
    config_validation as cv,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.event import async_call_later, async_track_state_change_event
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
from homeassistant.util.hass_dict import HassKey
from homeassistant.util.ulid import ulid_now

from .const import DOMAIN

DATA_UPDATE_REPORT: HassKey[UpdateReport] = HassKey("update_report")
STORAGE_KEY = "update.report"
STORAGE_VERSION = 1
# Integrations that poll a cloud service can take minutes to come up.
STARTUP_GRACE = timedelta(minutes=5)
MAX_REPORTS = 10
STALE_ISSUE_PREFIX = "stale_entity_"

ERROR_ISSUE_SEVERITIES = {ir.IssueSeverity.ERROR, ir.IssueSeverity.CRITICAL}
REFERENCING = {
    "automation": automation.automations_with_entity,
    "script": script.scripts_with_entity,
}


class RunSnapshot(TypedDict):
    """What a run of Home Assistant looked like when an update started."""

    # Entity registry id of the update entity the report belongs to
    update_entity: str
    version: str
    created: str
    backup: bool
    automatic: bool
    # platform -> {registry id: entity_id}, only enabled entities
    entities: dict[str, dict[str, str]]
    # (domain, issue_id) of active issues that are not ignored
    issues: list[list[str]]


class Report(TypedDict):
    """The repair issues that appeared since an update."""

    id: str
    from_version: str
    to_version: str
    update_started: str
    backup: bool
    automatic: bool
    # When Home Assistant was running again after the update
    started: str | None
    created: str | None
    pending: bool
    severity: str | None
    issues: list[dict[str, str | None]]


class PendingReport(TypedDict):
    """An update whose report is made once startup has settled."""

    id: str
    baseline: RunSnapshot
    started: str | None


class StoredData(TypedDict):
    """Stored snapshots and reports."""

    before_update: RunSnapshot | None
    pending: PendingReport | None
    # Entity registry id of the update entity -> reports, newest first
    reports: dict[str, list[Report]]


class UpdateReport:
    """Compare the run before an update with the run after it."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the update report."""
        self.hass = hass
        self._before_update: RunSnapshot | None = None
        self._pending: PendingReport | None = None
        self._reports: dict[str, list[Report]] = {}
        self._store: Store[StoredData] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._unsub_stale: CALLBACK_TYPE | None = None

    async def async_load(self) -> None:
        """Load the stored data; a snapshot from before an update becomes pending."""
        if (stored := await self._store.async_load()) is None:
            return
        self._pending = stored["pending"]
        self._reports = stored["reports"]
        if (before_update := stored["before_update"]) is None:
            return
        # A failed update leaves the version unchanged; drop its snapshot.
        if before_update["version"] != __version__:
            self._pending = {
                "id": ulid_now(),
                "baseline": before_update,
                "started": None,
            }
        await self._async_save()

    @callback
    def async_start(self) -> None:
        """Make the report once startup has settled, if one is pending."""
        self._async_track_stale_issues()
        if self._pending is None:
            return
        job = HassJob(
            self._async_startup_settled,
            "update report after startup",
            cancel_on_shutdown=True,
        )

        @callback
        def _async_started(hass: HomeAssistant) -> None:
            # A restart within the grace period keeps the first start.
            if self._pending is not None and self._pending["started"] is None:
                self._pending["started"] = dt_util.utcnow().isoformat()
                self._store.async_delay_save(self._data_to_save)
            async_call_later(hass, STARTUP_GRACE, job)

        async_at_started(self.hass, _async_started)

    async def _async_startup_settled(self, _now: datetime) -> None:
        # The next update may have finished the report already.
        if self._pending is None:
            return
        self._async_finish_pending()
        await self._async_save()

    @callback
    def _async_finish_pending(self) -> None:
        if TYPE_CHECKING:
            assert self._pending is not None
        baseline = self._pending["baseline"]
        # Created first, so they count as issues that appeared since the update
        _async_prune_stale_reference_issues(self.hass)
        _async_create_stale_reference_issues(self.hass, baseline)
        reports = self._reports.setdefault(baseline["update_entity"], [])
        reports.insert(0, async_diff(self.hass, self._pending, dt_util.utcnow()))
        del reports[MAX_REPORTS:]
        self._pending = None
        self._async_track_stale_issues()

    @callback
    def _async_track_stale_issues(self) -> None:
        """Watch the automations and scripts with a stale reference for a fix."""
        if self._unsub_stale is not None:
            self._unsub_stale()
            self._unsub_stale = None
        if not (referencing := _async_stale_reference_issues(self.hass)):
            return
        self._unsub_stale = async_track_state_change_event(
            self.hass, referencing, self._async_stale_reference_changed
        )

    @callback
    def _async_stale_reference_changed(
        self, event: Event[EventStateChangedData]
    ) -> None:
        if _async_prune_stale_reference_issues(self.hass, event.data["entity_id"]):
            self._async_track_stale_issues()

    async def async_before_update(
        self, update_entity: str, *, backup: bool, automatic: bool
    ) -> None:
        """Save a snapshot of the running instance before it is updated."""
        # This run is the one the pending report is about; it ends now.
        if self._pending is not None:
            self._async_finish_pending()
        self._before_update = async_take_snapshot(
            self.hass, update_entity, backup=backup, automatic=automatic
        )
        await self._async_save()

    async def async_discard_before_update(self) -> None:
        """Forget the snapshot of an update that did not start."""
        self._before_update = None
        await self._async_save()

    async def _async_save(self) -> None:
        await self._store.async_save(self._data_to_save())

    @callback
    def _data_to_save(self) -> StoredData:
        return {
            "before_update": self._before_update,
            "pending": self._pending,
            "reports": self._reports,
        }

    @callback
    def async_get_reports(self, update_entity: str) -> list[Report]:
        """Return the reports of an update entity newest first, live while pending."""
        reports = self._reports.get(update_entity, [])
        if (
            self._pending is None
            or self._pending["baseline"]["update_entity"] != update_entity
        ):
            return reports
        return [async_diff(self.hass, self._pending, None), *reports][:MAX_REPORTS]

    @callback
    def async_get_report(self, update_entity: str, report_id: str) -> Report | None:
        """Return a report of an update entity, live while pending."""
        if (
            self._pending is not None
            and self._pending["id"] == report_id
            and self._pending["baseline"]["update_entity"] == update_entity
        ):
            return async_diff(self.hass, self._pending, None)
        return next(
            (
                report
                for report in self._reports.get(update_entity, [])
                if report["id"] == report_id
            ),
            None,
        )


@callback
def _async_active_issues(hass: HomeAssistant) -> list[ir.IssueEntry]:
    issue_registry = ir.async_get(hass)
    return [
        issue
        for issue in issue_registry.issues.values()
        if issue.active
        and not issue_registry.async_is_hidden(issue)
        and issue.dismissed_version is None
    ]


@callback
def async_take_snapshot(
    hass: HomeAssistant, update_entity: str, *, backup: bool, automatic: bool
) -> RunSnapshot:
    """Return a snapshot of the running instance."""
    entities: dict[str, dict[str, str]] = {}
    for entity_entry in er.async_get(hass).entities.values():
        if entity_entry.disabled_by is None:
            entities.setdefault(entity_entry.platform, {})[entity_entry.id] = (
                entity_entry.entity_id
            )

    return {
        "update_entity": update_entity,
        "version": __version__,
        "created": dt_util.utcnow().isoformat(),
        "backup": backup,
        "automatic": automatic,
        "entities": entities,
        "issues": [
            [issue.domain, issue.issue_id] for issue in _async_active_issues(hass)
        ],
    }


@callback
def _async_create_stale_reference_issues(
    hass: HomeAssistant, baseline: RunSnapshot
) -> None:
    """Create a repair for each automation and script using an entity ID that is gone."""
    entity_registry = er.async_get(hass)
    for entity_ids in baseline["entities"].values():
        for registry_id, old_entity_id in entity_ids.items():
            if _async_entity_exists(hass, old_entity_id):
                continue
            entity_entry = entity_registry.entities.get_entry(registry_id)
            new_entity_id = entity_entry.entity_id if entity_entry else None
            for kind, referencing in REFERENCING.items():
                for kind_entity_id in referencing(hass, old_entity_id):
                    _async_create_stale_reference_issue(
                        hass, kind, kind_entity_id, old_entity_id, new_entity_id
                    )


@callback
def _async_entity_exists(hass: HomeAssistant, entity_id: str) -> bool:
    """Return whether references to entity_id work, maybe through another entity."""
    return (
        er.async_get(hass).async_is_registered(entity_id)
        or hass.states.get(entity_id) is not None
    )


@callback
def _async_stale_reference_issues(
    hass: HomeAssistant,
) -> dict[str, list[ir.IssueEntry]]:
    """Return the stale reference issues by the automation or script they are about."""
    issues: dict[str, list[ir.IssueEntry]] = {}
    for (domain, issue_id), issue in ir.async_get(hass).issues.items():
        if domain != DOMAIN or not issue_id.startswith(STALE_ISSUE_PREFIX):
            continue
        if TYPE_CHECKING:
            assert issue.translation_placeholders is not None
        issues.setdefault(issue.translation_placeholders["kind_entity_id"], []).append(
            issue
        )
    return issues


@callback
def _async_prune_stale_reference_issues(
    hass: HomeAssistant, kind_entity_id: str | None = None
) -> bool:
    """Delete the stale reference issues that are fixed; return whether any was."""
    deleted = False
    for referencing_id, issues in _async_stale_reference_issues(hass).items():
        if kind_entity_id is not None and referencing_id != kind_entity_id:
            continue
        for issue in issues:
            if TYPE_CHECKING:
                assert issue.translation_placeholders is not None
            if _async_is_stale_reference(
                hass, referencing_id, issue.translation_placeholders["old_entity_id"]
            ):
                continue
            ir.async_delete_issue(hass, DOMAIN, issue.issue_id)
            deleted = True
    return deleted


@callback
def _async_is_stale_reference(
    hass: HomeAssistant, kind_entity_id: str, old_entity_id: str
) -> bool:
    """Return whether the automation or script still uses the missing entity."""
    if hass.states.get(kind_entity_id) is None:
        # Without a state it is being reloaded, unless it was deleted
        return er.async_get(hass).async_is_registered(kind_entity_id)
    if _async_entity_exists(hass, old_entity_id):
        return False
    referencing = REFERENCING[kind_entity_id.partition(".")[0]]
    return kind_entity_id in referencing(hass, old_entity_id)


@callback
def _async_create_stale_reference_issue(
    hass: HomeAssistant,
    kind: str,
    kind_entity_id: str,
    old_entity_id: str,
    new_entity_id: str | None,
) -> None:
    entry = er.async_get(hass).async_get(kind_entity_id)
    state = hass.states.get(kind_entity_id)
    placeholders = {
        "name": state.name if state else kind_entity_id,
        "kind_entity_id": kind_entity_id,
        "old_entity_id": old_entity_id,
        "to_version": __version__,
        # Only automations and scripts with a unique id have an editor
        "edit": f"/config/{kind}/edit/{entry.unique_id}"
        if entry and entry.unique_id
        else f"/config/{kind}/show/{kind_entity_id}",
    }
    if new_entity_id is not None:
        placeholders["new_entity_id"] = new_entity_id
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"stale_entity_{kind_entity_id}_{old_entity_id}",
        is_fixable=False,
        is_persistent=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key=(
            "stale_entity_removed" if new_entity_id is None else "stale_entity_renamed"
        ),
        translation_placeholders=placeholders,
    )


@callback
def async_diff(
    hass: HomeAssistant, pending: PendingReport, created: datetime | None
) -> Report:
    """Return the issues that appeared since the baseline run."""
    baseline = pending["baseline"]
    old_issues = {(domain, issue_id) for domain, issue_id in baseline["issues"]}
    issues = sorted(
        (
            {
                "domain": issue.domain,
                "issue_id": issue.issue_id,
                "severity": issue.severity,
            }
            for issue in _async_active_issues(hass)
            if (issue.domain, issue.issue_id) not in old_issues
        ),
        key=itemgetter("domain", "issue_id"),
    )
    return {
        "id": pending["id"],
        "from_version": baseline["version"],
        "to_version": __version__,
        "update_started": baseline["created"],
        "backup": baseline["backup"],
        "automatic": baseline["automatic"],
        "started": pending["started"],
        "created": created.isoformat() if created else None,
        "pending": created is None,
        "severity": _severity(issues),
        "issues": issues,
    }


def _severity(issues: list[dict[str, str | None]]) -> str | None:
    """Return how bad the new issues are."""
    if any(issue["severity"] in ERROR_ISSUE_SEVERITIES for issue in issues):
        return "error"
    if issues:
        return "warning"
    return None


async def async_setup(hass: HomeAssistant) -> None:
    """Set up the update report."""
    update_report = hass.data[DATA_UPDATE_REPORT] = UpdateReport(hass)
    await update_report.async_load()
    update_report.async_start()
    websocket_api.async_register_command(hass, websocket_reports)
    websocket_api.async_register_command(hass, websocket_report)


async def async_snapshot_before_update(
    hass: HomeAssistant, entity_id: str, *, backup: bool, automatic: bool
) -> None:
    """Save the running instance before entity_id updates Home Assistant Core."""
    if (entity_entry := er.async_get(hass).async_get(entity_id)) is None or (
        update_report := hass.data.get(DATA_UPDATE_REPORT)
    ) is None:
        return
    await update_report.async_before_update(
        entity_entry.id, backup=backup, automatic=automatic
    )


async def async_discard_snapshot(hass: HomeAssistant) -> None:
    """Forget the snapshot when the update did not start."""
    if (update_report := hass.data.get(DATA_UPDATE_REPORT)) is not None:
        await update_report.async_discard_before_update()


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        probatio.Required("type"): "update/reports",
        probatio.Required("entity_id"): cv.entity_id,
    }
)
@callback
def websocket_reports(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return the reports of the recent updates of an update entity."""
    if (entity_entry := er.async_get(hass).async_get(msg["entity_id"])) is None:
        connection.send_result(msg["id"], [])
        return
    connection.send_result(
        msg["id"],
        [
            {
                "id": report["id"],
                "from_version": report["from_version"],
                "to_version": report["to_version"],
                "update_started": report["update_started"],
                "created": report["created"],
                "pending": report["pending"],
                "severity": report["severity"],
                "automatic": report["automatic"],
                "issues": len(report["issues"]),
            }
            for report in hass.data[DATA_UPDATE_REPORT].async_get_reports(
                entity_entry.id
            )
        ],
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        probatio.Required("type"): "update/report",
        probatio.Required("entity_id"): cv.entity_id,
        probatio.Required("report_id"): str,
    }
)
@callback
def websocket_report(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return a report of an update of an update entity."""
    if (entity_entry := er.async_get(hass).async_get(msg["entity_id"])) is None:
        connection.send_result(msg["id"], None)
        return
    connection.send_result(
        msg["id"],
        hass.data[DATA_UPDATE_REPORT].async_get_report(
            entity_entry.id, msg["report_id"]
        ),
    )
