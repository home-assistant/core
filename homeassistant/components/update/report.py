"""Report what got worse after a Home Assistant Core update."""

from datetime import datetime, timedelta
from operator import itemgetter
from typing import TYPE_CHECKING, Any, TypedDict

from awesomeversion import AwesomeVersion
import probatio

from homeassistant.components import automation, script, websocket_api
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, __version__
from homeassistant.core import HassJob, HomeAssistant, callback
from homeassistant.helpers import (
    config_validation as cv,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
from homeassistant.util.hass_dict import HassKey

DATA_UPDATE_REPORT: HassKey[UpdateReport] = HassKey("update_report")
STORAGE_KEY = "update.report"
STORAGE_VERSION = 1
# Integrations that poll a cloud service can take minutes to come up.
STARTUP_GRACE = timedelta(minutes=5)


class RunSnapshot(TypedDict):
    """What a run of Home Assistant looked like."""

    # Entity registry id of the update entity the report belongs to
    update_entity: str
    version: str
    created: str
    # domain -> {entry_id: title}, only entries that were loaded
    config_entries: dict[str, dict[str, str]]
    # platform -> {registry id: entity_id}, only enabled entities
    entities: dict[str, dict[str, str]]
    # registry ids of entities without a state or unavailable
    unavailable: list[str]
    # registry ids of entities with an unknown state
    unknown: list[str]
    # (domain, issue_id) of active issues that are not ignored, without
    # breaking changes
    issues: list[list[str]]
    # (domain, issue_id) of issues with a breaks_in_ha_version
    upcoming: list[list[str]]


class Report(TypedDict):
    """What got worse after an update."""

    from_version: str
    to_version: str
    created: str | None
    pending: bool
    config_entries: list[dict[str, Any]]
    entities_unavailable: list[dict[str, Any]]
    entities_renamed: list[dict[str, Any]]
    entities_removed: list[dict[str, Any]]
    issues: list[dict[str, str]]
    upcoming: list[dict[str, Any]]


class StoredData(TypedDict):
    """Stored snapshots and the last report."""

    before_update: RunSnapshot | None
    baseline: RunSnapshot | None
    report: Report | None


class UpdateReport:
    """Compare the run before an update with the run after it."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the update report."""
        self.hass = hass
        self.baseline: RunSnapshot | None = None
        self.report: Report | None = None
        self._before_update: RunSnapshot | None = None
        self._store: Store[StoredData] = Store(hass, STORAGE_VERSION, STORAGE_KEY)

    async def async_load(self) -> None:
        """Load the stored data; a snapshot from before an update becomes the baseline."""
        if (stored := await self._store.async_load()) is None:
            return
        self.baseline = stored["baseline"]
        self.report = stored["report"]
        if (before_update := stored["before_update"]) is None:
            return
        # A failed update leaves the version unchanged; drop its snapshot.
        if before_update["version"] != __version__:
            self.baseline = before_update
            self.report = None
        await self._async_save()

    @callback
    def async_start(self) -> None:
        """Make the report once startup has settled, if one is pending."""
        if self.baseline is None or self.report is not None:
            return
        job = HassJob(
            self._async_startup_settled,
            "update report after startup",
            cancel_on_shutdown=True,
        )

        @callback
        def _async_started(hass: HomeAssistant) -> None:
            async_call_later(hass, STARTUP_GRACE, job)

        async_at_started(self.hass, _async_started)

    async def _async_startup_settled(self, _now: datetime) -> None:
        if TYPE_CHECKING:
            assert self.baseline is not None
        self.report = async_diff(self.hass, self.baseline, dt_util.utcnow())
        await self._async_save()

    async def async_before_update(self, update_entity: str) -> None:
        """Save a snapshot of the running instance before it is updated."""
        self._before_update = async_take_snapshot(self.hass, update_entity)
        await self._async_save()

    async def _async_save(self) -> None:
        await self._store.async_save(
            {
                "before_update": self._before_update,
                "baseline": self.baseline,
                "report": self.report,
            }
        )

    @callback
    def async_get_report(self, update_entity: str) -> Report | None:
        """Return the last report of an update entity, live while pending."""
        if self.baseline is None or self.baseline["update_entity"] != update_entity:
            return None
        if self.report is not None:
            return self.report
        return async_diff(self.hass, self.baseline, None)


@callback
def _async_active_issues(hass: HomeAssistant) -> list[tuple[str, str]]:
    issue_registry = ir.async_get(hass)
    return [
        key
        for key, issue in issue_registry.issues.items()
        if issue.active
        and not issue_registry.async_is_hidden(issue)
        and issue.dismissed_version is None
        and not issue.breaks_in_ha_version
    ]


@callback
def async_take_snapshot(hass: HomeAssistant, update_entity: str) -> RunSnapshot:
    """Return a snapshot of the running instance."""
    config_entries: dict[str, dict[str, str]] = {}
    for entry in hass.config_entries.async_entries():
        if entry.state is ConfigEntryState.LOADED:
            config_entries.setdefault(entry.domain, {})[entry.entry_id] = entry.title

    entities: dict[str, dict[str, str]] = {}
    unavailable: list[str] = []
    unknown: list[str] = []
    for entity_entry in er.async_get(hass).entities.values():
        if entity_entry.disabled_by is not None:
            continue
        entities.setdefault(entity_entry.platform, {})[entity_entry.id] = (
            entity_entry.entity_id
        )
        if (state := hass.states.get(entity_entry.entity_id)) is None or (
            state.state == STATE_UNAVAILABLE
        ):
            unavailable.append(entity_entry.id)
        elif state.state == STATE_UNKNOWN:
            unknown.append(entity_entry.id)

    return {
        "update_entity": update_entity,
        "version": __version__,
        "created": dt_util.utcnow().isoformat(),
        "config_entries": config_entries,
        "entities": entities,
        "unavailable": unavailable,
        "unknown": unknown,
        "issues": [list(key) for key in _async_active_issues(hass)],
        "upcoming": [
            [domain, issue_id]
            for (domain, issue_id), issue in ir.async_get(hass).issues.items()
            if issue.breaks_in_ha_version
        ],
    }


@callback
def _async_failed_config_entries(
    hass: HomeAssistant, baseline: RunSnapshot
) -> list[dict[str, Any]]:
    """Return the config entries that were loaded before and are not now."""
    failed: list[dict[str, Any]] = []
    for domain, titles in baseline["config_entries"].items():
        for entry_id, title in titles.items():
            if (entry := hass.config_entries.async_get_entry(entry_id)) is None:
                failed.append(
                    {
                        "entry_id": entry_id,
                        "domain": domain,
                        "title": title,
                        "state": None,
                        "translation_domain": None,
                        "translation_key": None,
                        "translation_placeholders": None,
                    }
                )
            elif (
                entry.disabled_by is None and entry.state is not ConfigEntryState.LOADED
            ):
                failed.append(
                    {
                        "entry_id": entry_id,
                        "domain": entry.domain,
                        "title": entry.title,
                        "state": entry.state.value,
                        "translation_domain": entry.error_reason_translation_domain,
                        "translation_key": entry.error_reason_translation_key,
                        "translation_placeholders": (
                            entry.error_reason_translation_placeholders
                        ),
                    }
                )
    return sorted(failed, key=itemgetter("domain", "title"))


@callback
def async_diff(
    hass: HomeAssistant, baseline: RunSnapshot, created: datetime | None
) -> Report:
    """Return what got worse compared to the baseline run."""
    config_entries = _async_failed_config_entries(hass, baseline)
    failed_entry_ids = {entry["entry_id"] for entry in config_entries}

    entity_registry = er.async_get(hass)
    was_unavailable = set(baseline["unavailable"])
    was_unknown = set(baseline["unknown"])
    removed: list[dict[str, Any]] = []
    renamed: list[dict[str, Any]] = []
    unavailable: list[dict[str, Any]] = []
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
                registry_id in was_unavailable
                or entity_entry.disabled_by is not None
                or entity_entry.config_entry_id in failed_entry_ids
            ):
                continue
            # Unknown is only worse than a value; an unpressed button stays unknown.
            if (state := hass.states.get(entity_id)) is not None and (
                state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)
                or (state.state == STATE_UNKNOWN and registry_id in was_unknown)
            ):
                continue
            unavailable.append(
                {
                    "entity_id": entity_id,
                    "platform": platform,
                    "state": state.state if state else None,
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
        "created": created.isoformat() if created else None,
        "pending": created is None,
        "config_entries": config_entries,
        "entities_unavailable": sorted(unavailable, key=by_entity_id),
        "entities_renamed": sorted(renamed, key=by_entity_id),
        "entities_removed": sorted(removed, key=by_entity_id),
        "issues": sorted(issues, key=itemgetter("domain", "issue_id")),
        "upcoming": _async_upcoming(
            hass,
            {(domain, issue_id) for domain, issue_id in baseline["upcoming"]},
        ),
    }


@callback
def _async_upcoming(
    hass: HomeAssistant, known: set[tuple[str, str]]
) -> list[dict[str, Any]]:
    """Return new issues of set up integrations that break in a future version."""
    issue_registry = ir.async_get(hass)
    current = AwesomeVersion(__version__)
    upcoming = [
        {
            "domain": issue.domain,
            "issue_id": issue.issue_id,
            "issue_domain": issue.issue_domain,
            "breaks_in_ha_version": issue.breaks_in_ha_version,
            "dismissed": issue.dismissed_version is not None,
        }
        for key, issue in issue_registry.issues.items()
        if key not in known
        and issue.active
        and not issue_registry.async_is_hidden(issue)
        and issue.breaks_in_ha_version
        and AwesomeVersion(issue.breaks_in_ha_version) > current
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
    websocket_api.async_register_command(hass, websocket_report)


async def async_snapshot_before_update(hass: HomeAssistant, entity_id: str) -> None:
    """Save the running instance before entity_id updates Home Assistant Core."""
    if (entity_entry := er.async_get(hass).async_get(entity_id)) is None or (
        update_report := hass.data.get(DATA_UPDATE_REPORT)
    ) is None:
        return
    await update_report.async_before_update(entity_entry.id)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        probatio.Required("type"): "update/report",
        probatio.Required("entity_id"): cv.entity_id,
    }
)
@callback
def websocket_report(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Return the report of the last update of an update entity."""
    if (entity_entry := er.async_get(hass).async_get(msg["entity_id"])) is None or (
        report := hass.data[DATA_UPDATE_REPORT].async_get_report(entity_entry.id)
    ) is None:
        connection.send_result(msg["id"], None)
        return
    connection.send_result(
        msg["id"],
        {
            **report,
            "entities_removed": [
                entity | _async_references(hass, entity["entity_id"])
                for entity in report["entities_removed"]
            ],
            "entities_renamed": [
                entity | _async_references(hass, entity["old_entity_id"])
                for entity in report["entities_renamed"]
            ],
        },
    )


@callback
def _async_references(
    hass: HomeAssistant, entity_id: str
) -> dict[str, list[dict[str, str | None]]]:
    """Return the automations and scripts that still use an old entity ID."""
    return {
        "automations": _async_named(
            hass, automation.automations_with_entity(hass, entity_id)
        ),
        "scripts": _async_named(hass, script.scripts_with_entity(hass, entity_id)),
    }


@callback
def _async_named(
    hass: HomeAssistant, entity_ids: list[str]
) -> list[dict[str, str | None]]:
    entity_registry = er.async_get(hass)
    return [
        {
            "entity_id": entity_id,
            # The editor id, None when the automation or script is not editable
            "id": entry.unique_id
            if (entry := entity_registry.async_get(entity_id))
            else None,
            "name": state.name if (state := hass.states.get(entity_id)) else None,
        }
        for entity_id in sorted(entity_ids)
    ]
