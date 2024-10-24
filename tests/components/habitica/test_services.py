"""Test Habitica sensor platform."""

from collections.abc import Generator
import json
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.habitica.const import (
    ATTR_ADD_CHECKLIST_ITEM,
    ATTR_ALIAS,
    ATTR_CLEAR_DATE,
    ATTR_CLEAR_REMINDER,
    ATTR_CONFIG_ENTRY,
    ATTR_COST,
    ATTR_COUNTER_DOWN,
    ATTR_COUNTER_UP,
    ATTR_FREQUENCY,
    ATTR_INTERVAL,
    ATTR_PRIORITY,
    ATTR_REMINDER,
    ATTR_REMINDER_TIME,
    ATTR_REMOVE_CHECKLIST_ITEM,
    ATTR_REMOVE_REMINDER,
    ATTR_REMOVE_REMINDER_TIME,
    ATTR_REMOVE_TAG,
    ATTR_REPEAT,
    ATTR_REPEAT_MONTHLY,
    ATTR_SCORE_CHECKLIST_ITEM,
    ATTR_START_DATE,
    ATTR_STREAK,
    ATTR_TAG,
    ATTR_TASK,
    ATTR_UNSCORE_CHECKLIST_ITEM,
    ATTR_UP_DOWN,
    DEFAULT_URL,
    DOMAIN,
    SERVICE_UPDATE_DAILY,
    SERVICE_UPDATE_HABIT,
    SERVICE_UPDATE_REWARD,
    SERVICE_UPDATE_TODO,
)
from homeassistant.components.todo import ATTR_DESCRIPTION, ATTR_RENAME
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_DATE
from homeassistant.core import HomeAssistant

from .conftest import mock_called_with

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture(autouse=True)
def services_only() -> Generator[None]:
    """Enable only services."""
    with patch(
        "homeassistant.components.habitica.PLATFORMS",
        [],
    ):
        yield


