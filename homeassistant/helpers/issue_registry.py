"""Persistently store issues raised by integrations."""

from collections.abc import Iterable
import dataclasses
from datetime import datetime
from enum import StrEnum
import functools as ft
import re
from types import TracebackType
from typing import Any, Literal, Self, TypedDict, cast, override

from awesomeversion import AwesomeVersion, AwesomeVersionStrategy

from homeassistant.const import __version__ as ha_version
from homeassistant.core import HomeAssistant, callback, verify_event_loop_thread
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util
from homeassistant.util.async_ import run_callback_threadsafe
from homeassistant.util.event_type import EventType
from homeassistant.util.hass_dict import HassKey

from .registry import BaseRegistry
from .singleton import singleton
from .storage import Store

DATA_REGISTRY: HassKey[IssueRegistry] = HassKey("issue_registry")
EVENT_REPAIRS_ISSUE_REGISTRY_UPDATED: EventType[EventIssueRegistryUpdatedData] = (
    EventType("repairs_issue_registry_updated")
)
STORAGE_KEY = "repairs.issue_registry"
STORAGE_VERSION_MAJOR = 1
STORAGE_VERSION_MINOR = 3

# Issues that are handled entirely by the frontend and don't need
# a description or fix_flow.
FRONTEND_HANDLED_ISSUES: dict[str, set[str]] = {
    "sensor": {"mean_type_changed", "state_class_removed", "units_changed"},
    "vacuum": {"segments_changed"},
}


class EventIssueRegistryUpdatedData(TypedDict):
    """Event data for when the issue registry is updated."""

    action: Literal["create", "remove", "update"]
    domain: str
    issue_id: str


class IssueSeverity(StrEnum):
    """Issue severity."""

    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"


@dataclasses.dataclass(slots=True, frozen=True)
class IssueEntry:
    """Issue Registry Entry."""

    active: bool
    breaks_in_ha_version: str | None
    config_entry_id: str | None
    created: datetime
    data: dict[str, str | int | float | None] | None
    dismissed_version: str | None
    domain: str
    is_fixable: bool | None
    is_persistent: bool
    # Used if an integration creates issues for other integrations (ie alerts)
    issue_domain: str | None
    issue_id: str
    learn_more_url: str | None
    severity: IssueSeverity | None
    translation_key: str | None
    translation_placeholders: dict[str, str] | None

    def to_json(self) -> dict[str, Any]:
        """Return a JSON serializable representation for storage."""
        result = {
            "config_entry_id": self.config_entry_id,
            "created": self.created.isoformat(),
            "dismissed_version": self.dismissed_version,
            "domain": self.domain,
            "is_persistent": False,
            "issue_id": self.issue_id,
        }
        if not self.is_persistent:
            return result
        return {
            **result,
            "breaks_in_ha_version": self.breaks_in_ha_version,
            "data": self.data,
            "is_fixable": self.is_fixable,
            "is_persistent": True,
            "issue_domain": self.issue_domain,
            "issue_id": self.issue_id,
            "learn_more_url": self.learn_more_url,
            "severity": self.severity,
            "translation_key": self.translation_key,
            "translation_placeholders": self.translation_placeholders,
        }


