"""Test data redaction helpers."""

import json

from homeassistant.components.google_assistant.data_redaction import async_redact_msg

from tests.common import load_fixture


def test_redact_msg() -> None:
    """Test async_redact_msg."""
    messages = json.loads(load_fixture("data_redaction.json", "google_assistant"))
    agent_user_id = "333dee20-1234-1234-1234-2225a0d70d4c"
    for item in messages:
        assert async_redact_msg(item["raw"], agent_user_id) == item["redacted"]
