"""Common fixtures for the Famn tests."""

import asyncio
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
from famn_sdk import (
    CalendarEvent,
    CalendarPaginateResponse,
    DeviceTokenResponse,
    LeaderboardEntry,
    ListItem,
    ListModel,
    MealSlotPaginateResponse,
    SpaceMember,
    SpaceSeasonSummary,
    StartDevicePairingResponse,
    TaskItem,
    TaskListPaginateResponse,
)
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.famn.const import CONF_REFRESH_TOKEN, DOMAIN
from homeassistant.const import CONF_DEVICE_ID

from tests.common import (
    MockConfigEntry,
    load_json_array_fixture,
    load_json_object_fixture,
)

SPACE_ID = "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d"
DEVICE_ID = "7a6b5c4d-3e2f-4a1b-9c8d-7e6f5a4b3001"
CHORES_LIST_ID = "3f5b1c26-9a5b-4a41-9b3e-2c1a9b0f1001"
TODOS_LIST_ID = "3f5b1c26-9a5b-4a41-9b3e-2c1a9b0f1003"
CALENDAR_ID = "9c8d7e6f-5a4b-4c3d-8e2f-1a0b9c8d7001"
SHOPPING_LIST_ID = "5a4b3c2d-1e0f-4a9b-8c7d-6e5f4a3b2001"
PAIRING_SECRET = "mock-pairing-secret"


@pytest.fixture(autouse=True)
def frozen_time(freezer: FrozenDateTimeFactory) -> None:
    """Freeze the clock inside the validity of the token fixtures.

    The device token fixtures carry fixed expiry timestamps. On a clock that
    has drifted past them every request rotates the token again, which is
    never what a test means to exercise. Tests that need another moment move
    the clock on from here themselves.
    """
    freezer.move_to("2026-08-12T12:00:00Z")


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.famn.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Home Assistant",
        unique_id=SPACE_ID,
        data={
            CONF_REFRESH_TOKEN: "mock-refresh-token",
            CONF_DEVICE_ID: DEVICE_ID,
        },
    )


@pytest.fixture
def pairing_approved() -> asyncio.Event:
    """Event that releases the pairing poll, as the user approving in the app."""
    return asyncio.Event()


@pytest.fixture
def mock_device_api(pairing_approved: asyncio.Event) -> Generator[AsyncMock]:
    """Mock the Famn device API."""
    with (
        patch(
            "homeassistant.components.famn.api.DeviceApi", autospec=True
        ) as device_api,
        patch("homeassistant.components.famn.config_flow.DeviceApi", new=device_api),
        patch("homeassistant.components.famn.config_flow.FIRST_POLL_DELAY", 0),
        patch("homeassistant.components.famn.config_flow.POLL_INTERVAL", 0),
    ):
        client = device_api.return_value
        client.start_device_pairing_endpoint.return_value = (
            StartDevicePairingResponse.from_dict(
                load_json_object_fixture("pairing.json", DOMAIN)
            )
        )
        tokens = DeviceTokenResponse.from_dict(
            load_json_object_fixture("device_token.json", DOMAIN)
        )

        async def _poll(**kwargs: object) -> DeviceTokenResponse:
            await pairing_approved.wait()
            return client.pairing_result

        client.pairing_result = tokens
        client.poll_device_pairing_endpoint.side_effect = _poll
        client.rotate_device_refresh_token_endpoint.return_value = tokens
        yield client


@pytest.fixture
def mock_tasks_api() -> Generator[AsyncMock]:
    """Mock the Famn tasks API."""
    with patch(
        "homeassistant.components.famn.coordinator.TasksApi", autospec=True
    ) as tasks_api:
        client = tasks_api.return_value
        task_lists = TaskListPaginateResponse.from_dict(
            load_json_object_fixture("task_lists.json", DOMAIN)
        )

        async def _get_task_lists(
            *, task_type: str | None = None, **kwargs: object
        ) -> TaskListPaginateResponse:
            lists = [
                task_list
                for task_list in (task_lists.items or [])
                if task_list.task_type == task_type
            ]
            return TaskListPaginateResponse(
                items=lists, page=1, page_size=100, total=len(lists), total_pages=1
            )

        client.get_task_lists_endpoint.side_effect = _get_task_lists
        items = [
            TaskItem.from_dict(item)
            for item in load_json_array_fixture("task_items.json", DOMAIN)
        ]

        async def _get_task_items(
            task_list_id: str, *, completed: bool | None = None, **kwargs: object
        ) -> list[TaskItem]:
            return [item for item in items if item.task_list_id == task_list_id]

        client.get_task_items_endpoint.side_effect = _get_task_items
        yield client