class IssueRegistryStore(Store[dict[str, list[dict[str, Any]]]]):
    """Store entity registry data."""

    @override
    async def _async_migrate_func(
        self, old_major_version: int, old_minor_version: int, old_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Migrate to the new version."""
        if old_major_version == 1 and old_minor_version < 2:
            # Version 1.2 adds is_persistent
            for issue in old_data["issues"]:
                issue["is_persistent"] = False
        if old_major_version == 1 and old_minor_version < 3:
            # Version 1.3 adds config_entry_id
            for issue in old_data["issues"]:
                issue["config_entry_id"] = None
        return old_data


@dataclasses.dataclass(slots=True, eq=False)
class _RefreshState:
    """State of an active refresh."""

    scope: frozenset[tuple[str, str]]
    # Issues in scope not touched since the refresh began, deleted when it finishes
    untouched: set[tuple[str, str]]


def _newest_refresh(
    refreshes: list[_RefreshState], key: tuple[str, str]
) -> _RefreshState | None:
    """Return the newest active refresh which has the issue in its set."""
    for state in reversed(refreshes):
        if key in state.scope:
            return state
    return None


class IssuesRefresh:
    """Refresh of a set of issues.

    Issues in the set which have not been created, updated, deleted or kept when the
    refresh is finished are deleted. Issues don't need to be created through the
    refresh object, any call to async_create_issue counts.

    If refreshes overlap, the newest active refresh which has an issue in its set
    decides about the issue. When it ends, the decision falls back to the next
    newest active refresh, which deletes the issue only if it was not created,
    updated, deleted or kept since that refresh began.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        domain: str,
        refreshes: list[_RefreshState],
        deferred_deletes: set[tuple[str, str]],
        keys: set[tuple[str, str]],
    ) -> None:
        """Initialize the refresh and mark the issues as pending deletion."""
        self._deferred_deletes = deferred_deletes
        self._domain = domain
        self._hass = hass
        self._refreshes = refreshes
        self._state = _RefreshState(frozenset(keys), set(keys))
        refreshes.append(self._state)

    @callback
    def _async_end(self, candidates: Iterable[tuple[str, str]]) -> None:
        """End the refresh and delete the candidates it decides about."""
        if (state := self._state) not in self._refreshes:
            return
        newer = self._refreshes[self._refreshes.index(state) + 1 :]
        to_delete = [
            key for key in candidates if not any(key in r.scope for r in newer)
        ]
        self._refreshes.remove(state)
        issue_registry = async_get(self._hass)
        for domain, issue_id in to_delete:
            issue_registry.async_delete(domain, issue_id)

    @callback
    @verify_event_loop_thread("issue_registry.IssuesRefresh.async_keep")
    def async_keep(self, issue_ids: Iterable[str]) -> None:
        """Keep issues without creating or updating them.

        Issues outside the set of the refresh are ignored.
        """
        if (state := self._state) not in self._refreshes:
            return
        # Older refreshes don't get to delete an issue a newer one kept
        self_and_older = self._refreshes[: self._refreshes.index(state) + 1]
        for issue_id in issue_ids:
            key = (self._domain, issue_id)
            if key not in state.scope:
                continue
            for other in self_and_older:
                other.untouched.discard(key)
            if _newest_refresh(self._refreshes, key) is state:
                self._deferred_deletes.discard(key)

    @callback
    @verify_event_loop_thread("issue_registry.IssuesRefresh.async_finish")
    def async_finish(self) -> None:
        """Delete issues which were not created, updated, deleted or kept."""
        self._async_end(self._state.untouched)

    @callback
    @verify_event_loop_thread("issue_registry.IssuesRefresh.async_cancel")
    def async_cancel(self) -> None:
        """Cancel the refresh.

        Only issues whose delete was deferred to the refresh are deleted, other
        issues are left as they are.
        """
        self._async_end(self._deferred_deletes & self._state.scope)

    def __enter__(self) -> Self:
        """Enter the refresh context."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Finish the refresh, or cancel it if an exception was raised."""
        if exc_type is None:
            self.async_finish()
        else:
            self.async_cancel()


