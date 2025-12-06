"""DataUpdateCoordinator for the Todoist component."""

from __future__ import annotations

import logging
from datetime import date, timedelta

from todoist_api_python.api_async import TodoistAPIAsync
from todoist_api_python.models import Label, Project, Section, Task

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .task_filter import filter_tasks



class TodoistCoordinator(DataUpdateCoordinator[list[Task]]):
    """Coordinator for updating task data from Todoist."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        entry: ConfigEntry | None,
        update_interval: timedelta,
        api: TodoistAPIAsync,
        token: str,
    ) -> None:
        """Initialize the Todoist coordinator."""
        super().__init__(
            hass,
            logger,
            config_entry=entry,
            name="Todoist",
            update_interval=update_interval,
        )

        self.api = api
        self._projects: list[Project] | None = None
        self._labels: list[Label] | None = None
        self.token = token

        # Filtering configuration
        # Empty lists / None = no filtering.
        # Default: only high-priority tasks (3 and 4).
        self._filter_labels: list[str] = []          # Example: ["University"]
        self._filter_priorities: list[int] = [3, 4]
        self._filter_start_date: date | None = None
        self._filter_end_date: date | None = None

    async def _async_update_data(self) -> list[Task]:
        """Fetch tasks from Todoist and apply filtering."""
        try:
            tasks = await self.api.get_tasks()
        except Exception as err:
            # Any API failure is converted to UpdateFailed for the coordinator.
            raise UpdateFailed(f"Error communicating with API: {err}") from err

        # Apply backend filtering (labels, priorities, due range)
        return filter_tasks(
            tasks,
            labels=self._filter_labels,
            priorities=self._filter_priorities,
            start_date=self._filter_start_date,
            end_date=self._filter_end_date,
        )

    async def async_get_projects(self) -> list[Project]:
        """Return todoist projects fetched at most once."""
        if self._projects is None:
            self._projects = await self.api.get_projects()
        return self._projects

    async def async_get_sections(self, project_id: str) -> list[Section]:
        """Return todoist sections for a given project ID."""
        return await self.api.get_sections(project_id=project_id)

    async def async_get_labels(self) -> list[Label]:
        """Return todoist labels fetched at most once."""
        if self._labels is None:
            self._labels = await self.api.get_labels()
        return self._labels
