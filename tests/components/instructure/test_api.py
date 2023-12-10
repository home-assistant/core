"""Unit Tests for the CanvasAPI class."""

from datetime import UTC, datetime, timedelta
import json
from unittest.mock import AsyncMock, patch

from homeassistant.components.instructure.canvas_api import CanvasAPI

from . import (
    ANNOUNCEMENT_ENTITY_CONSTANT,
    ASSIGNMENT_ENTITY_CONSTANT,
    CONVERSATION_ENTITY_CONSTANT,
    GRADES_ENTITY_CONSTANT,
    MOCK_ANNOUNCEMENTS,
    MOCK_CONVERSATIONS,
    MOCK_TWO_ASSIGNMENTS,
)

host = "https://chalmers.instructure.com/api/v1"
access_token = "mock_access_token"
canvas_api = CanvasAPI(host, access_token)
ISO_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


@patch("httpx.AsyncClient.get")
async def test_async_make_get_request_success(mock_get) -> None:
    """Test successful GET request."""
    mock_get.return_value = AsyncMock(
        status_code=200, content=json.dumps({"key": "value"}).encode("utf-8")
    )

    response = await canvas_api.async_make_get_request("/courses")
    assert response.status_code == 200
    assert json.loads(response.content) == {"key": "value"}


@patch("httpx.AsyncClient.get")
async def test_async_make_get_request_failure(mock_get) -> None:
    """Test failed GET request."""
    mock_get.return_value = AsyncMock(status_code=404)

    response = await canvas_api.async_make_get_request("/courses")
    assert response.status_code == 404


@patch("httpx.AsyncClient.get")
async def test_async_test_authentication(mock_get) -> None:
    """Test authentication check."""
    mock_get.return_value = AsyncMock(status_code=200)

    result = await canvas_api.async_test_authentication()
    assert result


@patch("httpx.AsyncClient.get")
async def test_async_get_courses(mock_get) -> None:
    """Test getting courses."""
    mock_get.return_value = AsyncMock(
        status_code=200,
        content=json.dumps([{"id": 1, "name": "Test Course"}]).encode("utf-8"),
    )

    courses = await canvas_api.async_get_courses()
    assert len(courses) == 1
    assert courses[0]["name"] == "Test Course"
    assert courses[0]["id"] == 1


@patch("httpx.AsyncClient.get")
async def test_async_get_courses_empty_result(mock_get) -> None:
    """Test getting courses."""
    mock_get.return_value = AsyncMock(
        status_code=200, content=json.dumps([{}]).encode("utf-8")
    )

    courses = await canvas_api.async_get_courses()
    assert len(courses) == 1
    assert courses == [{}]
    assert courses[0] == {}


@patch("httpx.AsyncClient.get")
async def test_async_get_conversations(mock_get) -> None:
    """Test getting conversations."""
    mock_get.return_value = AsyncMock(
        status_code=200,
        content=json.dumps(
            [
                {
                    "id": 1,
                    "subject": "Test Conversation",
                    "workflow_state": "unread",
                    "context_name": "Test Course",
                    "participants": [{"name": "Test Sender"}],
                    "last_message": "This is a test message.",
                    "last_message_at": "2023-12-05T15:30:00Z",
                }
            ]
        ).encode("utf-8"),
    )

    conversations = await canvas_api.async_get_conversations()

    expected_conversation = MOCK_CONVERSATIONS["conversation-1"]
    actual_conversation = conversations["conversation-1"]
    assert expected_conversation == actual_conversation


@patch("httpx.AsyncClient.get")
async def test_async_get_conversations_empty_result(mock_get) -> None:
    """Test getting conversations with empty result."""
    mock_get.return_value = AsyncMock(
        status_code=200,
        content=json.dumps([]).encode("utf-8"),
    )
    conversations = await canvas_api.async_get_conversations()
    assert len(conversations) == 1
    assert conversations == {f"conversation-{CONVERSATION_ENTITY_CONSTANT}": {}}


