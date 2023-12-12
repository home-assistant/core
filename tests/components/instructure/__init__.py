"""Tests for the canvas integration."""
from datetime import UTC, datetime, timedelta

from homeassistant.components.instructure.canvas_api import ISO_DATETIME_FORMAT

# Save data
ANNOUNCEMENTS_KEY: str = "announcements"
ASSIGNMENTS_KEY: str = "assignments"
CONVERSATIONS_KEY: str = "conversations"
GRADES_KEY: str = "grades"
QUICK_LINKS_KEY: str = "quick_links"
ANNOUNCEMENT_ENTITY_CONSTANT = 1
ASSIGNMENT_ENTITY_CONSTANT = 2
CONVERSATION_ENTITY_CONSTANT = 3
GRADES_ENTITY_CONSTANT = 4

MOCK_ASSIGNMENTS = {
    "assignment-1": {
        "id": 1,
        "name": "Test Assignment",
        "due_at": (datetime.now(UTC) + timedelta(days=5)).strftime(ISO_DATETIME_FORMAT),
        "html_url": "https://canvas.example.com/assignments/1",
    }
}

MOCK_TWO_ASSIGNMENTS = {
    "assignment-1": {
        "id": 1,
        "name": "Test Assignment 1",
        "due_at": (datetime.now(UTC) + timedelta(days=5)).strftime(ISO_DATETIME_FORMAT),
        "html_url": "https://canvas.example.com/assignments/1",
    },
    "assignment-2": {
        "id": 2,
        "name": "Test Assignment 2",
        "due_at": (datetime.now(UTC) + timedelta(days=16)).strftime(
            ISO_DATETIME_FORMAT
        ),
        "html_url": "https://canvas.example.com/assignments/2",
    },
}
MOCK_ANNOUNCEMENTS = {
    "announcement-1": {
        "id": 1,
        "title": "Test Announcement",
        "read_state": "unread",
        "html_url": "https://canvas.example.com/announcements/1",
        "posted_at": "2023-12-01T09:00:00Z",
    }
}
MOCK_CONVERSATIONS = {
    "conversation-1": {
        "id": 1,
        "subject": "Test Conversation",
        "workflow_state": "unread",
        "context_name": "Test Course",
        "participants": [{"name": "Test Sender"}],
        "last_message": "This is a test message.",
        "last_message_at": "2023-12-05T15:30:00Z",
    }
}
MOCK_GRADES = {
    "grade-1": {
        "id": 1,
        "assignment_id": "Test Grade",
        "grade": "A",
        "score": 95,
        "submission_type": "online_text_entry",
    }
}

MOCK_QUICK_LINKS = {
    "quick-links-1": {
        "name": "Test Quick Links",
        "url": "https://canvas.example.com/quicklinks/1",
    }
}
