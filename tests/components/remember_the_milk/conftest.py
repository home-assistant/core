"""Provide common pytest fixtures."""

from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.core import HomeAssistant

from .const import TOKEN


@pytest.fixture(name="auth", autouse=True)
def auth_fixture() -> Generator[MagicMock]:
    """Create a mock auth."""
    with patch(
        "homeassistant.components.remember_the_milk.Auth", autospec=True
    ) as auth_class:
        auth = auth_class.return_value
        yield auth


@pytest.fixture(name="client")
def client_fixture() -> Generator[MagicMock]:
    """Create a mock client."""
    with patch(
        "homeassistant.components.remember_the_milk.AioRTMClient"
    ) as client_class:
        client = client_class.return_value
        client.rtm.api.check_token = AsyncMock(
            return_value={
                "token": "test-token",
                "perms": "delete",
                "user": {
                    "id": "1234567",
                    "username": "johnsmith",
                    "fullname": "John Smith",
                },
            }
        )
        timelines = MagicMock()
        timelines.timeline = 1234
        client.rtm.timelines.create = AsyncMock(return_value=timelines)
        response = MagicMock()
        response.task_list.id = 1
        task_series = MagicMock()
        task_series.id = 2
        task = MagicMock()
        task.id = 3
        task_series.task = [task]
        response.task_list.taskseries = [task_series]
        client.rtm.tasks.add = AsyncMock(return_value=response)
        client.rtm.tasks.complete = AsyncMock(return_value=response)
        client.rtm.tasks.set_name = AsyncMock(return_value=response)

        yield client


@pytest.fixture
async def storage(hass: HomeAssistant, client) -> AsyncGenerator[MagicMock]:
    """Mock the config storage."""
    with patch(
        "homeassistant.components.remember_the_milk.RememberTheMilkConfiguration",
        autospec=True,
    ) as storage_class:
        storage = storage_class.return_value
        storage.get_token.return_value = TOKEN
        storage.get_rtm_id.return_value = None
        yield storage