@patch("httpx.AsyncClient.get")
async def test_async_get_announcements(mock_get) -> None:
    """Test getting announcements."""
    mock_get.return_value = AsyncMock(
        status_code=200,
        content=json.dumps(
            [
                {
                    "id": 1,
                    "title": "Test Announcement",
                    "read_state": "unread",
                    "html_url": "https://canvas.example.com/announcements/1",
                    "posted_at": "2023-12-01T09:00:00Z",
                }
            ]
        ).encode("utf-8"),
    )

    announcements = await canvas_api.async_get_announcements(["course_id"])
    assert MOCK_ANNOUNCEMENTS["announcement-1"] == announcements["announcement-1"]


@patch("httpx.AsyncClient.get")
async def test_async_get_announcements_empty_result(mock_get) -> None:
    """Test getting announcements with an empty result."""
    mock_get.return_value = AsyncMock(
        status_code=200,
        content=json.dumps([]).encode("utf-8"),
    )

    announcements = await canvas_api.async_get_announcements(["course_id"])

    assert len(announcements) == 1
    assert announcements == {f"announcement-{ANNOUNCEMENT_ENTITY_CONSTANT}": {}}


@patch("httpx.AsyncClient.get")
async def test_async_get_upcoming_assignments(mock_get) -> None:
    """Test getting upcoming assignments."""
    mock_get.return_value = AsyncMock(
        status_code=200,
        content=json.dumps(
            [
                {
                    "id": 1,
                    "name": "Test Assignment 1",
                    "due_at": MOCK_TWO_ASSIGNMENTS["assignment-1"]["due_at"],
                    "html_url": "https://canvas.example.com/assignments/1",
                },
                {
                    "id": 2,
                    "name": "Test Assignment 2",
                    "due_at": MOCK_TWO_ASSIGNMENTS["assignment-2"]["due_at"],
                    "html_url": "https://canvas.example.com/assignments/2",
                },
            ]
        ).encode("utf-8"),
    )

    assignments = await canvas_api.async_get_upcoming_assignments(["course_id"])

    assert MOCK_TWO_ASSIGNMENTS["assignment-1"] == assignments["assignment-1"]
    # NOTE
    # Second assignment filtered because we only display upcoming assignments less than 15 days


@patch("httpx.AsyncClient.get")
async def test_async_get_assignments_empty_result(mock_get) -> None:
    """Test getting assignments with an empty result."""
    mock_get.return_value = AsyncMock(
        status_code=200,
        content=json.dumps([]).encode("utf-8"),
    )

    assignments = await canvas_api.async_get_upcoming_assignments(["course_id"])

    assert len(assignments) == 1
    assert assignments == {f"assignment-{ASSIGNMENT_ENTITY_CONSTANT}": {}}


# TODO correct this!
# @patch("httpx.AsyncClient.get")
# async def test_async_get_grades(mock_get) -> None:
#     """Test getting grades."""
#     mock_get.return_value = AsyncMock(status_code=200, content=json.dumps([
#         {
#             "id": 1,
#             "assignment_id": "assignment-1",
#             "grade": "A",
#             "score": 95,
#             "submission_type": "online_text_entry",
#         }
#     ]).encode("utf-8"))

#     grades = await canvas_api.async_get_grades(["course_id"])

#     assert MOCK_GRADES["grade-1"] == grades.get("submission-4")


@patch("httpx.AsyncClient.get")
async def test_async_get_grades(mock_get) -> None:
    """Test getting grades."""
    current_time = datetime.now(UTC)
    past_time = current_time - timedelta(days=15)
    mock_get.return_value = AsyncMock(
        status_code=200,
        content=json.dumps(
            [
                {
                    "id": 1,
                    "graded_at": past_time.strftime(ISO_DATETIME_FORMAT),
                    "assignment_id": "assignment-1",
                    "grade": "A",
                    "score": 95,
                    "submission_type": "online_text_entry",
                }
            ]
        ).encode("utf-8"),
    )

    grades = await canvas_api.async_get_grades(["course_id"])
    assert len(grades) == 1
    assert list(grades.keys())[0].startswith("submission-")


@patch("httpx.AsyncClient.get")
async def test_async_get_grades_empty_result(mock_get) -> None:
    """Test getting grades with an empty result."""
    mock_get.return_value = AsyncMock(
        status_code=200,
        content=json.dumps([]).encode("utf-8"),
    )

    grades = await canvas_api.async_get_grades(["course_id"])

    assert len(grades) == 1
    assert grades == {f"submission-{GRADES_ENTITY_CONSTANT}": {}}
