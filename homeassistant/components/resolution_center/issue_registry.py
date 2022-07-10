"""Persistently store issues raised by integrations."""
from __future__ import annotations

import dataclasses
from typing import Optional, cast

from homeassistant.const import __version__ as ha_version
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store

from .models import IssueSeverity

DATA_REGISTRY = "issue_registry"
STORAGE_KEY = "resolution_center.issue_registry"
STORAGE_VERSION = 1
SAVE_DELAY = 10
SAVED_FIELDS = ("dismissed_version", "domain", "issue_id")


@dataclasses.dataclass(frozen=True)
class IssueEntry:
    """Issue Registry Entry."""

    active: bool
    breaks_in_ha_version: str | None
    dismissed_version: str | None
    domain: str
    issue_id: str
    learn_more_url: str | None
    severity: IssueSeverity | None
    translation_key: str | None
    translation_placeholders: dict[str, str] | None


class IssueRegistry:
    """Class to hold a registry of issues."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the issue registry."""
        self.hass = hass
        self.issues: dict[tuple[str, str], IssueEntry] = {}
        self._store = Store[dict[str, list[dict[str, Optional[str]]]]](
            hass, STORAGE_VERSION, STORAGE_KEY, atomic_writes=True
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
                dismissed_version=None,
                domain=domain,
                issue_id=issue_id,
                learn_more_url=learn_more_url,
                severity=severity,
                translation_key=translation_key,
                translation_placeholders=translation_placeholders,
            )
            self.issues[(domain, issue_id)] = issue
            self.async_schedule_save()
        else:
            issue = self.issues[(domain, issue_id)] = dataclasses.replace(
                issue,
                active=True,
                breaks_in_ha_version=breaks_in_ha_version,
                learn_more_url=learn_more_url,
                severity=severity,
                translation_key=translation_key,
                translation_placeholders=translation_placeholders,
            )

        return issue

    @callback
    def async_delete(self, domain: str, issue_id: str) -> None:
        """Delete issue."""
        if self.issues.pop((domain, issue_id), None) is None:
            return

        self.async_schedule_save()

    @callback
    def async_dismiss(self, domain: str, issue_id: str) -> IssueEntry:
        """Dismiss issue."""
        old = self.issues[(domain, issue_id)]
        if old.dismissed_version == ha_version:
            return old

        issue = self.issues[(domain, issue_id)] = dataclasses.replace(
            old,
            dismissed_version=ha_version,
        )

        self.async_schedule_save()

        return issue

    async def async_load(self) -> None:
        """Load the issue registry."""
        data = await self._store.async_load()

        issues: dict[tuple[str, str], IssueEntry] = {}

        if isinstance(data, dict):
            for issue in data["issues"]:
                assert issue["domain"] and issue["issue_id"]
                issues[(issue["domain"], issue["issue_id"])] = IssueEntry(
                    active=False,
                    breaks_in_ha_version=None,
                    dismissed_version=issue["dismissed_version"],
                    domain=issue["domain"],
                    issue_id=issue["issue_id"],
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

        data["issues"] = [
            {field: getattr(entry, field) for field in SAVED_FIELDS}
            for entry in self.issues.values()
        ]

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