class IssueRegistry(BaseRegistry):
    """Class to hold a registry of issues."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the issue registry."""
        self.hass = hass
        self.issues: dict[tuple[str, str], IssueEntry] = {}
        # Active refreshes, oldest first
        self._refreshes: list[_RefreshState] = []
        # Issues whose delete was deferred to the newest refresh which has them in
        # its set, they are all untouched by that refresh
        self._deferred_deletes: set[tuple[str, str]] = set()
        self._store = IssueRegistryStore(
            hass,
            STORAGE_VERSION_MAJOR,
            STORAGE_KEY,
            atomic_writes=True,
            minor_version=STORAGE_VERSION_MINOR,
        )

    @callback
    def async_get_issue(self, domain: str, issue_id: str) -> IssueEntry | None:
        """Get issue by id."""
        return self.issues.get((domain, issue_id))

    @callback
    @verify_event_loop_thread("issue_registry.async_get_or_create")
    def async_get_or_create(
        self,
        domain: str,
        issue_id: str,
        *,
        breaks_in_ha_version: str | None = None,
        config_entry_id: str | None = None,
        data: dict[str, str | int | float | None] | None = None,
        is_fixable: bool,
        is_persistent: bool,
        issue_domain: str | None = None,
        learn_more_url: str | None = None,
        severity: IssueSeverity,
        translation_key: str,
        translation_placeholders: dict[str, str] | None = None,
    ) -> IssueEntry:
        """Get issue. Create if it doesn't exist."""
        if (
            config_entry_id is not None
            and self.hass.config_entries.async_get_entry(config_entry_id) is None
        ):
            raise HomeAssistantError(
                f"Can't link issue to unknown config entry {config_entry_id}"
            )
        self._async_touch((domain, issue_id))
        if (issue := self.async_get_issue(domain, issue_id)) is None:
            issue = IssueEntry(
                active=True,
                breaks_in_ha_version=breaks_in_ha_version,
                config_entry_id=config_entry_id,
                created=dt_util.utcnow(),
                data=data,
                dismissed_version=None,
                domain=domain,
                is_fixable=is_fixable,
                is_persistent=is_persistent,
                issue_domain=issue_domain,
                issue_id=issue_id,
                learn_more_url=learn_more_url,
                severity=severity,
                translation_key=translation_key,
                translation_placeholders=translation_placeholders,
            )
            self.issues[(domain, issue_id)] = issue
            self.async_schedule_save()
            self.hass.bus.async_fire_internal(
                EVENT_REPAIRS_ISSUE_REGISTRY_UPDATED,
                EventIssueRegistryUpdatedData(
                    action="create",
                    domain=domain,
                    issue_id=issue_id,
                ),
            )
        else:
            replacement = dataclasses.replace(
                issue,
                active=True,
                breaks_in_ha_version=breaks_in_ha_version,
                config_entry_id=config_entry_id,
                data=data,
                is_fixable=is_fixable,
                is_persistent=is_persistent,
                issue_domain=issue_domain,
                learn_more_url=learn_more_url,
                severity=severity,
                translation_key=translation_key,
                translation_placeholders=translation_placeholders,
            )
            # Only fire is something changed
            if replacement != issue:
                issue = self.issues[(domain, issue_id)] = replacement
                self.async_schedule_save()
                self.hass.bus.async_fire_internal(
                    EVENT_REPAIRS_ISSUE_REGISTRY_UPDATED,
                    EventIssueRegistryUpdatedData(
                        action="update",
                        domain=domain,
                        issue_id=issue_id,
                    ),
                )

        return issue

    @callback
    @verify_event_loop_thread("issue_registry.async_delete")
    def async_delete(
        self, domain: str, issue_id: str, *, defer_to_refresh: bool = False
    ) -> None:
        """Delete issue, see async_delete_issue."""
        key = (domain, issue_id)
        if (
            defer_to_refresh
            and (owner := _newest_refresh(self._refreshes, key)) is not None
        ):
            # A create or keep since the refresh began wins, also before this delete
            if key in owner.untouched:
                self._deferred_deletes.add(key)
            return
        self._async_touch(key)
        if self.issues.pop(key, None) is None:
            return

        self.async_schedule_save()
        self.hass.bus.async_fire_internal(
            EVENT_REPAIRS_ISSUE_REGISTRY_UPDATED,
            EventIssueRegistryUpdatedData(
                action="remove",
                domain=domain,
                issue_id=issue_id,
            ),
        )

    @callback
    @verify_event_loop_thread("issue_registry.async_keep")
    def async_keep(self, domain: str, issue_id: str) -> None:
        """Keep an issue in active refreshes, see async_keep_issue."""
        self._async_touch((domain, issue_id))

    @callback
    def _async_touch(self, key: tuple[str, str]) -> None:
        """Take a created, updated or deleted issue out of active refreshes."""
        for state in self._refreshes:
            state.untouched.discard(key)
        self._deferred_deletes.discard(key)

    @callback
    def async_clear_config_entry(self, config_entry_id: str) -> None:
        """Delete issues linked to a config entry."""
        for domain, issue_id in [
            key
            for key, issue in self.issues.items()
            if issue.config_entry_id == config_entry_id
        ]:
            self.async_delete(domain, issue_id)

    @callback
    def async_config_entry_disabled_by_changed(self, config_entry_id: str) -> None:
        """Fire update events for issues of a config entry which was (un)disabled.

        Issues of disabled config entries are hidden from issue listings, so
        listeners need to refresh them.
        """
        for issue in self.issues.values():
            if issue.config_entry_id != config_entry_id:
                continue
            self.hass.bus.async_fire_internal(
                EVENT_REPAIRS_ISSUE_REGISTRY_UPDATED,
                EventIssueRegistryUpdatedData(
                    action="update",
                    domain=issue.domain,
                    issue_id=issue.issue_id,
                ),
            )

    @callback
    def async_is_hidden(self, issue: IssueEntry) -> bool:
        """Return if an issue is hidden because its config entry is disabled."""
        if issue.config_entry_id is None:
            return False
        entry = self.hass.config_entries.async_get_entry(issue.config_entry_id)
        return entry is not None and entry.disabled_by is not None

    @callback
    @verify_event_loop_thread("issue_registry.async_ignore")
    def async_ignore(self, domain: str, issue_id: str, ignore: bool) -> IssueEntry:
        """Ignore issue."""
        old = self.issues[(domain, issue_id)]
        dismissed_version = ha_version if ignore else None
        if old.dismissed_version == dismissed_version:
            return old

        issue = self.issues[(domain, issue_id)] = dataclasses.replace(
            old,
            dismissed_version=dismissed_version,
        )

        self.async_schedule_save()
        self.hass.bus.async_fire_internal(
            EVENT_REPAIRS_ISSUE_REGISTRY_UPDATED,
            EventIssueRegistryUpdatedData(
                action="update",
                domain=domain,
                issue_id=issue_id,
            ),
        )

        return issue

    @callback
    @verify_event_loop_thread("issue_registry.async_refresh_issues")
    def async_refresh_issues(
        self,
        domain: str,
        *,
        issue_id_pattern: str | re.Pattern[str] | None = None,
        issue_ids: Iterable[str] | None = None,
        config_entry_id: str | None = None,
    ) -> IssuesRefresh:
        """Begin a refresh of a set of issues, see the async_refresh_issues helper."""
        if issue_id_pattern is not None and issue_ids is not None:
            raise ValueError("At most one of issue_id_pattern and issue_ids is allowed")
        if issue_ids is not None:
            candidates = {
                key
                for issue_id in issue_ids
                if (key := (domain, issue_id)) in self.issues
            }
        elif issue_id_pattern is None:
            candidates = {key for key in self.issues if key[0] == domain}
        else:
            pattern = re.compile(issue_id_pattern)
            candidates = {
                key for key in self.issues if key[0] == domain and pattern.match(key[1])
            }
        if config_entry_id is not None:
            candidates = {
                key
                for key in candidates
                if self.issues[key].config_entry_id == config_entry_id
            }
        return IssuesRefresh(
            self.hass, domain, self._refreshes, self._deferred_deletes, candidates
        )

    @callback
    def make_read_only(self) -> None:
        """Make the registry read-only.

        This method is irreversible.
        """
        self._store.make_read_only()

    @override
    async def _async_load(self) -> None:
        """Load the issue registry."""
        data = await self._store.async_load()

        issues: dict[tuple[str, str], IssueEntry] = {}

        if isinstance(data, dict):
            for issue in data["issues"]:
                created = cast(datetime, dt_util.parse_datetime(issue["created"]))
                if issue["is_persistent"]:
                    issues[(issue["domain"], issue["issue_id"])] = IssueEntry(
                        active=True,
                        breaks_in_ha_version=issue["breaks_in_ha_version"],
                        config_entry_id=issue["config_entry_id"],
                        created=created,
                        data=issue["data"],
                        dismissed_version=issue["dismissed_version"],
                        domain=issue["domain"],
                        is_fixable=issue["is_fixable"],
                        is_persistent=issue["is_persistent"],
                        issue_id=issue["issue_id"],
                        issue_domain=issue["issue_domain"],
                        learn_more_url=issue["learn_more_url"],
                        severity=issue["severity"],
                        translation_key=issue["translation_key"],
                        translation_placeholders=issue["translation_placeholders"],
                    )
                else:
                    issues[(issue["domain"], issue["issue_id"])] = IssueEntry(
                        active=False,
                        breaks_in_ha_version=None,
                        config_entry_id=issue["config_entry_id"],
                        created=created,
                        data=None,
                        dismissed_version=issue["dismissed_version"],
                        domain=issue["domain"],
                        is_fixable=None,
                        is_persistent=issue["is_persistent"],
                        issue_id=issue["issue_id"],
                        issue_domain=None,
                        learn_more_url=None,
                        severity=None,
                        translation_key=None,
                        translation_placeholders=None,
                    )

        # Assign before waiting, config entries update their issues while loading
        self.issues = issues

        if not any(issue.config_entry_id is not None for issue in issues.values()):
            return

        # Config entries load concurrently with the issue registry
        await self.hass.config_entries.async_wait_initialized()
        for domain, issue_id in [
            key
            for key, issue in self.issues.items()
            if issue.config_entry_id is not None
            and self.hass.config_entries.async_get_entry(issue.config_entry_id) is None
        ]:
            self.async_delete(domain, issue_id)

    @callback
    @override
    def _data_to_save(self) -> dict[str, list[dict[str, str | None]]]:
        """Return data of issue registry to store in a file."""
        data = {}

        data["issues"] = [entry.to_json() for entry in self.issues.values()]

        return data


@callback
@singleton(DATA_REGISTRY)
def async_get(hass: HomeAssistant) -> IssueRegistry:
    """Get issue registry."""
    return IssueRegistry(hass)


async def async_load(
    hass: HomeAssistant,
    *,
    read_only: bool = False,
    load_empty: bool = False,
) -> None:
    """Load issue registry."""
    ir = async_get(hass)
    if read_only:  # only used in for check config script
        ir.make_read_only()
    await ir.async_load(load_empty=load_empty)


@callback
def async_create_issue(
    hass: HomeAssistant,
    domain: str,
    issue_id: str,
    *,
    breaks_in_ha_version: str | None = None,
    config_entry_id: str | None = None,
    data: dict[str, str | int | float | None] | None = None,
    is_fixable: bool,
    is_persistent: bool = False,
    issue_domain: str | None = None,
    learn_more_url: str | None = None,
    severity: IssueSeverity,
    translation_key: str,
    translation_placeholders: dict[str, str] | None = None,
) -> None:
    """Create an issue, or replace an existing one."""
    # Verify the breaks_in_ha_version is a valid version string
    if breaks_in_ha_version:
        AwesomeVersion(
            breaks_in_ha_version,
            ensure_strategy=AwesomeVersionStrategy.CALVER,
        )

    issue_registry = async_get(hass)
    issue_registry.async_get_or_create(
        domain,
        issue_id,
        breaks_in_ha_version=breaks_in_ha_version,
        config_entry_id=config_entry_id,
        data=data,
        is_fixable=is_fixable,
        is_persistent=is_persistent,
        issue_domain=issue_domain,
        learn_more_url=learn_more_url,
        severity=severity,
        translation_key=translation_key,
        translation_placeholders=translation_placeholders,
    )


