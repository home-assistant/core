"""Provide common pytest fixtures."""

from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.remember_the_milk.const import DOMAIN
from homeassistant.core import HomeAssistant

from .const import CREATE_ENTRY_DATA, TOKEN_RESPONSE

from tests.common import MockConfigEntry


@pytest.fixture(name="client")
def client_fixture() -> Generator[MagicMock]:
    """Create a mock client."""
    with patch(
        "homeassistant.components.remember_the_milk.AioRTMClient",
    ) as client_class:
        client = client_class.return_value
        client.rtm.api.check_token = AsyncMock(return_value=TOKEN_RESPONSE)
        timelines = MagicMock()
        timelines.timeline = 1234
        client.rtm.timelines.create = AsyncMock(return_value=timelines)
        response = MagicMock()
        response.task_list.id = 1
        response.task_list.taskseries = []
        task_series = MagicMock()
        task_series.id = 2
        task_series.task = []
        task = MagicMock()
        task.id = 3
        task_series.task.append(task)
        response.task_list.taskseries.append(task_series)
        client.rtm.tasks.add = AsyncMock(return_value=response)
        client.rtm.tasks.complete = AsyncMock(return_value=response)
        client.rtm.tasks.set_name = AsyncMock(return_value=response)

        yield client


@pytest.fixture
async def storage(hass: HomeAssistant, client) -> AsyncGenerator[MagicMock]:
    """Mock the config storage."""
    with patch(
        "homeassistant.components.remember_the_milk.RememberTheMilkConfiguration"
    ) as storage_class:
        storage = storage_class.return_value
        storage.get_rtm_id.return_value = None
        yield storage


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a mock config entry."""
    entry = MockConfigEntry(
        data=CREATE_ENTRY_DATA,
        domain=DOMAIN,
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.remember_the_milk.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry
