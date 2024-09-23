"""Tests for the habitica component."""

from unittest.mock import patch

import pytest

from homeassistant.components.habitica.const import CONF_API_USER, DEFAULT_URL, DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_URL

from tests.common import MockConfigEntry, load_json_object_fixture
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture(autouse=True)
def disable_plumbum():
    """Disable plumbum in tests as it can cause the test suite to fail.

    plumbum can leave behind PlumbumTimeoutThreads
    """
    with patch("plumbum.local"), patch("plumbum.colors"):
        yield


@pytest.fixture
def mock_habitica(aioclient_mock: AiohttpClientMocker) -> AiohttpClientMocker:
    """Mock aiohttp requests."""

    aioclient_mock.get(
        f"{DEFAULT_URL}/api/v3/user", json=load_json_object_fixture("user.json", DOMAIN)
    )
    aioclient_mock.get(
        f"{DEFAULT_URL}/api/v3/tasks/user",
        params={"type": "completedTodos"},
        json=load_json_object_fixture("completed_todos.json", DOMAIN),
    )
    aioclient_mock.get(
        f"{DEFAULT_URL}/api/v3/tasks/user",
        json=load_json_object_fixture("tasks.json", DOMAIN),
    )

    return aioclient_mock


@pytest.fixture(name="config_entry")
def mock_config_entry() -> MockConfigEntry:
    """Mock Habitica configuration entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="test-user",
        data={
            CONF_URL: DEFAULT_URL,
            CONF_API_USER: "test-api-user",
            CONF_API_KEY: "test-api-key",
        },
        unique_id="00000000-0000-0000-0000-000000000000",
    )
