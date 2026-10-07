"""Provide common pytest fixtures."""

from collections.abc import AsyncGenerator, Callable, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.remember_the_milk.const import DOMAIN
from homeassistant.core import HomeAssistant

from .const import CREATE_ENTRY_DATA, PROFILE, TOKEN_RESPONSE

from tests.common import MockConfigEntry


@pytest.fixture
def ignore_missing_translations(request: pytest.FixtureRequest) -> list[str]:
    """Ignore translations for the per-account services registered at runtime.

    The services are only registered when the integration is set up, so only
    ignore them for the test modules that load the integration.
    """
    if request.module.__name__.endswith((".test_entity", ".test_init", ".test_todo")):
        return [
            f"component.{DOMAIN}.services.{PROFILE}_create_task.",
            f"component.{DOMAIN}.services.{PROFILE}_complete_task.",
        ]
    return []


@pytest.fixture(name="client")
def client_fixture() -> Generator[MagicMock]:
    """Create a mock client."""
    with (
        patch(
            "homeassistant.components.remember_the_milk.AioRTMClient",
        ) as client_class,
        patch(
            "homeassistant.components.remember_the_milk.config_flow.Auth.check_token",
            AsyncMock(return_value=TOKEN_RESPONSE),
        ),
        patch(
            "homeassistant.components.remember_the_milk.config_flow.Auth.authenticate_desktop",
            AsyncMock(return_value=("https://test-url.com", "test-frob")),
        ),
        patch(
            "homeassistant.components.remember_the_milk.config_flow.Auth.get_token",
            AsyncMock(return_value=TOKEN_RESPONSE),
        ),
    ):
        client = client_class.return_value
        client.rtm.api.check_token = AsyncMock(return_value=TOKEN_RESPONSE)
        timelines = MagicMock()
        timelines.timeline = 1234
        client.rtm.timelines.create = AsyncMock(return_value=timelines)
        task_modified_response = MagicMock()
        task_modified_response.task_list.id = 1
        task_modified_response.task_list.taskseries = []
        task_series = MagicMock()
        task_series.id = 2
        task_series.task = []
        task = MagicMock()
        task.id = 3
        task_series.task.append(task)
        task_modified_response.task_list.taskseries.append(task_series)
        client.rtm.tasks.add = AsyncMock(return_value=task_modified_response)
        client.rtm.tasks.complete = AsyncMock(return_value=task_modified_response)
        client.rtm.tasks.uncomplete = AsyncMock(  # codespell:ignore uncomplete
            return_value=task_modified_response
        )
        client.rtm.tasks.delete = AsyncMock(return_value=task_modified_response)
        client.rtm.tasks.set_name = AsyncMock(return_value=task_modified_response)
        client.rtm.tasks.set_due_date = AsyncMock(return_value=task_modified_response)
        tasks_response = MagicMock()
        tasks_response.tasks.task_list = []
        client.rtm.tasks.get_list = AsyncMock(return_value=tasks_response)
        note_response = MagicMock()
        client.rtm.tasks.notes.add = AsyncMock(return_value=note_response)
        client.rtm.tasks.notes.edit = AsyncMock(return_value=note_response)
        client.rtm.tasks.notes.delete = AsyncMock(return_value=note_response)
        lists_response = MagicMock()
        lists_response.lists = []
        client.rtm.lists.get_list = AsyncMock(return_value=lists_response)
        list_add_response = MagicMock()
        list_add_response.list.id = 42
        client.rtm.lists.add = AsyncMock(return_value=list_add_response)
        client.rtm.lists.set_name = AsyncMock(return_value=MagicMock())
        client.rtm.lists.delete = AsyncMock(return_value=MagicMock())

        yield client


@pytest.fixture
async def storage(hass: HomeAssistant, client) -> AsyncGenerator[MagicMock]:
    """Mock the config storage."""
    with patch(
        "homeassistant.components.remember_the_milk.RememberTheMilkConfiguration"
    ) as storage_class:
        storage = storage_class.return_value
        storage.get_rtm_id.return_value = None
        storage.get_token.return_value = "test-token"
        yield storage


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a mock config entry."""
    entry = MockConfigEntry(
        data=CREATE_ENTRY_DATA,
        domain=DOMAIN,
        unique_id="1234567",
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def make_rtm_list_mock() -> Callable[..., MagicMock]:
    """Return a factory that creates a single RTM list mock with optional flags."""

    def factory(
        list_id: int,
        name: str,
        *,
        smart: bool = False,
        archived: bool = False,
        locked: bool = False,
        deleted: bool = False,
    ) -> MagicMock:
        lst = MagicMock()
        lst.id = list_id
        lst.name = name
        lst.smart = smart
        lst.archived = archived
        lst.locked = locked
        lst.deleted = deleted
        return lst

    return factory


@pytest.fixture
def rtm_list_mock(
    client: MagicMock, make_rtm_list_mock: Callable[..., MagicMock]
) -> Callable[[int, str], MagicMock]:
    """Return a helper that configures get_list to return a single standard list."""

    def factory(list_id: int, name: str) -> MagicMock:
        lst = make_rtm_list_mock(list_id, name)
        response = MagicMock()
        response.lists = [lst]
        client.rtm.lists.get_list.return_value = response
        return lst

    return factory


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.remember_the_milk.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry
