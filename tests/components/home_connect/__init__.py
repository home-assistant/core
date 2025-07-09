"""Tests for the Home Connect integration."""

from typing import Any

from aiohomeconnect.model import ArrayOfStatus

from tests.common import load_json_object_fixture

MOCK_PROGRAMS: dict[str, Any] = load_json_object_fixture("home_connect/programs.json")
MOCK_SETTINGS: dict[str, Any] = load_json_object_fixture("home_connect/settings.json")
MOCK_STATUS = ArrayOfStatus.from_dict(
    load_json_object_fixture("home_connect/status.json")["data"]  # type: ignore[arg-type]
)
MOCK_AVAILABLE_COMMANDS: dict[str, Any] = load_json_object_fixture(
    "home_connect/available_commands.json"
)
