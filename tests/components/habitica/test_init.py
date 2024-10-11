"""Test the habitica module."""

import datetime
from http import HTTPStatus
import logging

from freezegun.api import FrozenDateTimeFactory
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
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_NAME
from homeassistant.core import Event, HomeAssistant

from tests.common import (
    MockConfigEntry,
    async_capture_events,
    async_fire_time_changed,
    load_json_object_fixture,
)
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
                "auth": {"local": {"username": TEST_USER_NAME}},
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


@pytest.mark.parametrize(
    ("status"), [HTTPStatus.NOT_FOUND, HTTPStatus.TOO_MANY_REQUESTS]
)
async def test_config_entry_not_ready(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    status: HTTPStatus,
) -> None:
    """Test config entry not ready."""

    aioclient_mock.get(
        f"{DEFAULT_URL}/api/v3/user",
        status=status,
    )

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_coordinator_update_failed(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test coordinator update failed."""

    aioclient_mock.get(
        f"{DEFAULT_URL}/api/v3/user",
        json=load_json_object_fixture("user.json", DOMAIN),
    )
    aioclient_mock.get(
        f"{DEFAULT_URL}/api/v3/tasks/user",
        status=HTTPStatus.NOT_FOUND,
    )

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_coordinator_rate_limited(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_habitica: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test coordinator when rate limited."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    mock_habitica.clear_requests()
    mock_habitica.get(
        f"{DEFAULT_URL}/api/v3/user",
        status=HTTPStatus.TOO_MANY_REQUESTS,
    )

    with caplog.at_level(logging.DEBUG):
        freezer.tick(datetime.timedelta(seconds=60))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        assert "Currently rate limited, skipping update" in caplog.text