def create_issue(
    hass: HomeAssistant,
    domain: str,
    issue_id: str,
    *,
    breaks_in_ha_version: str | None = None,
    config_entry_id: str | None = None,
    data: dict[str, str | int | float | None] | None = None,
    is_fixable: bool,
    is_persistent: bool = False,
    issue_domain: str | None = None,
    learn_more_url: str | None = None,
    severity: IssueSeverity,
    translation_key: str,
    translation_placeholders: dict[str, str] | None = None,
) -> None:
    """Create an issue, or replace an existing one."""
    return run_callback_threadsafe(
        hass.loop,
        ft.partial(
            async_create_issue,
            hass,
            domain,
            issue_id,
            breaks_in_ha_version=breaks_in_ha_version,
            config_entry_id=config_entry_id,
            data=data,
            is_fixable=is_fixable,
            is_persistent=is_persistent,
            issue_domain=issue_domain,
            learn_more_url=learn_more_url,
            severity=severity,
            translation_key=translation_key,
            translation_placeholders=translation_placeholders,
        ),
    ).result()


@callback
def async_delete_issue(
    hass: HomeAssistant, domain: str, issue_id: str, *, defer_to_refresh: bool = False
) -> None:
    """Delete an issue.

    It is not an error to delete an issue that does not exist.

    With defer_to_refresh, an issue in the set of an active refresh is left for that
    refresh to delete, so it survives if it is created or kept again while the
    refresh runs. Otherwise it is deleted immediately. This is meant for entities
    removed during a reload, which may create the issue again.
    """
    issue_registry = async_get(hass)
    issue_registry.async_delete(domain, issue_id, defer_to_refresh=defer_to_refresh)


