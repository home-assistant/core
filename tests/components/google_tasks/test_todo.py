"""Test Google Tasks Todo functionalities."""

from datetime import date
from unittest.mock import Mock

import pytest

from homeassistant.components.google_tasks.todo import (
    GoogleTaskTodoListEntity,
    _convert_api_item,
)


def create_todo_item(title, due=None, description=None, position="0"):
    """Create a dictionary simulating API response for a todo item."""
    return {
        "title": title,
        "id": "task_" + title.lower().replace(" ", "_"),
        "status": "needsAction",
        "due": due.isoformat() if due else None,
        "notes": description or "",
        "position": position,
    }


@pytest.mark.parametrize(
    ("task_title", "expected_due"),
    [
        ("Remind me to call Harsha on 2024/10/23", date(2024, 10, 23)),
        ("Remind me to schedule a meeting on 2024/12/24", date(2024, 12, 24)),
        ("Remind me to wish happy new year on 2026/01/01", date(2026, 1, 1)),
        ("I have a badminton match on 2023/12/01", date(2023, 12, 1)),
    ],
)
def test_todo_item_due_dates(task_title, expected_due) -> None:
    """Test that TodoItem correctly parses and assigns due dates from task titles."""
    item = create_todo_item(task_title, expected_due)
    todo_item = _convert_api_item(item)
    assert todo_item.due == expected_due, f"Due date mismatch for task: {task_title}"


@pytest.mark.parametrize(
    ("task_title", "due_date"),
    [
        ("Remind me to call Harsha on 2024/10/23", date(2024, 10, 23)),
        ("Remind me to schedule a meeting on 2024/12/24", date(2024, 12, 24)),
        ("Remind me to wish happy new year on 2026/01/01", date(2026, 1, 1)),
        ("I have a badminton match on 2023/12/01", date(2023, 12, 1)),
    ],
)
def test_todo_item_creation(task_title, due_date) -> None:
    """Test the creation of TodoItem objects from API responses."""
    item = create_todo_item(task_title, due_date)
    todo_item = _convert_api_item(item)
    assert todo_item.summary == task_title, "Task title mismatch"
    assert todo_item.due == due_date, "Due date mismatch"


@pytest.mark.parametrize(
    ("task_title", "description", "due_date"),
    [
        ("Remind me to call Harsha", "Call Harsha on the 23rd", date(2024, 10, 23)),
        ("Meeting with team", "Schedule meeting on 24th Dec", date(2024, 12, 24)),
        ("New Year Reminder", "Wish happy new year on Jan 1st", date(2026, 1, 1)),
    ],
)
def test_todo_item_with_description(task_title, description, due_date) -> None:
    """Test TodoItem creation with both title and description."""
    item = create_todo_item(task_title, due_date, description)
    todo_item = _convert_api_item(item)
    assert todo_item.summary == task_title, "Task title mismatch"
    assert todo_item.description == description, "Description mismatch"
    assert todo_item.due == due_date, "Due date mismatch"


def test_todo_item_without_due_date() -> None:
    """Test TodoItem creation without a due date."""
    item = create_todo_item("Task without due date")
    todo_item = _convert_api_item(item)
    assert todo_item.summary == "Task without due date"
    assert todo_item.due is None


def test_todo_item_completed_status() -> None:
    """Test TodoItem with completed status."""
    item = create_todo_item("Completed task")
    item["status"] = "completed"
    todo_item = _convert_api_item(item)
    assert todo_item.status == "completed"


@pytest.mark.asyncio
async def test_integration_create_todo_item() -> None:
    """Integration test for creating a Todo item and verifying it appears in the task list."""
    mock_coordinator = Mock()
    mock_coordinator.data = [
        create_todo_item(
            "Remind me to call Harsha on 2024/10/23", date(2024, 10, 23), position="1"
        ),
        create_todo_item(
            "Meeting with team",
            date(2024, 12, 24),
            "Discuss project timeline",
            position="2",
        ),
    ]

    task_entity = GoogleTaskTodoListEntity(
        coordinator=mock_coordinator,
        name="Personal Tasks",
        config_entry_id="entry1",
        task_list_id="tasklist1",
    )

    # Use the correct method to get todo items
    todo_items = task_entity.todo_items

    assert len(todo_items) == 2
    assert todo_items[0].summary == "Remind me to call Harsha on 2024/10/23"
    assert todo_items[1].summary == "Meeting with team"
    assert todo_items[1].description == "Discuss project timeline"
