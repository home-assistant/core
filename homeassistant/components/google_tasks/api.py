"""API for Google Tasks bound to Home Assistant OAuth."""

import json
import logging
from typing import Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import Resource, build
from googleapiclient.errors import HttpError
from googleapiclient.http import BatchHttpRequest, HttpRequest

from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from .exceptions import GoogleTasksApiError

_LOGGER = logging.getLogger(__name__)

MAX_TASK_RESULTS = 100


def _raise_if_error(result: Any | dict[str, Any]) -> None:
    """Raise a GoogleTasksApiError if the response contains an error."""
    if not isinstance(result, dict):
        raise GoogleTasksApiError(
            f"Google Tasks API replied with unexpected response: {result}"
        )
    if error := result.get("error"):
        message = error.get("message", "Unknown Error")
        raise GoogleTasksApiError(f"Google Tasks API response: {message}")


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
        result = await self._execute(cmd)
        return result["items"]

    async def list_tasks(self, task_list_id: str) -> list[dict[str, Any]]:
        """Get all Task resources for the task list."""
        service = await self._get_service()
        cmd: HttpRequest = service.tasks().list(
            tasklist=task_list_id, maxResults=MAX_TASK_RESULTS
        )
        result = await self._execute(cmd)
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
        await self._execute(cmd)

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
        await self._execute(cmd)

    async def delete(
        self,
        task_list_id: str,
        task_ids: list[str],
    ) -> None:
        """Delete a task resources."""
        service = await self._get_service()
        batch: BatchHttpRequest = service.new_batch_http_request()

        def response_handler(_, response, exception: HttpError) -> None:
            if exception is not None:
                raise GoogleTasksApiError(
                    f"Google Tasks API responded with error ({exception.status_code})"
                ) from exception
            data = json.loads(response)
            _raise_if_error(data)

        for task_id in task_ids:
            batch.add(
                service.tasks().delete(
                    tasklist=task_list_id,
                    task=task_id,
                ),
                request_id=task_id,
                callback=response_handler,
            )
        await self._execute(batch)

    async def move(
        self,
        task_list_id: str,
        task_id: str,
        previous: str | None,
    ) -> None:
        """Move a task resource to a specific position within the task list."""
        service = await self._get_service()
        cmd: HttpRequest = service.tasks().move(
            tasklist=task_list_id,
            task=task_id,
            previous=previous,
        )
        await self._execute(cmd)

    async def _execute(self, request: HttpRequest | BatchHttpRequest) -> Any:
        try:
            result = await self._hass.async_add_executor_job(request.execute)
        except HttpError as err:
            raise GoogleTasksApiError(
                f"Google Tasks API responded with error ({err.status_code})"
            ) from err
        if result:
            _raise_if_error(result)
        return result