@pytest.fixture(autouse=True)
async def load_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_habitica: AiohttpClientMocker,
) -> None:
    """Load config entry."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED


@pytest.mark.parametrize(
    ("service_data", "expected"),
    [
        (
            {ATTR_TASK: "Zahnseide benutzen"},
            "{}",
        ),
        (
            {ATTR_TASK: "564b9ac9-c53d-4638-9e7f-1cd96fe19baa"},
            "{}",
        ),
        (
            {ATTR_TASK: "alias_zahnseide_benutzen"},
            "{}",
        ),
        (
            {
                ATTR_RENAME: "new-task-name",
            },
            '{"text": "new-task-name"}',
        ),
        (
            {
                ATTR_DESCRIPTION: "new-task-description",
            },
            '{"notes": "new-task-description"}',
        ),
        (
            {ATTR_ALIAS: "test-alias"},
            '{"alias": "test-alias"}',
        ),
        (
            {
                ATTR_PRIORITY: "trivial",
            },
            '{"priority": 0.1}',
        ),
        (
            {
                ATTR_PRIORITY: "easy",
            },
            '{"priority": 1}',
        ),
        (
            {
                ATTR_PRIORITY: "medium",
            },
            '{"priority": 1.5}',
        ),
        (
            {
                ATTR_PRIORITY: "hard",
            },
            '{"priority": 2}',
        ),
        (
            {
                ATTR_START_DATE: "2024-10-14",
            },
            '{"startDate": "2024-10-14T00:00:00"}',
        ),
        (
            {
                ATTR_FREQUENCY: "daily",
            },
            '{"frequency": "daily"}',
        ),
        (
            {
                ATTR_FREQUENCY: "weekly",
            },
            '{"frequency": "weekly"}',
        ),
        (
            {
                ATTR_FREQUENCY: "monthly",
            },
            '{"frequency": "monthly"}',
        ),
        (
            {
                ATTR_FREQUENCY: "yearly",
            },
            '{"frequency": "yearly"}',
        ),
        (
            {
                ATTR_INTERVAL: 1,
            },
            '{"everyX": 1}',
        ),
        (
            {
                ATTR_REPEAT: ["su", "t", "th", "s"],
            },
            '{"repeat": {"m": false, "t": true, "w": false, "th": true, "f": false, "s": true, "su": true}}',
        ),
        (
            {
                ATTR_FREQUENCY: "monthly",
                ATTR_REPEAT_MONTHLY: "day_of_month",
            },
            '{"frequency": "monthly", "daysOfMonth": 6, "weeksOfMonth": []}',
        ),
        (
            {
                ATTR_FREQUENCY: "monthly",
                ATTR_REPEAT_MONTHLY: "day_of_week",
            },
            (
                '{"frequency": "monthly", "weeksOfMonth": 0, "repeat": {"m": false, "t": false, "w": '
                'false, "th": false, "f": false, "s": true, "su": false}, "daysOfMonth": []}'
            ),
        ),
        (
            {
                ATTR_STREAK: 100,
            },
            '{"streak": 100}',
        ),
        (
            {
                ATTR_REMINDER_TIME: ["20:00", "22:00"],
            },
            (
                '{"reminders": [{"id": "5d1935ff-80c8-443c-b2e9-733c66b44745", "startDate": "", "time": "2024-10-14T20:00:00+00:00"},'
                ' {"id": "5d1935ff-80c8-443c-b2e9-733c66b44745", "startDate": "", "time": "2024-10-14T22:00:00+00:00"},'
                ' {"id": "e2c62b7f-2e20-474b-a268-779252b25e8c", "startDate": "", "time": "2024-10-14T20:30:00+00:00"},'
                ' {"id": "4c472190-efba-4277-9d3e-ce7a9e1262ba", "startDate": "", "time": "2024-10-14T22:30:00+00:00"}]}'
            ),
        ),
        (
            {
                ATTR_REMOVE_REMINDER_TIME: ["22:30"],
            },
            '{"reminders": [{"id": "e2c62b7f-2e20-474b-a268-779252b25e8c", "startDate": "", "time": "2024-10-14T20:30:00+00:00"}]}',
        ),
        (
            {
                ATTR_CLEAR_REMINDER: True,
            },
            '{"reminders": []}',
        ),
    ],
    ids=[
        "match_task_by_name",
        "match_task_by_id",
        "match_task_by_alias",
        "rename",
        "description",
        "alias",
        "difficulty_trivial",
        "difficulty_easy",
        "difficulty_medium",
        "difficulty_hard",
        "start_date",
        "frequency_daily",
        "frequency_weekly",
        "frequency_monthly",
        "frequency_yearly",
        "interval",
        "repeat_days",
        "repeat_day_of_month",
        "repeat_day_of_week",
        "streak",
        "add_reminders",
        "remove_reminders",
        "clear_reminders",
    ],
)
async def test_update_daily(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_habitica: AiohttpClientMocker,
    service_data: dict[str, Any],
    expected: dict[str, Any],
) -> None:
    """Test Habitica update_daily action."""
    task_id = "564b9ac9-c53d-4638-9e7f-1cd96fe19baa"
    mock_habitica.put(
        f"{DEFAULT_URL}/api/v3/tasks/{task_id}",
        json={"success": True, "data": {}},
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_UPDATE_DAILY,
        service_data={
            ATTR_CONFIG_ENTRY: config_entry.entry_id,
            ATTR_TASK: task_id,
            **service_data,
        },
        return_response=True,
        blocking=True,
    )

    mock_call = mock_called_with(
        mock_habitica,
        "PUT",
        f"{DEFAULT_URL}/api/v3/tasks/{task_id}",
    )
    assert mock_call
    assert mock_call[2] == expected


@pytest.mark.parametrize(
    ("service_data", "expected"),
    [
        (
            {ATTR_DATE: "2024-10-14"},
            '{"date": "2024-10-14T00:00:00"}',
        ),
        (
            {ATTR_CLEAR_DATE: True},
            '{"date": null}',
        ),
        (
            {ATTR_REMINDER: ["2024-12-20T22:00"]},
            (
                '{"reminders": [{"id": "5d1935ff-80c8-443c-b2e9-733c66b44745", "time": "2024-12-20T22:00:00"},'
                ' {"id": "30224d1d-705b-4817-9d65-50f0481607f4", "time": "2024-12-20T22:30:00"}]}'
            ),
        ),
        (
            {ATTR_REMOVE_REMINDER: ["2024-12-20T22:30"]},
            '{"reminders": []}',
        ),
        (
            {ATTR_CLEAR_REMINDER: True},
            '{"reminders": []}',
        ),
    ],
    ids=[
        "due_date",
        "clear_due_date",
        "add_reminders",
        "remove_reminders",
        "clear_reminders",
    ],
)
async def test_update_todo(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_habitica: AiohttpClientMocker,
    service_data: dict[str, Any],
    expected: dict[str, Any],
) -> None:
    """Test Habitica update_todo action."""
    task_id = "2f6fcabc-f670-4ec3-ba65-817e8deea490"
    mock_habitica.put(
        f"{DEFAULT_URL}/api/v3/tasks/{task_id}",
        json={"success": True, "data": {}},
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_UPDATE_TODO,
        service_data={
            ATTR_CONFIG_ENTRY: config_entry.entry_id,
            ATTR_TASK: task_id,
            **service_data,
        },
        return_response=True,
        blocking=True,
    )

    mock_call = mock_called_with(
        mock_habitica,
        "PUT",
        f"{DEFAULT_URL}/api/v3/tasks/{task_id}",
    )
    assert mock_call
    assert mock_call[2] == expected


@pytest.mark.parametrize(
    ("service_data", "expected"),
    [
        (
            {ATTR_UP_DOWN: ["positive", "negative"]},
            '{"up": true, "down": true}',
        ),
        (
            {ATTR_COUNTER_DOWN: 111},
            '{"counterDown": 111}',
        ),
        (
            {ATTR_COUNTER_UP: 222},
            '{"counterUp": 222}',
        ),
    ],
    ids=[
        "positive_negative_habit",
        "counter_up",
        "counter_down",
    ],
)
async def test_update_habit(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_habitica: AiohttpClientMocker,
    service_data: dict[str, Any],
    expected: dict[str, Any],
) -> None:
    """Test Habitica update_habit action."""
    task_id = "1d147de6-5c02-4740-8e2f-71d3015a37f4"
    mock_habitica.put(
        f"{DEFAULT_URL}/api/v3/tasks/{task_id}",
        json={"success": True, "data": {}},
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_UPDATE_HABIT,
        service_data={
            ATTR_CONFIG_ENTRY: config_entry.entry_id,
            ATTR_TASK: task_id,
            **service_data,
        },
        return_response=True,
        blocking=True,
    )

    mock_call = mock_called_with(
        mock_habitica,
        "PUT",
        f"{DEFAULT_URL}/api/v3/tasks/{task_id}",
    )
    assert mock_call
    assert mock_call[2] == expected


async def test_update_reward(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_habitica: AiohttpClientMocker,
) -> None:
    """Test Habitica update_reward action."""
    task_id = "5e2ea1df-f6e6-4ba3-bccb-97c5ec63e99b"
    mock_habitica.put(
        f"{DEFAULT_URL}/api/v3/tasks/{task_id}",
        json={"success": True, "data": {}},
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_UPDATE_REWARD,
        service_data={
            ATTR_CONFIG_ENTRY: config_entry.entry_id,
            ATTR_TASK: task_id,
            ATTR_COST: 100,
        },
        return_response=True,
        blocking=True,
    )

    mock_call = mock_called_with(
        mock_habitica,
        "PUT",
        f"{DEFAULT_URL}/api/v3/tasks/{task_id}",
    )
    assert mock_call
    assert mock_call[2] == '{"value": 100.0}'


async def test_tags(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_habitica: AiohttpClientMocker,
) -> None:
    """Test adding tags to a task."""
    task_id = "88de7cd9-af2b-49ce-9afd-bf941d87336b"
    mock_habitica.put(
        f"{DEFAULT_URL}/api/v3/tasks/{task_id}",
        json={"success": True, "data": {}},
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_UPDATE_TODO,
        service_data={
            ATTR_CONFIG_ENTRY: config_entry.entry_id,
            ATTR_TASK: task_id,
            ATTR_TAG: ["Schule"],
        },
        return_response=True,
        blocking=True,
    )

    mock_call = mock_called_with(
        mock_habitica,
        "PUT",
        f"{DEFAULT_URL}/api/v3/tasks/{task_id}",
    )
    assert mock_call
    assert (tags := json.loads(mock_call[2]).get("tags"))
    assert len(tags) == 3

    assert set(tags) == {
        "2ac458af-0833-4f3f-bf04-98a0c33ef60b",
        "20409521-c096-447f-9a90-23e8da615710",
        "8515e4ae-2f4b-455a-b4a4-8939e04b1bfd",
    }


async def test_remove_tags(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_habitica: AiohttpClientMocker,
) -> None:
    """Test removing tags from a task."""
    task_id = "88de7cd9-af2b-49ce-9afd-bf941d87336b"
    mock_habitica.put(
        f"{DEFAULT_URL}/api/v3/tasks/{task_id}",
        json={"success": True, "data": {}},
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_UPDATE_TODO,
        service_data={
            ATTR_CONFIG_ENTRY: config_entry.entry_id,
            ATTR_TASK: task_id,
            ATTR_REMOVE_TAG: ["arbeit"],
        },
        return_response=True,
        blocking=True,
    )

    mock_call = mock_called_with(
        mock_habitica,
        "PUT",
        f"{DEFAULT_URL}/api/v3/tasks/{task_id}",
    )
    assert mock_call
    assert (tags := json.loads(mock_call[2]).get("tags"))
    assert len(tags) == 1

    assert set(tags) == {"20409521-c096-447f-9a90-23e8da615710"}


async def test_add_checklist(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_habitica: AiohttpClientMocker,
) -> None:
    """Test adding a checklist item."""

    task_id = "564b9ac9-c53d-4638-9e7f-1cd96fe19baa"
    mock_habitica.put(
        f"{DEFAULT_URL}/api/v3/tasks/{task_id}",
        json={"success": True, "data": {}},
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_UPDATE_DAILY,
        service_data={
            ATTR_CONFIG_ENTRY: config_entry.entry_id,
            ATTR_TASK: task_id,
            ATTR_ADD_CHECKLIST_ITEM: ["Checklist-item2"],
        },
        return_response=True,
        blocking=True,
    )

    mock_call = mock_called_with(
        mock_habitica,
        "PUT",
        f"{DEFAULT_URL}/api/v3/tasks/{task_id}",
    )
    assert mock_call
    assert (checklist := json.loads(mock_call[2]).get("checklist"))
    assert len(checklist) == 2
    assert {
        "completed": False,
        "id": "5d1935ff-80c8-443c-b2e9-733c66b44745",
        "text": "Checklist-item2",
    } in checklist


async def test_remove_checklist(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_habitica: AiohttpClientMocker,
) -> None:
    """Test adding a checklist item."""

    task_id = "564b9ac9-c53d-4638-9e7f-1cd96fe19baa"
    mock_habitica.put(
        f"{DEFAULT_URL}/api/v3/tasks/{task_id}",
        json={"success": True, "data": {}},
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_UPDATE_DAILY,
        service_data={
            ATTR_CONFIG_ENTRY: config_entry.entry_id,
            ATTR_TASK: task_id,
            ATTR_REMOVE_CHECKLIST_ITEM: ["Checklist-item1"],
        },
        return_response=True,
        blocking=True,
    )

    mock_call = mock_called_with(
        mock_habitica,
        "PUT",
        f"{DEFAULT_URL}/api/v3/tasks/{task_id}",
    )
    assert mock_call
    checklist = json.loads(mock_call[2]).get("checklist")
    assert len(checklist) == 0


@pytest.mark.parametrize(
    ("service", "task_id", "expected"),
    [
        (ATTR_SCORE_CHECKLIST_ITEM, "564b9ac9-c53d-4638-9e7f-1cd96fe19baa", True),
        (ATTR_UNSCORE_CHECKLIST_ITEM, "2c6d136c-a1c3-4bef-b7c4-fa980784b1e1", False),
    ],
    ids=["score_checklist", "unscore_checklist"],
)
async def test_complete_checklist(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_habitica: AiohttpClientMocker,
    service: str,
    task_id: str,
    expected: bool,
) -> None:
    """Test completing a checklist item."""

    mock_habitica.put(
        f"{DEFAULT_URL}/api/v3/tasks/{task_id}",
        json={"success": True, "data": {}},
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_UPDATE_DAILY,
        service_data={
            ATTR_CONFIG_ENTRY: config_entry.entry_id,
            ATTR_TASK: task_id,
            service: ["Checklist-item1"],
        },
        return_response=True,
        blocking=True,
    )

    mock_call = mock_called_with(
        mock_habitica,
        "PUT",
        f"{DEFAULT_URL}/api/v3/tasks/{task_id}",
    )
    assert mock_call
    checklist = json.loads(mock_call[2]).get("checklist")
    assert len(checklist) == 1
    assert checklist[0]["completed"] is expected
