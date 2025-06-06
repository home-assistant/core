"""Tests for the habitica component."""

from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

from habiticalib import (
    BadRequestError,
    HabiticaCastSkillResponse,
    HabiticaContentResponse,
    HabiticaErrorResponse,
    HabiticaGroupMembersResponse,
    HabiticaLoginResponse,
    HabiticaQuestResponse,
    HabiticaResponse,
    HabiticaScoreResponse,
    HabiticaSleepResponse,
    HabiticaTagResponse,
    HabiticaTaskOrderResponse,
    HabiticaTaskResponse,
    HabiticaTasksResponse,
    HabiticaUserAnonymizedResponse,
    HabiticaUserResponse,
    NotAuthorizedError,
    NotFoundError,
    TaskFilter,
    TooManyRequestsError,
)
import pytest

from homeassistant.components.habitica.const import CONF_API_USER, DEFAULT_URL, DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_URL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_load_fixture, load_fixture

ERROR_RESPONSE = HabiticaErrorResponse(success=False, error="error", message="reason")
ERROR_NOT_AUTHORIZED = NotAuthorizedError(error=ERROR_RESPONSE, headers={})
ERROR_NOT_FOUND = NotFoundError(error=ERROR_RESPONSE, headers={})
ERROR_BAD_REQUEST = BadRequestError(error=ERROR_RESPONSE, headers={})
ERROR_TOO_MANY_REQUESTS = TooManyRequestsError(
    error=ERROR_RESPONSE, headers={"retry-after": 5}
)


@pytest.fixture(name="config_entry")
def mock_config_entry() -> MockConfigEntry:
    """Mock Habitica configuration entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="test-user",
        data={
            CONF_URL: DEFAULT_URL,
            CONF_API_USER: "a380546a-94be-4b8e-8a0b-23e0d5c03303",
            CONF_API_KEY: "cd0e5985-17de-4b4f-849e-5d506c5e4382",
        },
        unique_id="a380546a-94be-4b8e-8a0b-23e0d5c03303",
    )


@pytest.fixture
async def set_tz(hass: HomeAssistant) -> None:
    """Fixture to set timezone."""
    await hass.config.async_set_time_zone("Europe/Berlin")


def mock_get_tasks(task_type: TaskFilter | None = None) -> HabiticaTasksResponse:
    """Load tasks fixtures."""

    if task_type is TaskFilter.COMPLETED_TODOS:
        return HabiticaTasksResponse.from_json(
            load_fixture("completed_todos.json", DOMAIN)
        )
    return HabiticaTasksResponse.from_json(load_fixture("tasks.json", DOMAIN))


@pytest.fixture(name="habitica")
async def mock_habiticalib(hass: HomeAssistant) -> AsyncGenerator[AsyncMock]:
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
            await async_load_fixture(hass, "login.json", DOMAIN)
        )

        client.get_user.return_value = HabiticaUserResponse.from_json(
            await async_load_fixture(hass, "user.json", DOMAIN)
        )

        client.cast_skill.return_value = HabiticaCastSkillResponse.from_json(
            await async_load_fixture(hass, "cast_skill_response.json", DOMAIN)
        )
        client.toggle_sleep.return_value = HabiticaSleepResponse(
            success=True, data=True
        )
        client.update_score.return_value = HabiticaUserResponse.from_json(
            await async_load_fixture(hass, "score_with_drop.json", DOMAIN)
        )
        client.get_group_members.return_value = HabiticaGroupMembersResponse.from_json(
            await async_load_fixture(hass, "party_members.json", DOMAIN)
        )
        for func in (
            "leave_quest",
            "reject_quest",
            "cancel_quest",
            "abort_quest",
            "start_quest",
            "accept_quest",
        ):
            getattr(client, func).return_value = HabiticaQuestResponse.from_json(
                await async_load_fixture(hass, "party_quest.json", DOMAIN)
            )
        client.get_content.return_value = HabiticaContentResponse.from_json(
            await async_load_fixture(hass, "content.json", DOMAIN)
        )
        client.get_tasks.side_effect = mock_get_tasks
        client.update_score.return_value = HabiticaScoreResponse.from_json(
            await async_load_fixture(hass, "score_with_drop.json", DOMAIN)
        )
        client.update_task.return_value = HabiticaTaskResponse.from_json(
            await async_load_fixture(hass, "task.json", DOMAIN)
        )
        client.create_task.return_value = HabiticaTaskResponse.from_json(
            await async_load_fixture(hass, "task.json", DOMAIN)
        )
        client.delete_task.return_value = HabiticaResponse.from_dict(
            {"data": {}, "success": True}
        )
        client.delete_completed_todos.return_value = HabiticaResponse.from_dict(
            {"data": {}, "success": True}
        )
        client.reorder_task.return_value = HabiticaTaskOrderResponse.from_dict(
            {"data": [], "success": True}
        )
        client.get_user_anonymized.return_value = (
            HabiticaUserAnonymizedResponse.from_json(
                await async_load_fixture(hass, "anonymized.json", DOMAIN)
            )
        )
        client.update_task.return_value = HabiticaTaskResponse.from_json(
            await async_load_fixture(hass, "task.json", DOMAIN)
        )
        client.create_tag.return_value = HabiticaTagResponse.from_json(
            await async_load_fixture(hass, "create_tag.json", DOMAIN)
        )
        client.create_task.return_value = HabiticaTaskResponse.from_json(
            await async_load_fixture(hass, "task.json", DOMAIN)
        )
        yield client


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.habitica.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_uuid4() -> Generator[MagicMock]:
    """Mock uuid4."""
    with patch(
        "homeassistant.components.habitica.services.uuid4", autospec=True
    ) as mock_uuid4:
        mock_uuid4.return_value = UUID("12345678-1234-5678-1234-567812345678")
        yield mock_uuid4
