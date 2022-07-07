"""Persistently store issues raised by integrations."""
from __future__ import annotations

import dataclasses
from typing import cast

from homeassistant.const import __version__ as ha_version
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store

DATA_REGISTRY = "issue_registry"
STORAGE_KEY = "resolution_center.issue_registry"
STORAGE_VERSION = 1
SAVE_DELAY = 10


@dataclasses.dataclass(frozen=True)
class IssueEntry:
    """Issue Registry Entry."""

    dismissed_version: str | None
    domain: str
    issue_id: str

    @property
    def is_dismissed(self) -> bool:
        """Return True if an issue is dismissed."""
        return self.dismissed_version is not None


class IssueRegistry:
    """Class to hold a registry of issues."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the issue registry."""
        self.hass = hass
        self.issues: dict[tuple[str, str], IssueEntry] = {}
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY, atomic_writes=True)

    @callback
    def async_get_issue(self, domain: str, issue_id: str) -> IssueEntry | None:
        """Get issue by id."""
        return self.issues.get((domain, issue_id))

    @callback
    def async_get_or_create(self, domain: str, issue_id: str) -> IssueEntry:
        """Get issue. Create if it doesn't exist."""

        if (issue := self.async_get_issue(domain, issue_id)) is None:
            issue = IssueEntry(
                dismissed_version=None,
                domain=domain,
                issue_id=issue_id,
            )
            self.issues[(domain, issue_id)] = issue
            self.async_schedule_save()

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
        """Load the area registry."""
        data = await self._store.async_load()

        issues: dict[tuple[str, str], IssueEntry] = {}

        if isinstance(data, dict):
            for issue in data["issues"]:
                issues[(issue["domain"], issue["issue_id"])] = IssueEntry(
                    dismissed_version=issue["dismissed_version"],
                    domain=issue["domain"],
                    issue_id=issue["issue_id"],
                )

        self.issues = issues

    @callback
    def async_schedule_save(self) -> None:
        """Schedule saving the area registry."""
        self._store.async_delay_save(self._data_to_save, SAVE_DELAY)

    @callback
    def _data_to_save(self) -> dict[str, list[dict[str, str | None]]]:
        """Return data of area registry to store in a file."""
        data = {}

        data["issues"] = [dataclasses.asdict(entry) for entry in self.issues.values()]

        return data


@callback
def async_get(hass: HomeAssistant) -> IssueRegistry:
    """Get area registry."""
    return cast(IssueRegistry, hass.data[DATA_REGISTRY])


async def async_load(hass: HomeAssistant) -> None:
    """Load area registry."""
    assert DATA_REGISTRY not in hass.data
    hass.data[DATA_REGISTRY] = IssueRegistry(hass)
    await hass.data[DATA_REGISTRY].async_load()
