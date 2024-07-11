"""Test the habitica module."""

from http import HTTPStatus

import pytest

from homeassistant.components.habitica.const import (
    ATTR_ARGS,
    ATTR_DATA,
    ATTR_PATH,
    DEFAULT_URL,
    DOMAIN,
    EVENT_API_CALL_SUCCESS,
    SERVICE_API_CALL,
)
from homeassistant.const import ATTR_NAME
from homeassistant.core import Event, HomeAssistant

from tests.common import MockConfigEntry, async_capture_events
from tests.test_util.aiohttp import AiohttpClientMocker

TEST_API_CALL_ARGS = {"text": "Use API from Home Assistant", "type": "todo"}
TEST_USER_NAME = "test_user"


@pytest.fixture
def capture_api_call_success(hass: HomeAssistant) -> list[Event]:
    """Capture api_call events."""
    return async_capture_events(hass, EVENT_API_CALL_SUCCESS)


@pytest.fixture
def habitica_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Test entry for the following tests."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test-api-user",
        data={
            "api_user": "test-api-user",
            "api_key": "test-api-key",
            "url": DEFAULT_URL,
        },
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def common_requests(aioclient_mock: AiohttpClientMocker) -> AiohttpClientMocker:
    """Register requests for the tests."""
    aioclient_mock.get(
        "https://habitica.com/api/v3/user",
        json={
            "data": {
                "api_user": "test-api-user",
                "profile": {"name": TEST_USER_NAME},
                "stats": {
                    "class": "warrior",
                    "con": 1,
                    "exp": 2,
                    "gp": 3,
                    "hp": 4,
                    "int": 5,
                    "lvl": 6,
                    "maxHealth": 7,
                    "maxMP": 8,
                    "mp": 9,
                    "per": 10,
                    "points": 11,
                    "str": 12,
                    "toNextLevel": 13,
                },
            }
        },
    )

    aioclient_mock.get(
        "https://habitica.com/api/v3/tasks/user",
        json={
            "data": [
                {
                    "text": f"this is a mock {task} #{i}",
                    "id": f"{i}",
                    "type": task,
                    "completed": False,
                }
                for i, task in enumerate(("habit", "daily", "todo", "reward"), start=1)
            ]
        },
    )
    aioclient_mock.get(
        "https://habitica.com/api/v3/tasks/user?type=completedTodos",
        json={
            "data": [
                {
                    "text": "this is a mock todo #5",
                    "id": 5,
                    "type": "todo",
                    "completed": True,
                }
            ]
        },
    )

    aioclient_mock.post(
        "https://habitica.com/api/v3/tasks/user",
        status=HTTPStatus.CREATED,
        json={"data": TEST_API_CALL_ARGS},
    )

    return aioclient_mock


@pytest.mark.usefixtures("common_requests")
async def test_entry_setup_unload(
    hass: HomeAssistant, habitica_entry: MockConfigEntry
) -> None:
    """Test integration setup and unload."""
    assert await hass.config_entries.async_setup(habitica_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.services.has_service(DOMAIN, SERVICE_API_CALL)

    assert await hass.config_entries.async_unload(habitica_entry.entry_id)

    assert not hass.services.has_service(DOMAIN, SERVICE_API_CALL)


@pytest.mark.usefixtures("common_requests")
async def test_service_call(
    hass: HomeAssistant,
    habitica_entry: MockConfigEntry,
    capture_api_call_success: list[Event],
) -> None:
    """Test integration setup, service call and unload."""

    assert await hass.config_entries.async_setup(habitica_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.services.has_service(DOMAIN, SERVICE_API_CALL)

    assert len(capture_api_call_success) == 0

    TEST_SERVICE_DATA = {
        ATTR_NAME: "test_user",
        ATTR_PATH: ["tasks", "user", "post"],
        ATTR_ARGS: TEST_API_CALL_ARGS,
    }
    await hass.services.async_call(
        DOMAIN, SERVICE_API_CALL, TEST_SERVICE_DATA, blocking=True
    )

    assert len(capture_api_call_success) == 1
    captured_data = capture_api_call_success[0].data
    captured_data[ATTR_ARGS] = captured_data[ATTR_DATA]
    del captured_data[ATTR_DATA]
    assert captured_data == TEST_SERVICE_DATA

    assert await hass.config_entries.async_unload(habitica_entry.entry_id)

    assert not hass.services.has_service(DOMAIN, SERVICE_API_CALL)