def delete_issue(hass: HomeAssistant, domain: str, issue_id: str) -> None:
    """Delete an issue.

    It is not an error to delete an issue that does not exist.
    """
    return run_callback_threadsafe(
        hass.loop, async_delete_issue, hass, domain, issue_id
    ).result()


@callback
def async_refresh_issues(
    hass: HomeAssistant,
    domain: str,
    *,
    issue_id_pattern: str | re.Pattern[str] | None = None,
    issue_ids: Iterable[str] | None = None,
    config_entry_id: str | None = None,
) -> IssuesRefresh:
    """Begin a refresh of a set of issues.

    When the refresh finishes, issues in the set which were not created, updated,
    deleted or kept since it began are deleted. Issues which are still valid thus
    keep user customizations such as the ignore flag.

    The set is selected by issue_id_pattern, a regular expression matched from the
    start of the issue id, or by issue_ids, and can be narrowed down to the issues
    linked to config_entry_id. Without issue_id_pattern and issue_ids, the set is
    all issues of the domain.

    The returned object is a context manager which finishes the refresh on a clean
    exit and cancels it if an exception is raised.
    """
    return async_get(hass).async_refresh_issues(
        domain,
        issue_id_pattern=issue_id_pattern,
        issue_ids=issue_ids,
        config_entry_id=config_entry_id,
    )


@callback
def async_keep_issue(hass: HomeAssistant, domain: str, issue_id: str) -> None:
    """Keep an issue in all active refreshes without creating or updating it.

    This has the same effect on active refreshes as creating the issue again
    unchanged, including dropping a deferred delete. It allows code which can't
    tell whether an issue is still valid to keep it without access to the refresh
    object. If no active refresh has the issue in its set, nothing happens.
    """
    async_get(hass).async_keep(domain, issue_id)


@callback
def async_ignore_issue(
    hass: HomeAssistant, domain: str, issue_id: str, ignore: bool
) -> None:
    """Ignore an issue.

    Will raise if the issue does not exist.
    """
    issue_registry = async_get(hass)
    issue_registry.async_ignore(domain, issue_id, ignore)
