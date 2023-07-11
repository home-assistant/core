"""DataUpdateCoordinator for the Todoist component."""
from datetime import timedelta
import logging

from todoist_api_python.api_async import TodoistAPIAsync
from todoist_api_python.models import Task

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed


class TodoistCoordinator(DataUpdateCoordinator[list[Task]]):
    """Coordinator for updating task data from Todoist."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        update_interval: timedelta,
        api: TodoistAPIAsync,
    ) -> None:
        """Initialize the Todoist coordinator."""
        super().__init__(hass, logger, name="Todoist", update_interval=update_interval)
        self.api = api

    async def _async_update_data(self) -> list[Task]:
        """Fetch tasks from the Todoist API."""
        try:
            return await self.api.get_tasks()
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
