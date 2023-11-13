"""API for Google Tasks bound to Home Assistant OAuth."""

from typing import Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import Resource, build
from googleapiclient.http import HttpRequest

from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

MAX_TASK_RESULTS = 100


class AsyncConfigEntryAuth:
    """Provide Google Tasks authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        hass: HomeAssistant,
        oauth2_session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Initialize Google Tasks Auth."""
        self._hass = hass
        self._oauth_session = oauth2_session

    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        if not self._oauth_session.valid_token:
            await self._oauth_session.async_ensure_token_valid()
        return self._oauth_session.token[CONF_ACCESS_TOKEN]

    async def _get_service(self) -> Resource:
        """Get current resource."""
        token = await self.async_get_access_token()
        return build("tasks", "v1", credentials=Credentials(token=token))

    async def list_task_lists(self) -> list[dict[str, Any]]:
        """Get all TaskList resources."""
        service = await self._get_service()
        cmd: HttpRequest = service.tasklists().list()
        result = await self._hass.async_add_executor_job(cmd.execute)
        return result["items"]

    async def list_tasks(self, task_list_id: str) -> list[dict[str, Any]]:
        """Get all Task resources for the task list."""
        service = await self._get_service()
        cmd: HttpRequest = service.tasks().list(
            tasklist=task_list_id, maxResults=MAX_TASK_RESULTS
        )
        result = await self._hass.async_add_executor_job(cmd.execute)
        return result["items"]

    async def insert(
        self,
        task_list_id: str,
        task: dict[str, Any],
    ) -> None:
        """Create a new Task resource on the task list."""
        service = await self._get_service()
        cmd: HttpRequest = service.tasks().insert(
            tasklist=task_list_id,
            body=task,
        )
        await self._hass.async_add_executor_job(cmd.execute)

    async def patch(
        self,
        task_list_id: str,
        task_id: str,
        task: dict[str, Any],
    ) -> None:
        """Update a task resource."""
        service = await self._get_service()
        cmd: HttpRequest = service.tasks().patch(
            tasklist=task_list_id,
            task=task_id,
            body=task,
        )
        await self._hass.async_add_executor_job(cmd.execute)
