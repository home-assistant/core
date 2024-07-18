"""Test configuration for DoorBird tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

from doorbirdpy import DoorBirdScheduleEntry
import pytest

from . import get_mock_doorbirdapi_return_values

from tests.common import load_json_value_fixture


@pytest.fixture
def doorbird_info() -> dict[str, Any]:
    """Return a loaded DoorBird info fixture."""
    return load_json_value_fixture("info.json", "doorbird")["BHA"]["VERSION"][0]


@pytest.fixture
def doorbird_schedule() -> list[DoorBirdScheduleEntry]:
    """Return a loaded DoorBird schedule fixture."""
    return DoorBirdScheduleEntry.parse_all(
        load_json_value_fixture("schedule.json", "doorbird")
    )


@pytest.fixture
def doorbird_api(
    doorbird_info: dict[str, Any], doorbird_schedule: dict[str, Any]
) -> Generator[Any, Any, MagicMock]:
    """Mock the DoorBirdAPI."""
    api = get_mock_doorbirdapi_return_values(
        info=doorbird_info, schedule=doorbird_schedule
    )

    with (
        patch(
            "homeassistant.components.doorbird.DoorBird",
            return_value=api,
        ),
        patch(
            "homeassistant.components.doorbird.config_flow.DoorBird",
            return_value=api,
        ),
    ):
        yield api
