"""Persistently store issues raised by integrations."""
from __future__ import annotations

import dataclasses
from datetime import datetime
from enum import StrEnum
import functools as ft
from typing import Any, cast

from awesomeversion import AwesomeVersion, AwesomeVersionStrategy

from homeassistant.const import __version__ as ha_version
from homeassistant.core import HomeAssistant, callback
from homeassistant.util.async_ import run_callback_threadsafe
import homeassistant.util.dt as dt_util

from .storage import Store

DATA_REGISTRY = "issue_registry"
EVENT_REPAIRS_ISSUE_REGISTRY_UPDATED = "repairs_issue_registry_updated"
STORAGE_KEY = "repairs.issue_registry"
STORAGE_VERSION_MAJOR = 1
STORAGE_VERSION_MINOR = 2
SAVE_DELAY = 10


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

    async def _async_migrate_func(
        self, old_major_version: int, old_minor_version: int, old_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Migrate to the new version."""
        if old_major_version == 1 and old_minor_version < 2:
            # Version 1.2 adds is_persistent
            for issue in old_data["issues"]:
                issue["is_persistent"] = False
        return old_data


class IssueRegistry:
    """Class to hold a registry of issues."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the issue registry."""
        self.hass = hass
        self.issues: dict[tuple[str, str], IssueEntry] = {}
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
    def async_get_or_create(
        self,
        domain: str,
        issue_id: str,
        *,
        breaks_in_ha_version: str | None = None,
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

        if (issue := self.async_get_issue(domain, issue_id)) is None:
            issue = IssueEntry(
                active=True,
                breaks_in_ha_version=breaks_in_ha_version,
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
            self.hass.bus.async_fire(
                EVENT_REPAIRS_ISSUE_REGISTRY_UPDATED,
                {"action": "create", "domain": domain, "issue_id": issue_id},
            )
        else:
            issue = self.issues[(domain, issue_id)] = dataclasses.replace(
                issue,
                active=True,
                breaks_in_ha_version=breaks_in_ha_version,
                data=data,
                is_fixable=is_fixable,
                is_persistent=is_persistent,
                issue_domain=issue_domain,
                learn_more_url=learn_more_url,
                severity=severity,
                translation_key=translation_key,
                translation_placeholders=translation_placeholders,
            )
            self.hass.bus.async_fire(
                EVENT_REPAIRS_ISSUE_REGISTRY_UPDATED,
                {"action": "update", "domain": domain, "issue_id": issue_id},
            )

        return issue

    @callback
    def async_delete(self, domain: str, issue_id: str) -> None:
        """Delete issue."""
        if self.issues.pop((domain, issue_id), None) is None:
            return

        self.async_schedule_save()
        self.hass.bus.async_fire(
            EVENT_REPAIRS_ISSUE_REGISTRY_UPDATED,
            {"action": "remove", "domain": domain, "issue_id": issue_id},
        )

    @callback
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
        self.hass.bus.async_fire(
            EVENT_REPAIRS_ISSUE_REGISTRY_UPDATED,
            {"action": "update", "domain": domain, "issue_id": issue_id},
        )

        return issue

    async def async_load(self) -> None:
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

        self.issues = issues

    @callback
    def async_schedule_save(self) -> None:
        """Schedule saving the issue registry."""
        self._store.async_delay_save(self._data_to_save, SAVE_DELAY)

    @callback
    def _data_to_save(self) -> dict[str, list[dict[str, str | None]]]:
        """Return data of issue registry to store in a file."""
        data = {}

        data["issues"] = [entry.to_json() for entry in self.issues.values()]

        return data


@callback
def async_get(hass: HomeAssistant) -> IssueRegistry:
    """Get issue registry."""
    return cast(IssueRegistry, hass.data[DATA_REGISTRY])


async def async_load(hass: HomeAssistant) -> None:
    """Load issue registry."""
    assert DATA_REGISTRY not in hass.data
    hass.data[DATA_REGISTRY] = IssueRegistry(hass)
    await hass.data[DATA_REGISTRY].async_load()


@callback
def async_create_issue(
    hass: HomeAssistant,
    domain: str,
    issue_id: str,
    *,
    breaks_in_ha_version: str | None = None,
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
def async_delete_issue(hass: HomeAssistant, domain: str, issue_id: str) -> None:
    """Delete an issue.

    It is not an error to delete an issue that does not exist.
    """
    issue_registry = async_get(hass)
    issue_registry.async_delete(domain, issue_id)


def delete_issue(hass: HomeAssistant, domain: str, issue_id: str) -> None:
    """Delete an issue.

    It is not an error to delete an issue that does not exist.
    """
    return run_callback_threadsafe(
        hass.loop, async_delete_issue, hass, domain, issue_id
    ).result()


@callback
def async_ignore_issue(
    hass: HomeAssistant, domain: str, issue_id: str, ignore: bool
) -> None:
    """Ignore an issue.

    Will raise if the issue does not exist.
    """
    issue_registry = async_get(hass)
    issue_registry.async_ignore(domain, issue_id, ignore)