@pytest.fixture
def mock_calendar_api() -> Generator[AsyncMock]:
    """Mock the Famn calendar API."""
    with patch(
        "homeassistant.components.famn.coordinator.CalendarApi", autospec=True
    ) as calendar_api:
        client = calendar_api.return_value
        client.get_calendars_endpoint.return_value = CalendarPaginateResponse.from_dict(
            load_json_object_fixture("calendars.json", DOMAIN)
        )
        events = [
            CalendarEvent.from_dict(event)
            for event in load_json_array_fixture("calendar_events.json", DOMAIN)
        ]

        async def _get_events(
            calendar_id: str, **kwargs: object
        ) -> list[CalendarEvent]:
            return [event for event in events if str(event.calendar_id) == calendar_id]

        client.get_calendar_events_endpoint.side_effect = _get_events
        yield client


@pytest.fixture
def mock_space_api() -> Generator[AsyncMock]:
    """Mock the Famn space API (XP leaderboard and season)."""
    with patch(
        "homeassistant.components.famn.coordinator.SpaceApi", autospec=True
    ) as space_api:
        client = space_api.return_value
        client.get_space_members_endpoint.return_value = [
            SpaceMember.from_dict(member)
            for member in load_json_array_fixture("members.json", DOMAIN)
        ]
        client.get_space_score_leaderboard_endpoint.return_value = [
            LeaderboardEntry.from_dict(entry)
            for entry in load_json_array_fixture("leaderboard.json", DOMAIN)
        ]
        client.get_space_score_season_endpoint.return_value = (
            SpaceSeasonSummary.from_dict(
                load_json_object_fixture("season.json", DOMAIN)
            )
        )
        yield client


@pytest.fixture
def mock_list_api() -> Generator[AsyncMock]:
    """Mock the Famn lists API (shopping lists)."""
    with (
        patch(
            "homeassistant.components.famn.coordinator.ListApi", autospec=True
        ) as list_api,
        patch(
            "homeassistant.components.famn.coordinator.ListItemApi", autospec=True
        ) as list_item_api,
    ):
        lists_client = list_api.return_value
        lists_client.get_lists_endpoint.return_value = [
            ListModel.from_dict(shopping_list)
            for shopping_list in load_json_array_fixture("shopping_lists.json", DOMAIN)
        ]

        items_client = list_item_api.return_value
        items = [
            ListItem.from_dict(item)
            for item in load_json_array_fixture("shopping_items.json", DOMAIN)
        ]

        async def _get_items(list_id: str, **kwargs: object) -> list[ListItem]:
            return [item for item in items if str(item.list_id) == list_id]

        items_client.get_list_items_endpoint.side_effect = _get_items
        items_client.lists = lists_client
        yield items_client


@pytest.fixture
def mock_meal_api() -> Generator[AsyncMock]:
    """Mock the Famn meal planner API."""
    with patch(
        "homeassistant.components.famn.coordinator.MealPlannerApi", autospec=True
    ) as meal_api:
        client = meal_api.return_value
        client.get_meal_slots_endpoint.return_value = (
            MealSlotPaginateResponse.from_dict(
                load_json_object_fixture("meal_slots.json", DOMAIN)
            )
        )
        yield client


@pytest.fixture
def mock_realtime_session() -> Generator[MagicMock]:
    """Mock the realtime gateway as unreachable.

    The integration then falls back to polling, which keeps the tests of
    the REST behavior undisturbed. The realtime tests swap in a scripted
    fake socket via this session.
    """
    session = MagicMock()
    session.ws_connect = MagicMock(side_effect=aiohttp.ClientError("no gateway"))
    with patch(
        "homeassistant.components.famn.realtime.async_get_clientsession",
        return_value=session,
    ):
        yield session


@pytest.fixture
def mock_famn(
    mock_device_api: AsyncMock,
    mock_tasks_api: AsyncMock,
    mock_calendar_api: AsyncMock,
    mock_space_api: AsyncMock,
    mock_list_api: AsyncMock,
    mock_meal_api: AsyncMock,
    mock_realtime_session: MagicMock,
) -> None:
    """Mock every Famn API used by the integration."""
