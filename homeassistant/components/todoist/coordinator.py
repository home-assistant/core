"""DataUpdateCoordinator for the Todoist component."""

from datetime import UTC, datetime, timedelta
import logging

from todoist_api_python.api_async import TodoistAPIAsync
from todoist_api_python.models import Label, Project, Section, Task

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed


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

    async def _async_update_data(self) -> list[Task]:
        """Fetch tasks from the Todoist API."""
        try:
            # Collect active tasks
            active_tasks: list[Task] = []
            async for task_page in await self.api.get_tasks():
                active_tasks.extend(task_page)

            # Collect completed tasks (optional date range)
            since = datetime(2025, 11, 1, tzinfo=UTC)
            until = datetime(2025, 11, 14, 23, 59, 59, tzinfo=UTC)
            completed_tasks: list[Task] = []
            async for task_page in await self.api.get_completed_tasks_by_due_date(
                since=since, until=until
            ):
                completed_tasks.extend(task_page)

            return active_tasks + completed_tasks
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    async def async_get_projects(self) -> list[Project]:
        """Return Todoist projects fetched at most once."""
        if self._projects is None:
            raw = await self.api.get_projects()
            projects: list[Project] = []

            # If raw itself is an async generator (yielding pages/lists)
            if hasattr(raw, "__aiter__"):
                async for item in raw:
                    if isinstance(item, list):
                        projects.extend(item)
                    elif isinstance(item, Project):
                        projects.append(item)
            # If raw is a normal list of Project objects
            elif isinstance(raw, list):
                projects = raw
            # If raw is a single Project object
            elif isinstance(raw, Project):
                projects.append(raw)
            else:
                # Defensive: unexpected type
                raise TypeError(f"Unexpected type from get_projects(): {type(raw)}")

            self._projects = projects

        return self._projects

    async def async_get_sections(self, project_id: str) -> list[Section]:
        """Return Todoist sections for a given project ID."""
        raw = await self.api.get_sections(project_id=project_id)
        sections: list[Section] = []

        # Case 1: async generator (new API behaviour)
        if hasattr(raw, "__aiter__"):
            async for item in raw:
                if isinstance(item, list):
                    sections.extend(item)
                elif isinstance(item, Section):
                    sections.append(item)
        # Case 2: returned a normal list
        elif isinstance(raw, list):
            sections = raw
        # Case 3: single section (unlikely, but safe)
        elif isinstance(raw, Section):
            sections.append(raw)
        else:
            raise TypeError(f"Unexpected type from get_sections(): {type(raw)}")
        return sections

    async def async_get_labels(self) -> list[Label]:
        """Return todoist labels fetched at most once."""
        if self._labels is None:
            raw = await self.api.get_labels()
            labels: list[Label] = []

            # If it's an async generator, iterate over it
            if hasattr(raw, "__aiter__"):
                async for item in raw:
                    if isinstance(item, list):
                        labels.extend(item)
                    elif isinstance(item, Label):
                        labels.append(item)
            # If raw is a normal list of Project objects
            elif isinstance(raw, list):
                labels = raw
            # If raw is a single Project object
            elif isinstance(raw, Label):
                labels.append(raw)
            else:
                # Defensive: unexpected type
                raise TypeError(f"Unexpected type from get_projects(): {type(raw)}")

            self._labels = labels
        return self._labels
