"""Tests for the habitica component."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from habiticalib import (
    BadRequestError,
    HabiticaErrorResponse,
    HabiticaGroupMembersResponse,
    HabiticaLoginResponse,
    HabiticaSleepResponse,
    HabiticaUserResponse,
    NotAuthorizedError,
    NotFoundError,
    TooManyRequestsError,
)
import pytest
from yarl import URL

from homeassistant.components.habitica.const import CONF_API_USER, DEFAULT_URL, DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_URL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture, load_json_object_fixture
from tests.test_util.aiohttp import AiohttpClientMocker

ERROR_RESPONSE = HabiticaErrorResponse(success=False, error="error", message="message")
ERROR_NOT_AUTHORIZED = NotAuthorizedError(error=ERROR_RESPONSE, headers={})
ERROR_NOT_FOUND = NotFoundError(error=ERROR_RESPONSE, headers={})
ERROR_BAD_REQUEST = BadRequestError(error=ERROR_RESPONSE, headers={})
ERROR_TOO_MANY_REQUESTS = TooManyRequestsError(error=ERROR_RESPONSE, headers={})


@pytest.fixture(autouse=True)
def disable_plumbum():
    """Disable plumbum in tests as it can cause the test suite to fail.

    plumbum can leave behind PlumbumTimeoutThreads
    """
    with patch("plumbum.local"), patch("plumbum.colors"):
        yield


def mock_called_with(
    mock_client: AiohttpClientMocker,
    method: str,
    url: str,
) -> tuple | None:
    """Assert request mock was called with json data."""

    return next(
        (
            call
            for call in mock_client.mock_calls
            if call[0].upper() == method.upper() and call[1] == URL(url)
        ),
        None,
    )


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
    aioclient_mock.get(
        f"{DEFAULT_URL}/api/v3/content",
        params={"language": "en"},
        json=load_json_object_fixture("content.json", DOMAIN),
    )
    aioclient_mock.get(
        f"{DEFAULT_URL}/api/v3/user/anonymized",
        json={
            "data": {
                "user": load_json_object_fixture("user.json", DOMAIN)["data"],
                "tasks": load_json_object_fixture("tasks.json", DOMAIN)["data"],
            }
        },
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


@pytest.fixture
async def set_tz(hass: HomeAssistant) -> None:
    """Fixture to set timezone."""
    await hass.config.async_set_time_zone("Europe/Berlin")


@pytest.fixture(name="habitica")
async def mock_habiticalib() -> Generator[AsyncMock]:
    """Mock habiticalib."""

    with (
        patch(
            "homeassistant.components.habitica.Habitica", autospec=True
        ) as mock_client,
        patch(
            "homeassistant.components.habitica.config_flow.Habitica", new=mock_client
        ),
    ):
        client = mock_client.return_value

        client.login.return_value = HabiticaLoginResponse.from_json(
            load_fixture("login.json", DOMAIN)
        )

        client.get_user.return_value = HabiticaUserResponse.from_json(
            load_fixture("user.json", DOMAIN)
        )

        client.cast_skill.return_value = HabiticaUserResponse.from_json(
            load_fixture("user.json", DOMAIN)
        )
        client.toggle_sleep.return_value = HabiticaSleepResponse(
            success=True, data=True
        )
        client.update_score.return_value = HabiticaUserResponse.from_json(
            load_fixture("score_with_drop.json", DOMAIN)
        )
        client.get_group_members.return_value = HabiticaGroupMembersResponse.from_json(
            load_fixture("party_members.json", DOMAIN)
        )
        yield client


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.habitica.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
