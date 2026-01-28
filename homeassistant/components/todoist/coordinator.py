"""DataUpdateCoordinator for the Todoist component."""

from collections.abc import AsyncGenerator
from datetime import timedelta
import logging
from typing import TypeVar

from todoist_api_python.api_async import TodoistAPIAsync
from todoist_api_python.models import Label, Project, Section, Task

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

T = TypeVar("T")


async def flatten_async_pages(
    pages: AsyncGenerator[list[T]],
) -> list[T]:
    """Flatten paginated results from an async generator."""
    all_items: list[T] = []
    async for page in pages:
        all_items.extend(page)
    return all_items


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
            tasks_async = await self.api.get_tasks()
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        return await flatten_async_pages(tasks_async)

    async def async_get_projects(self) -> list[Project]:
        """Return todoist projects fetched at most once."""
        if self._projects is None:
            projects_async = await self.api.get_projects()
            self._projects = await flatten_async_pages(projects_async)
        return self._projects

    async def async_get_sections(self, project_id: str) -> list[Section]:
        """Return todoist sections for a given project ID."""
        sections_async = await self.api.get_sections(project_id=project_id)
        return await flatten_async_pages(sections_async)

    async def async_get_labels(self) -> list[Label]:
        """Return todoist labels fetched at most once."""
        if self._labels is None:
            labels_async = await self.api.get_labels()
            self._labels = await flatten_async_pages(labels_async)
        return self._labels
