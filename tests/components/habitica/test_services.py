"""Test Habitica actions."""

from collections.abc import Generator
from http import HTTPStatus
import json
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.habitica.const import (
    ATTR_ADD_CHECKLIST_ITEM,
    ATTR_ALIAS,
    ATTR_CLEAR_DATE,
    ATTR_CLEAR_REMINDER,
    ATTR_CONFIG_ENTRY,
    ATTR_COST,
    ATTR_COUNTER_DOWN,
    ATTR_COUNTER_UP,
    ATTR_DIRECTION,
    ATTR_ITEM,
    ATTR_FREQUENCY,
    ATTR_INTERVAL,
    ATTR_PRIORITY,
    ATTR_REMINDER,
    ATTR_REMINDER_TIME,
    ATTR_REMOVE_CHECKLIST_ITEM,
    ATTR_REMOVE_REMINDER,
    ATTR_REMOVE_REMINDER_TIME,
    ATTR_REMOVE_TAG,
    ATTR_REPEAT,
    ATTR_REPEAT_MONTHLY,
    ATTR_SCORE_CHECKLIST_ITEM,
    ATTR_SKILL,
    ATTR_TARGET,
    ATTR_START_DATE,
    ATTR_STREAK,
    ATTR_TAG,
    ATTR_TASK,
    ATTR_UNSCORE_CHECKLIST_ITEM,
    ATTR_UP_DOWN,
    DEFAULT_URL,
    DOMAIN,
    SERVICE_ABORT_QUEST,
    SERVICE_ACCEPT_QUEST,
    SERVICE_CANCEL_QUEST,
    SERVICE_CAST_SKILL,
    SERVICE_LEAVE_QUEST,
    SERVICE_REJECT_QUEST,
    SERVICE_SCORE_HABIT,
    SERVICE_SCORE_REWARD,
    SERVICE_START_QUEST,
    SERVICE_TRANSFORMATION,
    SERVICE_UPDATE_DAILY,
    SERVICE_UPDATE_HABIT,
    SERVICE_UPDATE_REWARD,
    SERVICE_UPDATE_TODO,
)
from homeassistant.components.todo import ATTR_DESCRIPTION, ATTR_RENAME
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_DATE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .conftest import load_json_object_fixture, mock_called_with

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

REQUEST_EXCEPTION_MSG = "Unable to connect to Habitica, try again later"
RATE_LIMIT_EXCEPTION_MSG = "Rate limit exceeded, try again later"


@pytest.fixture(autouse=True)
def services_only() -> Generator[None]:
    """Enable only services."""
    with patch(
        "homeassistant.components.habitica.PLATFORMS",
        [],
    ):
        yield


@pytest.fixture(autouse=True)
async def load_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_habitica: AiohttpClientMocker,
    services_only: Generator,
) -> None:
    """Load config entry."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED


@pytest.fixture(autouse=True)
def uuid_mock() -> Generator[None]:
    """Mock the UUID."""
    with patch(
        "uuid.uuid4", return_value="5d1935ff-80c8-443c-b2e9-733c66b44745"
    ) as uuid_mock:
        yield uuid_mock.return_value


@pytest.mark.parametrize(
    ("service_data", "item", "target_id"),
    [
        (
            {
                ATTR_TASK: "2f6fcabc-f670-4ec3-ba65-817e8deea490",
                ATTR_SKILL: "pickpocket",
            },
            "pickPocket",
            "2f6fcabc-f670-4ec3-ba65-817e8deea490",
        ),
        (
            {
                ATTR_TASK: "2f6fcabc-f670-4ec3-ba65-817e8deea490",
                ATTR_SKILL: "backstab",
            },
            "backStab",
            "2f6fcabc-f670-4ec3-ba65-817e8deea490",
        ),
        (
            {
                ATTR_TASK: "2f6fcabc-f670-4ec3-ba65-817e8deea490",
                ATTR_SKILL: "fireball",
            },
            "fireball",
            "2f6fcabc-f670-4ec3-ba65-817e8deea490",
        ),
        (
            {
                ATTR_TASK: "2f6fcabc-f670-4ec3-ba65-817e8deea490",
                ATTR_SKILL: "smash",
            },
            "smash",
            "2f6fcabc-f670-4ec3-ba65-817e8deea490",
        ),
        (
            {
                ATTR_TASK: "Rechnungen bezahlen",
                ATTR_SKILL: "smash",
            },
            "smash",
            "2f6fcabc-f670-4ec3-ba65-817e8deea490",
        ),
        (
            {
                ATTR_TASK: "pay_bills",
                ATTR_SKILL: "smash",
            },
            "smash",
            "2f6fcabc-f670-4ec3-ba65-817e8deea490",
        ),
    ],
    ids=[
        "cast pickpocket",
        "cast backstab",
        "cast fireball",
        "cast smash",
        "select task by name",
        "select task_by_alias",
    ],
)
async def test_cast_skill(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_habitica: AiohttpClientMocker,
    service_data: dict[str, Any],
    item: str,
    target_id: str,
) -> None:
    """Test Habitica cast skill action."""

    mock_habitica.post(
        f"{DEFAULT_URL}/api/v3/user/class/cast/{item}?targetId={target_id}",
        json={"success": True, "data": {}},
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CAST_SKILL,
        service_data={
            ATTR_CONFIG_ENTRY: config_entry.entry_id,
            **service_data,
        },
        return_response=True,
        blocking=True,
    )

    assert mock_called_with(
        mock_habitica,
        "post",
        f"{DEFAULT_URL}/api/v3/user/class/cast/{item}?targetId={target_id}",
    )


@pytest.mark.parametrize(
    (
        "service_data",
        "http_status",
        "expected_exception",
        "expected_exception_msg",
    ),
    [
        (
            {
                ATTR_TASK: "task-not-found",
                ATTR_SKILL: "smash",
            },
            HTTPStatus.OK,
            ServiceValidationError,
            "Unable to complete action, could not find the task 'task-not-found'",
        ),
        (
            {
                ATTR_TASK: "Rechnungen bezahlen",
                ATTR_SKILL: "smash",
            },
            HTTPStatus.TOO_MANY_REQUESTS,
            ServiceValidationError,
            RATE_LIMIT_EXCEPTION_MSG,
        ),
        (
            {
                ATTR_TASK: "Rechnungen bezahlen",
                ATTR_SKILL: "smash",
            },
            HTTPStatus.NOT_FOUND,
            ServiceValidationError,
            "Unable to cast skill, your character does not have the skill or spell smash",
        ),
        (
            {
                ATTR_TASK: "Rechnungen bezahlen",
                ATTR_SKILL: "smash",
            },
            HTTPStatus.UNAUTHORIZED,
            ServiceValidationError,
            "Unable to cast skill, not enough mana. Your character has 50 MP, but the skill costs 10 MP",
        ),
        (
            {
                ATTR_TASK: "Rechnungen bezahlen",
                ATTR_SKILL: "smash",
            },
            HTTPStatus.BAD_REQUEST,
            HomeAssistantError,
            REQUEST_EXCEPTION_MSG,
        ),
    ],
)
@pytest.mark.usefixtures("mock_habitica")
async def test_cast_skill_exceptions(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_habitica: AiohttpClientMocker,
    service_data: dict[str, Any],
    http_status: HTTPStatus,
    expected_exception: Exception,
    expected_exception_msg: str,
) -> None:
    """Test Habitica cast skill action exceptions."""

    mock_habitica.post(
        f"{DEFAULT_URL}/api/v3/user/class/cast/smash?targetId=2f6fcabc-f670-4ec3-ba65-817e8deea490",
        json={"success": True, "data": {}},
        status=http_status,
    )

    with pytest.raises(expected_exception, match=expected_exception_msg):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CAST_SKILL,
            service_data={
                ATTR_CONFIG_ENTRY: config_entry.entry_id,
                **service_data,
            },
            return_response=True,
            blocking=True,
        )


@pytest.mark.usefixtures("mock_habitica")
async def test_get_config_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_habitica: AiohttpClientMocker,
) -> None:
    """Test Habitica config entry exceptions."""

    with pytest.raises(
        ServiceValidationError,
        match="The selected character is not configured in Home Assistant",
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CAST_SKILL,
            service_data={
                ATTR_CONFIG_ENTRY: "0000000000000000",
                ATTR_TASK: "2f6fcabc-f670-4ec3-ba65-817e8deea490",
                ATTR_SKILL: "smash",
            },
            return_response=True,
            blocking=True,
        )

    assert await hass.config_entries.async_unload(config_entry.entry_id)

    with pytest.raises(
        ServiceValidationError,
        match="The selected character is currently not loaded or disabled in Home Assistant",
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CAST_SKILL,
            service_data={
                ATTR_CONFIG_ENTRY: config_entry.entry_id,
                ATTR_TASK: "2f6fcabc-f670-4ec3-ba65-817e8deea490",
                ATTR_SKILL: "smash",
            },
            return_response=True,
            blocking=True,
        )


@pytest.mark.parametrize(
    ("service", "command"),
    [
        (SERVICE_ABORT_QUEST, "abort"),
        (SERVICE_ACCEPT_QUEST, "accept"),
        (SERVICE_CANCEL_QUEST, "cancel"),
        (SERVICE_LEAVE_QUEST, "leave"),
        (SERVICE_REJECT_QUEST, "reject"),
        (SERVICE_START_QUEST, "force-start"),
    ],
    ids=[],
)
async def test_handle_quests(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_habitica: AiohttpClientMocker,
    service: str,
    command: str,
) -> None:
    """Test Habitica actions for quest handling."""

    mock_habitica.post(
        f"{DEFAULT_URL}/api/v3/groups/party/quests/{command}",
        json={"success": True, "data": {}},
    )

    await hass.services.async_call(
        DOMAIN,
        service,
        service_data={ATTR_CONFIG_ENTRY: config_entry.entry_id},
        return_response=True,
        blocking=True,
    )

    assert mock_called_with(
        mock_habitica,
        "post",
        f"{DEFAULT_URL}/api/v3/groups/party/quests/{command}",
    )


@pytest.mark.parametrize(
    (
        "http_status",
        "expected_exception",
        "expected_exception_msg",
    ),
    [
        (
            HTTPStatus.TOO_MANY_REQUESTS,
            ServiceValidationError,
            RATE_LIMIT_EXCEPTION_MSG,
        ),
        (
            HTTPStatus.NOT_FOUND,
            ServiceValidationError,
            "Unable to complete action, quest or group not found",
        ),
        (
            HTTPStatus.UNAUTHORIZED,
            ServiceValidationError,
            "Action not allowed, only quest leader or group leader can perform this action",
        ),
        (
            HTTPStatus.BAD_REQUEST,
            HomeAssistantError,
            REQUEST_EXCEPTION_MSG,
        ),
    ],
)
@pytest.mark.usefixtures("mock_habitica")
async def test_handle_quests_exceptions(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_habitica: AiohttpClientMocker,
    http_status: HTTPStatus,
    expected_exception: Exception,
    expected_exception_msg: str,
) -> None:
    """Test Habitica handle quests action exceptions."""

    mock_habitica.post(
        f"{DEFAULT_URL}/api/v3/groups/party/quests/accept",
        json={"success": True, "data": {}},
        status=http_status,
    )

    with pytest.raises(expected_exception, match=expected_exception_msg):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ACCEPT_QUEST,
            service_data={ATTR_CONFIG_ENTRY: config_entry.entry_id},
            return_response=True,
            blocking=True,
        )


@pytest.mark.parametrize(
    ("service", "service_data", "task_id"),
    [
        (
            SERVICE_SCORE_HABIT,
            {
                ATTR_TASK: "e97659e0-2c42-4599-a7bb-00282adc410d",
                ATTR_DIRECTION: "up",
            },
            "e97659e0-2c42-4599-a7bb-00282adc410d",
        ),
        (
            SERVICE_SCORE_HABIT,
            {
                ATTR_TASK: "e97659e0-2c42-4599-a7bb-00282adc410d",
                ATTR_DIRECTION: "down",
            },
            "e97659e0-2c42-4599-a7bb-00282adc410d",
        ),
        (
            SERVICE_SCORE_REWARD,
            {
                ATTR_TASK: "5e2ea1df-f6e6-4ba3-bccb-97c5ec63e99b",
            },
            "5e2ea1df-f6e6-4ba3-bccb-97c5ec63e99b",
        ),
        (
            SERVICE_SCORE_HABIT,
            {
                ATTR_TASK: "Füge eine Aufgabe zu Habitica hinzu",
                ATTR_DIRECTION: "up",
            },
            "e97659e0-2c42-4599-a7bb-00282adc410d",
        ),
        (
            SERVICE_SCORE_HABIT,
            {
                ATTR_TASK: "create_a_task",
                ATTR_DIRECTION: "up",
            },
            "e97659e0-2c42-4599-a7bb-00282adc410d",
        ),
    ],
    ids=[
        "habit score up",
        "habit score down",
        "buy reward",
        "match task by name",
        "match task by alias",
    ],
)
async def test_score_task(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_habitica: AiohttpClientMocker,
    service: str,
    service_data: dict[str, Any],
    task_id: str,
) -> None:
    """Test Habitica score task action."""

    mock_habitica.post(
        f"{DEFAULT_URL}/api/v3/tasks/{task_id}/score/{service_data.get(ATTR_DIRECTION, "up")}",
        json={"success": True, "data": {}},
    )

    await hass.services.async_call(
        DOMAIN,
        service,
        service_data={
            ATTR_CONFIG_ENTRY: config_entry.entry_id,
            **service_data,
        },
        return_response=True,
        blocking=True,
    )

    assert mock_called_with(
        mock_habitica,
        "post",
        f"{DEFAULT_URL}/api/v3/tasks/{task_id}/score/{service_data.get(ATTR_DIRECTION, "up")}",
    )


@pytest.mark.parametrize(
    (
        "service_data",
        "http_status",
        "expected_exception",
        "expected_exception_msg",
    ),
    [
        (
            {
                ATTR_TASK: "task does not exist",
                ATTR_DIRECTION: "up",
            },
            HTTPStatus.OK,
            ServiceValidationError,
            "Unable to complete action, could not find the task 'task does not exist'",
        ),
        (
            {
                ATTR_TASK: "e97659e0-2c42-4599-a7bb-00282adc410d",
                ATTR_DIRECTION: "up",
            },
            HTTPStatus.TOO_MANY_REQUESTS,
            ServiceValidationError,
            RATE_LIMIT_EXCEPTION_MSG,
        ),
        (
            {
                ATTR_TASK: "e97659e0-2c42-4599-a7bb-00282adc410d",
                ATTR_DIRECTION: "up",
            },
            HTTPStatus.BAD_REQUEST,
            HomeAssistantError,
            REQUEST_EXCEPTION_MSG,
        ),
        (
            {
                ATTR_TASK: "5e2ea1df-f6e6-4ba3-bccb-97c5ec63e99b",
                ATTR_DIRECTION: "up",
            },
            HTTPStatus.UNAUTHORIZED,
            HomeAssistantError,
            "Unable to buy reward, not enough gold. Your character has 137.63 GP, but the reward costs 10 GP",
        ),
    ],
)
@pytest.mark.usefixtures("mock_habitica")
async def test_score_task_exceptions(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_habitica: AiohttpClientMocker,
    service_data: dict[str, Any],
    http_status: HTTPStatus,
    expected_exception: Exception,
    expected_exception_msg: str,
) -> None:
    """Test Habitica score task action exceptions."""

    mock_habitica.post(
        f"{DEFAULT_URL}/api/v3/tasks/e97659e0-2c42-4599-a7bb-00282adc410d/score/up",
        json={"success": True, "data": {}},
        status=http_status,
    )
    mock_habitica.post(
        f"{DEFAULT_URL}/api/v3/tasks/5e2ea1df-f6e6-4ba3-bccb-97c5ec63e99b/score/up",
        json={"success": True, "data": {}},
        status=http_status,
    )

    with pytest.raises(expected_exception, match=expected_exception_msg):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SCORE_HABIT,
            service_data={
                ATTR_CONFIG_ENTRY: config_entry.entry_id,
                **service_data,
            },
            return_response=True,
            blocking=True,
        )


@pytest.mark.parametrize(
    ("service_data", "item", "target_id"),
    [
        (
            {
                ATTR_TARGET: "a380546a-94be-4b8e-8a0b-23e0d5c03303",
                ATTR_ITEM: "spooky_sparkles",
            },
            "spookySparkles",
            "a380546a-94be-4b8e-8a0b-23e0d5c03303",
        ),
        (
            {
                ATTR_TARGET: "a380546a-94be-4b8e-8a0b-23e0d5c03303",
                ATTR_ITEM: "shiny_seed",
            },
            "shinySeed",
            "a380546a-94be-4b8e-8a0b-23e0d5c03303",
        ),
        (
            {
                ATTR_TARGET: "a380546a-94be-4b8e-8a0b-23e0d5c03303",
                ATTR_ITEM: "seafoam",
            },
            "seafoam",
            "a380546a-94be-4b8e-8a0b-23e0d5c03303",
        ),
        (
            {
                ATTR_TARGET: "a380546a-94be-4b8e-8a0b-23e0d5c03303",
                ATTR_ITEM: "snowball",
            },
            "snowball",
            "a380546a-94be-4b8e-8a0b-23e0d5c03303",
        ),
        (
            {
                ATTR_TARGET: "test-user",
                ATTR_ITEM: "spooky_sparkles",
            },
            "spookySparkles",
            "a380546a-94be-4b8e-8a0b-23e0d5c03303",
        ),
        (
            {
                ATTR_TARGET: "test-username",
                ATTR_ITEM: "spooky_sparkles",
            },
            "spookySparkles",
            "a380546a-94be-4b8e-8a0b-23e0d5c03303",
        ),
        (
            {
                ATTR_TARGET: "ffce870c-3ff3-4fa4-bad1-87612e52b8e7",
                ATTR_ITEM: "spooky_sparkles",
            },
            "spookySparkles",
            "ffce870c-3ff3-4fa4-bad1-87612e52b8e7",
        ),
        (
            {
                ATTR_TARGET: "test-partymember-username",
                ATTR_ITEM: "spooky_sparkles",
            },
            "spookySparkles",
            "ffce870c-3ff3-4fa4-bad1-87612e52b8e7",
        ),
        (
            {
                ATTR_TARGET: "test-partymember-displayname",
                ATTR_ITEM: "spooky_sparkles",
            },
            "spookySparkles",
            "ffce870c-3ff3-4fa4-bad1-87612e52b8e7",
        ),
    ],
    ids=[],
)
async def test_transformation(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_habitica: AiohttpClientMocker,
    service_data: dict[str, Any],
    item: str,
    target_id: str,
) -> None:
    """Test Habitica user transformation item action."""
    mock_habitica.get(
        f"{DEFAULT_URL}/api/v3/groups/party/members",
        json=load_json_object_fixture("party_members.json", DOMAIN),
    )
    mock_habitica.post(
        f"{DEFAULT_URL}/api/v3/user/class/cast/{item}?targetId={target_id}",
        json={"success": True, "data": {}},
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_TRANSFORMATION,
        service_data={
            ATTR_CONFIG_ENTRY: config_entry.entry_id,
            **service_data,
        },
        return_response=True,
        blocking=True,
    )

    assert mock_called_with(
        mock_habitica,
        "post",
        f"{DEFAULT_URL}/api/v3/user/class/cast/{item}?targetId={target_id}",
    )


@pytest.mark.parametrize(
    (
        "service_data",
        "http_status_members",
        "http_status_cast",
        "expected_exception",
        "expected_exception_msg",
    ),
    [
        (
            {
                ATTR_TARGET: "user-not-found",
                ATTR_ITEM: "spooky_sparkles",
            },
            HTTPStatus.OK,
            HTTPStatus.OK,
            ServiceValidationError,
            "Unable to find target 'user-not-found' in your party",
        ),
        (
            {
                ATTR_TARGET: "test-partymember-username",
                ATTR_ITEM: "spooky_sparkles",
            },
            HTTPStatus.TOO_MANY_REQUESTS,
            HTTPStatus.OK,
            ServiceValidationError,
            RATE_LIMIT_EXCEPTION_MSG,
        ),
        (
            {
                ATTR_TARGET: "test-partymember-username",
                ATTR_ITEM: "spooky_sparkles",
            },
            HTTPStatus.NOT_FOUND,
            HTTPStatus.OK,
            ServiceValidationError,
            "Unable to find target, you are currently not in a party. You can only target yourself",
        ),
        (
            {
                ATTR_TARGET: "test-partymember-username",
                ATTR_ITEM: "spooky_sparkles",
            },
            HTTPStatus.BAD_REQUEST,
            HTTPStatus.OK,
            HomeAssistantError,
            "Unable to connect to Habitica, try again later",
        ),
        (
            {
                ATTR_TARGET: "test-partymember-username",
                ATTR_ITEM: "spooky_sparkles",
            },
            HTTPStatus.OK,
            HTTPStatus.TOO_MANY_REQUESTS,
            ServiceValidationError,
            RATE_LIMIT_EXCEPTION_MSG,
        ),
        (
            {
                ATTR_TARGET: "test-partymember-username",
                ATTR_ITEM: "spooky_sparkles",
            },
            HTTPStatus.OK,
            HTTPStatus.UNAUTHORIZED,
            ServiceValidationError,
            "Unable to use spooky_sparkles, you don't own this item",
        ),
        (
            {
                ATTR_TARGET: "test-partymember-username",
                ATTR_ITEM: "spooky_sparkles",
            },
            HTTPStatus.OK,
            HTTPStatus.BAD_REQUEST,
            HomeAssistantError,
            "Unable to connect to Habitica, try again later",
        ),
    ],
)
@pytest.mark.usefixtures("mock_habitica")
async def test_transformation_exceptions(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_habitica: AiohttpClientMocker,
    service_data: dict[str, Any],
    http_status_members: HTTPStatus,
    http_status_cast: HTTPStatus,
    expected_exception: Exception,
    expected_exception_msg: str,
) -> None:
    """Test Habitica transformation action exceptions."""
    mock_habitica.get(
        f"{DEFAULT_URL}/api/v3/groups/party/members",
        json=load_json_object_fixture("party_members.json", DOMAIN),
        status=http_status_members,
    )
    mock_habitica.post(
        f"{DEFAULT_URL}/api/v3/user/class/cast/spookySparkles?targetId=ffce870c-3ff3-4fa4-bad1-87612e52b8e7",
        json={"success": True, "data": {}},
        status=http_status_cast,
    )

    with pytest.raises(expected_exception, match=expected_exception_msg):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_TRANSFORMATION,
            service_data={
                ATTR_CONFIG_ENTRY: config_entry.entry_id,
                **service_data,
            },
            return_response=True,
            blocking=True,
        )


@pytest.mark.parametrize(
    ("service_data", "expected"),
    [
        (
            {ATTR_TASK: "Zahnseide benutzen"},
            "{}",
        ),
        (
            {ATTR_TASK: "564b9ac9-c53d-4638-9e7f-1cd96fe19baa"},
            "{}",
        ),
        (
            {ATTR_TASK: "alias_zahnseide_benutzen"},
            "{}",
        ),
        (
            {
                ATTR_RENAME: "new-task-name",
            },
            '{"text": "new-task-name"}',
        ),
        (
            {
                ATTR_DESCRIPTION: "new-task-description",
            },
            '{"notes": "new-task-description"}',
        ),
        (
            {
                ATTR_PRIORITY: "trivial",
            },
            '{"priority": 0.1}',
        ),
        (
            {
                ATTR_PRIORITY: "easy",
            },
            '{"priority": 1}',
        ),
        (
            {
                ATTR_PRIORITY: "medium",
            },
            '{"priority": 1.5}',
        ),
        (
            {
                ATTR_PRIORITY: "hard",
            },
            '{"priority": 2}',
        ),
        (
            {
                ATTR_START_DATE: "2024-10-14",
            },
            '{"startDate": "2024-10-14T00:00:00"}',
        ),
        (
            {
                ATTR_FREQUENCY: "daily",
            },
            '{"frequency": "daily"}',
        ),
        (
            {
                ATTR_FREQUENCY: "weekly",
            },
            '{"frequency": "weekly"}',
        ),
        (
            {
                ATTR_FREQUENCY: "monthly",
            },
            '{"frequency": "monthly"}',
        ),
        (
            {
                ATTR_FREQUENCY: "yearly",
            },
            '{"frequency": "yearly"}',
        ),
        (
            {
                ATTR_INTERVAL: 1,
            },
            '{"everyX": 1}',
        ),
        (
            {
                ATTR_REPEAT: ["su", "t", "th", "s"],
            },
            '{"repeat": {"m": false, "t": true, "w": false, "th": true, "f": false, "s": true, "su": true}}',
        ),
        (
            {
                ATTR_FREQUENCY: "monthly",
                ATTR_REPEAT_MONTHLY: "day_of_month",
            },
            '{"frequency": "monthly", "daysOfMonth": 6, "weeksOfMonth": []}',
        ),
        (
            {
                ATTR_FREQUENCY: "monthly",
                ATTR_REPEAT_MONTHLY: "day_of_week",
            },
            (
                '{"frequency": "monthly", "weeksOfMonth": 0, "repeat": {"m": false, "t": false, "w": '
                'false, "th": false, "f": false, "s": true, "su": false}, "daysOfMonth": []}'
            ),
        ),
        (
            {
                ATTR_STREAK: 100,
            },
            '{"streak": 100}',
        ),
        (
            {
                ATTR_REMINDER_TIME: ["20:00", "22:00"],
            },
            (
                '{"reminders": [{"id": "5d1935ff-80c8-443c-b2e9-733c66b44745", "startDate": "", "time": "2024-10-14T20:00:00+00:00"},'
                ' {"id": "5d1935ff-80c8-443c-b2e9-733c66b44745", "startDate": "", "time": "2024-10-14T22:00:00+00:00"},'
                ' {"id": "e2c62b7f-2e20-474b-a268-779252b25e8c", "startDate": "", "time": "2024-10-14T20:30:00+00:00"},'
                ' {"id": "4c472190-efba-4277-9d3e-ce7a9e1262ba", "startDate": "", "time": "2024-10-14T22:30:00+00:00"}]}'
            ),
        ),
        (
            {
                ATTR_REMOVE_REMINDER_TIME: ["22:30"],
            },
            '{"reminders": [{"id": "e2c62b7f-2e20-474b-a268-779252b25e8c", "startDate": "", "time": "2024-10-14T20:30:00+00:00"}]}',
        ),
        (
            {
                ATTR_CLEAR_REMINDER: True,
            },
            '{"reminders": []}',
        ),
    ],
    ids=[
        "match_task_by_name",
        "match_task_by_id",
        "match_task_by_alias",
        "rename",
        "description",
        "difficulty_trivial",
        "difficulty_easy",
        "difficulty_medium",
        "difficulty_hard",
        "start_date",
        "frequency_daily",
        "frequency_weekly",
        "frequency_monthly",
        "frequency_yearly",
        "interval",
        "repeat_days",
        "repeat_day_of_month",
        "repeat_day_of_week",
        "streak",
        "add_reminders",
        "remove_reminders",
        "clear_reminders",
    ],
)
async def test_update_daily(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_habitica: AiohttpClientMocker,
    service_data: dict[str, Any],
    expected: dict[str, Any],
) -> None:
    """Test Habitica update_daily action."""

    mock_habitica.put(
        f"{DEFAULT_URL}/api/v3/tasks/564b9ac9-c53d-4638-9e7f-1cd96fe19baa",
        json={"success": True, "data": {}},
    )

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await hass.services.async_call(
        DOMAIN,
        SERVICE_UPDATE_DAILY,
        service_data={
            ATTR_CONFIG_ENTRY: config_entry.entry_id,
            ATTR_TASK: "564b9ac9-c53d-4638-9e7f-1cd96fe19baa",
            **service_data,
        },
        return_response=True,
        blocking=True,
    )

    mock_call = mock_called_with(
        mock_habitica,
        "PUT",
        f"{DEFAULT_URL}/api/v3/tasks/564b9ac9-c53d-4638-9e7f-1cd96fe19baa",
    )
    assert mock_call
    assert mock_call[2] == expected


@pytest.mark.parametrize(
    ("service_data", "item", "target_id"),
    [
        (
            {
                ATTR_TASK: "2f6fcabc-f670-4ec3-ba65-817e8deea490",
                ATTR_SKILL: "pickpocket",
            },
            "pickPocket",
            "2f6fcabc-f670-4ec3-ba65-817e8deea490",
        ),
        (
            {
                ATTR_TASK: "2f6fcabc-f670-4ec3-ba65-817e8deea490",
                ATTR_SKILL: "backstab",
            },
            "backStab",
            "2f6fcabc-f670-4ec3-ba65-817e8deea490",
        ),
        (
            {
                ATTR_TASK: "2f6fcabc-f670-4ec3-ba65-817e8deea490",
                ATTR_SKILL: "fireball",
            },
            "fireball",
            "2f6fcabc-f670-4ec3-ba65-817e8deea490",
        ),
        (
            {
                ATTR_TASK: "2f6fcabc-f670-4ec3-ba65-817e8deea490",
                ATTR_SKILL: "smash",
            },
            "smash",
            "2f6fcabc-f670-4ec3-ba65-817e8deea490",
        ),
        (
            {
                ATTR_TASK: "Rechnungen bezahlen",
                ATTR_SKILL: "smash",
            },
            "smash",
            "2f6fcabc-f670-4ec3-ba65-817e8deea490",
        ),
        (
            {
                ATTR_TASK: "pay_bills",
                ATTR_SKILL: "smash",
            },
            "smash",
            "2f6fcabc-f670-4ec3-ba65-817e8deea490",
        ),
    ],
    ids=[
        "cast pickpocket",
        "cast backstab",
        "cast fireball",
        "cast smash",
        "select task by name",
        "select task_by_alias",
    ],
)
async def test_cast_skill(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_habitica: AiohttpClientMocker,
    service_data: dict[str, Any],
    item: str,
    target_id: str,
) -> None:
    """Test Habitica cast skill action."""

    mock_habitica.post(
        f"{DEFAULT_URL}/api/v3/user/class/cast/{item}?targetId={target_id}",
        json={"success": True, "data": {}},
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CAST_SKILL,
        service_data={
            ATTR_CONFIG_ENTRY: config_entry.entry_id,
            **service_data,
        },
        return_response=True,
        blocking=True,
    )

    assert mock_called_with(
        mock_habitica,
        "post",
        f"{DEFAULT_URL}/api/v3/user/class/cast/{item}?targetId={target_id}",
    )


@pytest.mark.parametrize(
    (
        "service_data",
        "http_status",
        "expected_exception",
        "expected_exception_msg",
    ),
    [
        (
            {
                ATTR_TASK: "task-not-found",
                ATTR_SKILL: "smash",
            },
            HTTPStatus.OK,
            ServiceValidationError,
            "Unable to complete action, could not find the task 'task-not-found'",
        ),
        (
            {
                ATTR_TASK: "Rechnungen bezahlen",
                ATTR_SKILL: "smash",
            },
            HTTPStatus.TOO_MANY_REQUESTS,
            ServiceValidationError,
            RATE_LIMIT_EXCEPTION_MSG,
        ),
        (
            {
                ATTR_TASK: "Rechnungen bezahlen",
                ATTR_SKILL: "smash",
            },
            HTTPStatus.NOT_FOUND,
            ServiceValidationError,
            "Unable to cast skill, your character does not have the skill or spell smash",
        ),
        (
            {
                ATTR_TASK: "Rechnungen bezahlen",
                ATTR_SKILL: "smash",
            },
            HTTPStatus.UNAUTHORIZED,
            ServiceValidationError,
            "Unable to cast skill, not enough mana. Your character has 50 MP, but the skill costs 10 MP",
        ),
        (
            {
                ATTR_TASK: "Rechnungen bezahlen",
                ATTR_SKILL: "smash",
            },
            HTTPStatus.BAD_REQUEST,
            HomeAssistantError,
            REQUEST_EXCEPTION_MSG,
        ),
    ],
)
@pytest.mark.usefixtures("mock_habitica")
async def test_cast_skill_exceptions(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_habitica: AiohttpClientMocker,
    service_data: dict[str, Any],
    http_status: HTTPStatus,
    expected_exception: Exception,
    expected_exception_msg: str,
) -> None:
    """Test Habitica cast skill action exceptions."""

    mock_habitica.post(
        f"{DEFAULT_URL}/api/v3/user/class/cast/smash?targetId=2f6fcabc-f670-4ec3-ba65-817e8deea490",
        json={"success": True, "data": {}},
        status=http_status,
    )

    with pytest.raises(expected_exception, match=expected_exception_msg):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CAST_SKILL,
            service_data={
                ATTR_CONFIG_ENTRY: config_entry.entry_id,
                **service_data,
            },
            return_response=True,
            blocking=True,
        )


@pytest.mark.usefixtures("mock_habitica")
async def test_get_config_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_habitica: AiohttpClientMocker,
) -> None:
    """Test Habitica config entry exceptions."""

    with pytest.raises(
        ServiceValidationError,
        match="The selected character is not configured in Home Assistant",
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CAST_SKILL,
            service_data={
                ATTR_CONFIG_ENTRY: "0000000000000000",
                ATTR_TASK: "2f6fcabc-f670-4ec3-ba65-817e8deea490",
                ATTR_SKILL: "smash",
            },
            return_response=True,
            blocking=True,
        )

    assert await hass.config_entries.async_unload(config_entry.entry_id)

    with pytest.raises(
        ServiceValidationError,
        match="The selected character is currently not loaded or disabled in Home Assistant",
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CAST_SKILL,
            service_data={
                ATTR_CONFIG_ENTRY: config_entry.entry_id,
                ATTR_TASK: "2f6fcabc-f670-4ec3-ba65-817e8deea490",
                ATTR_SKILL: "smash",
            },
            return_response=True,
            blocking=True,
        )


@pytest.mark.parametrize(
    ("service", "command"),
    [
        (SERVICE_ABORT_QUEST, "abort"),
        (SERVICE_ACCEPT_QUEST, "accept"),
        (SERVICE_CANCEL_QUEST, "cancel"),
        (SERVICE_LEAVE_QUEST, "leave"),
        (SERVICE_REJECT_QUEST, "reject"),
        (SERVICE_START_QUEST, "force-start"),
    ],
    ids=[],
)
async def test_handle_quests(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_habitica: AiohttpClientMocker,
    service: str,
    command: str,
) -> None:
    """Test Habitica actions for quest handling."""

    mock_habitica.post(
        f"{DEFAULT_URL}/api/v3/groups/party/quests/{command}",
        json={"success": True, "data": {}},
    )

    await hass.services.async_call(
        DOMAIN,
        service,
        service_data={ATTR_CONFIG_ENTRY: config_entry.entry_id},
        return_response=True,
        blocking=True,
    )

    assert mock_called_with(
        mock_habitica,
        "post",
        f"{DEFAULT_URL}/api/v3/groups/party/quests/{command}",
    )


@pytest.mark.parametrize(
    (
        "http_status",
        "expected_exception",
        "expected_exception_msg",
    ),
    [
        (
            HTTPStatus.TOO_MANY_REQUESTS,
            ServiceValidationError,
            RATE_LIMIT_EXCEPTION_MSG,
        ),
        (
            HTTPStatus.NOT_FOUND,
            ServiceValidationError,
            "Unable to complete action, quest or group not found",
        ),
        (
            HTTPStatus.UNAUTHORIZED,
            ServiceValidationError,
            "Action not allowed, only quest leader or group leader can perform this action",
        ),
        (
            HTTPStatus.BAD_REQUEST,
            HomeAssistantError,
            REQUEST_EXCEPTION_MSG,
        ),
    ],
)
@pytest.mark.usefixtures("mock_habitica")
async def test_handle_quests_exceptions(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_habitica: AiohttpClientMocker,
    http_status: HTTPStatus,
    expected_exception: Exception,
    expected_exception_msg: str,
) -> None:
    """Test Habitica handle quests action exceptions."""

    mock_habitica.post(
        f"{DEFAULT_URL}/api/v3/groups/party/quests/accept",
        json={"success": True, "data": {}},
        status=http_status,
    )

    with pytest.raises(expected_exception, match=expected_exception_msg):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ACCEPT_QUEST,
            service_data={ATTR_CONFIG_ENTRY: config_entry.entry_id},
            return_response=True,
            blocking=True,
        )


@pytest.mark.parametrize(
    ("service_data", "expected"),
    [
        (
            {ATTR_TASK: "Zahnseide benutzen"},
            "{}",
        ),
        (
            {ATTR_TASK: "564b9ac9-c53d-4638-9e7f-1cd96fe19baa"},
            "{}",
        ),
        (
            {ATTR_TASK: "alias_zahnseide_benutzen"},
            "{}",
        ),
        (
            {
                ATTR_RENAME: "new-task-name",
            },
            '{"text": "new-task-name"}',
        ),
        (
            {
                ATTR_DESCRIPTION: "new-task-description",
            },
            '{"notes": "new-task-description"}',
        ),
        (
            {ATTR_ALIAS: "test-alias"},
            '{"alias": "test-alias"}',
        ),
        (
            {
                ATTR_PRIORITY: "trivial",
            },
            '{"priority": 0.1}',
        ),
        (
            {
                ATTR_PRIORITY: "easy",
            },
            '{"priority": 1}',
        ),
        (
            {
                ATTR_PRIORITY: "medium",
            },
            '{"priority": 1.5}',
        ),
        (
            {
                ATTR_PRIORITY: "hard",
            },
            '{"priority": 2}',
        ),
        (
            {
                ATTR_START_DATE: "2024-10-14",
            },
            '{"startDate": "2024-10-14T00:00:00"}',
        ),
        (
            {
                ATTR_FREQUENCY: "daily",
            },
            '{"frequency": "daily"}',
        ),
        (
            {
                ATTR_FREQUENCY: "weekly",
            },
            '{"frequency": "weekly"}',
        ),
        (
            {
                ATTR_FREQUENCY: "monthly",
            },
            '{"frequency": "monthly"}',
        ),
        (
            {
                ATTR_FREQUENCY: "yearly",
            },
            '{"frequency": "yearly"}',
        ),
        (
            {
                ATTR_INTERVAL: 1,
            },
            '{"everyX": 1}',
        ),
        (
            {
                ATTR_REPEAT: ["su", "t", "th", "s"],
            },
            '{"repeat": {"m": false, "t": true, "w": false, "th": true, "f": false, "s": true, "su": true}}',
        ),
        (
            {
                ATTR_FREQUENCY: "monthly",
                ATTR_REPEAT_MONTHLY: "day_of_month",
            },
            '{"frequency": "monthly", "daysOfMonth": 6, "weeksOfMonth": []}',
        ),
        (
            {
                ATTR_FREQUENCY: "monthly",
                ATTR_REPEAT_MONTHLY: "day_of_week",
            },
            (
                '{"frequency": "monthly", "weeksOfMonth": 0, "repeat": {"m": false, "t": false, "w": '
                'false, "th": false, "f": false, "s": true, "su": false}, "daysOfMonth": []}'
            ),
        ),
        (
            {
                ATTR_STREAK: 100,
            },
            '{"streak": 100}',
        ),
        (
            {
                ATTR_REMINDER_TIME: ["20:00", "22:00"],
            },
            (
                '{"reminders": [{"id": "5d1935ff-80c8-443c-b2e9-733c66b44745", "startDate": "", "time": "2024-10-14T20:00:00+00:00"},'
                ' {"id": "5d1935ff-80c8-443c-b2e9-733c66b44745", "startDate": "", "time": "2024-10-14T22:00:00+00:00"},'
                ' {"id": "e2c62b7f-2e20-474b-a268-779252b25e8c", "startDate": "", "time": "2024-10-14T20:30:00+00:00"},'
                ' {"id": "4c472190-efba-4277-9d3e-ce7a9e1262ba", "startDate": "", "time": "2024-10-14T22:30:00+00:00"}]}'
            ),
        ),
        (
            {
                ATTR_REMOVE_REMINDER_TIME: ["22:30"],
            },
            '{"reminders": [{"id": "e2c62b7f-2e20-474b-a268-779252b25e8c", "startDate": "", "time": "2024-10-14T20:30:00+00:00"}]}',
        ),
        (
            {
                ATTR_CLEAR_REMINDER: True,
            },
            '{"reminders": []}',
        ),
    ],
    ids=[
        "match_task_by_name",
        "match_task_by_id",
        "match_task_by_alias",
        "rename",
        "description",
        "alias",
        "difficulty_trivial",
        "difficulty_easy",
        "difficulty_medium",
        "difficulty_hard",
        "start_date",
        "frequency_daily",
        "frequency_weekly",
        "frequency_monthly",
        "frequency_yearly",
        "interval",
        "repeat_days",
        "repeat_day_of_month",
        "repeat_day_of_week",
        "streak",
        "add_reminders",
        "remove_reminders",
        "clear_reminders",
    ],
)
@pytest.mark.freeze_time("2024-10-14 00:00:00")
async def test_update_daily(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_habitica: AiohttpClientMocker,
    service_data: dict[str, Any],
    expected: dict[str, Any],
) -> None:
    """Test Habitica update_daily action."""
    task_id = "564b9ac9-c53d-4638-9e7f-1cd96fe19baa"
    mock_habitica.put(
        f"{DEFAULT_URL}/api/v3/tasks/{task_id}",
        json={"success": True, "data": {}},
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_UPDATE_DAILY,
        service_data={
            ATTR_CONFIG_ENTRY: config_entry.entry_id,
            ATTR_TASK: task_id,
            **service_data,
        },
        return_response=True,
        blocking=True,
    )

    mock_call = mock_called_with(
        mock_habitica,
        "PUT",
        f"{DEFAULT_URL}/api/v3/tasks/{task_id}",
    )
    assert mock_call
    assert mock_call[2] == expected


@pytest.mark.parametrize(
    ("service_data"),
    [
        (
            {
                ATTR_FREQUENCY: "monthly",
                ATTR_REPEAT: ["su", "t", "th", "s"],
            }
        ),
        (
            {
                ATTR_FREQUENCY: "weekly",
                ATTR_REPEAT_MONTHLY: "day_of_month",
            }
        ),
    ],
    ids=["frequency_not_weekly", "frequency_not_monthly"],
)
@pytest.mark.freeze_time("2024-10-14 00:00:00")
@pytest.mark.usefixtures("mock_habitica")
async def test_update_daily_exceptions(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    service_data: dict[str, Any],
) -> None:
    """Test Habitica update_daily action exceptions."""
    task_id = "564b9ac9-c53d-4638-9e7f-1cd96fe19baa"

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_UPDATE_DAILY,
            service_data={
                ATTR_CONFIG_ENTRY: config_entry.entry_id,
                ATTR_TASK: task_id,
                **service_data,
            },
            return_response=True,
            blocking=True,
        )


@pytest.mark.parametrize(
    ("status", "exception"),
    [
        (HTTPStatus.TOO_MANY_REQUESTS, ServiceValidationError),
        (HTTPStatus.BAD_GATEWAY, HomeAssistantError),
    ],
)
@pytest.mark.usefixtures("mock_habitica")
async def test_update_task_exceptions(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_habitica: AiohttpClientMocker,
    status: HTTPStatus,
    exception: Exception,
) -> None:
    """Test Habitica task action exceptions."""
    task_id = "564b9ac9-c53d-4638-9e7f-1cd96fe19baa"

    mock_habitica.put(
        f"{DEFAULT_URL}/api/v3/tasks/{task_id}",
        status=status,
    )
    with pytest.raises(exception):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_UPDATE_DAILY,
            service_data={
                ATTR_CONFIG_ENTRY: config_entry.entry_id,
                ATTR_TASK: task_id,
            },
            return_response=True,
            blocking=True,
        )


@pytest.mark.parametrize(
    ("service_data", "expected"),
    [
        (
            {ATTR_DATE: "2024-10-14"},
            '{"date": "2024-10-14T00:00:00"}',
        ),
        (
            {ATTR_CLEAR_DATE: True},
            '{"date": null}',
        ),
        (
            {ATTR_REMINDER: ["2024-12-20T22:00"]},
            (
                '{"reminders": [{"id": "5d1935ff-80c8-443c-b2e9-733c66b44745", "time": "2024-12-20T22:00:00"},'
                ' {"id": "30224d1d-705b-4817-9d65-50f0481607f4", "time": "2024-12-20T22:30:00"}]}'
            ),
        ),
        (
            {ATTR_REMOVE_REMINDER: ["2024-12-20T22:30"]},
            '{"reminders": []}',
        ),
        (
            {ATTR_CLEAR_REMINDER: True},
            '{"reminders": []}',
        ),
    ],
    ids=[
        "due_date",
        "clear_due_date",
        "add_reminders",
        "remove_reminders",
        "clear_reminders",
    ],
)
async def test_update_todo(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_habitica: AiohttpClientMocker,
    service_data: dict[str, Any],
    expected: dict[str, Any],
) -> None:
    """Test Habitica update_todo action."""
    task_id = "2f6fcabc-f670-4ec3-ba65-817e8deea490"
    mock_habitica.put(
        f"{DEFAULT_URL}/api/v3/tasks/{task_id}",
        json={"success": True, "data": {}},
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_UPDATE_TODO,
        service_data={
            ATTR_CONFIG_ENTRY: config_entry.entry_id,
            ATTR_TASK: task_id,
            **service_data,
        },
        return_response=True,
        blocking=True,
    )

    mock_call = mock_called_with(
        mock_habitica,
        "PUT",
        f"{DEFAULT_URL}/api/v3/tasks/{task_id}",
    )
    assert mock_call
    assert mock_call[2] == expected


@pytest.mark.parametrize(
    ("service_data", "expected"),
    [
        (
            {ATTR_UP_DOWN: ["positive", "negative"]},
            '{"up": true, "down": true}',
        ),
        (
            {ATTR_COUNTER_DOWN: 111},
            '{"counterDown": 111}',
        ),
        (
            {ATTR_COUNTER_UP: 222},
            '{"counterUp": 222}',
        ),
    ],
    ids=[
        "positive_negative_habit",
        "counter_up",
        "counter_down",
    ],
)
async def test_update_habit(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_habitica: AiohttpClientMocker,
    service_data: dict[str, Any],
    expected: dict[str, Any],
) -> None:
    """Test Habitica update_habit action."""
    task_id = "1d147de6-5c02-4740-8e2f-71d3015a37f4"
    mock_habitica.put(
        f"{DEFAULT_URL}/api/v3/tasks/{task_id}",
        json={"success": True, "data": {}},
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_UPDATE_HABIT,
        service_data={
            ATTR_CONFIG_ENTRY: config_entry.entry_id,
            ATTR_TASK: task_id,
            **service_data,
        },
        return_response=True,
        blocking=True,
    )

    mock_call = mock_called_with(
        mock_habitica,
        "PUT",
        f"{DEFAULT_URL}/api/v3/tasks/{task_id}",
    )
    assert mock_call
    assert mock_call[2] == expected


async def test_update_reward(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_habitica: AiohttpClientMocker,
) -> None:
    """Test Habitica update_reward action."""
    task_id = "5e2ea1df-f6e6-4ba3-bccb-97c5ec63e99b"
    mock_habitica.put(
        f"{DEFAULT_URL}/api/v3/tasks/{task_id}",
        json={"success": True, "data": {}},
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_UPDATE_REWARD,
        service_data={
            ATTR_CONFIG_ENTRY: config_entry.entry_id,
            ATTR_TASK: task_id,
            ATTR_COST: 100,
        },
        return_response=True,
        blocking=True,
    )

    mock_call = mock_called_with(
        mock_habitica,
        "PUT",
        f"{DEFAULT_URL}/api/v3/tasks/{task_id}",
    )
    assert mock_call
    assert mock_call[2] == '{"value": 100.0}'


async def test_tags(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_habitica: AiohttpClientMocker,
) -> None:
    """Test adding tags to a task."""
    task_id = "88de7cd9-af2b-49ce-9afd-bf941d87336b"
    mock_habitica.put(
        f"{DEFAULT_URL}/api/v3/tasks/{task_id}",
        json={"success": True, "data": {}},
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_UPDATE_TODO,
        service_data={
            ATTR_CONFIG_ENTRY: config_entry.entry_id,
            ATTR_TASK: task_id,
            ATTR_TAG: ["Schule"],
        },
        return_response=True,
        blocking=True,
    )

    mock_call = mock_called_with(
        mock_habitica,
        "PUT",
        f"{DEFAULT_URL}/api/v3/tasks/{task_id}",
    )
    assert mock_call
    assert (tags := json.loads(mock_call[2]).get("tags"))
    assert len(tags) == 3

    assert set(tags) == {
        "2ac458af-0833-4f3f-bf04-98a0c33ef60b",
        "20409521-c096-447f-9a90-23e8da615710",
        "8515e4ae-2f4b-455a-b4a4-8939e04b1bfd",
    }


async def test_create_new_tag(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_habitica: AiohttpClientMocker,
) -> None:
    """Test adding a non-existent tag and create it as new."""
    task_id = "88de7cd9-af2b-49ce-9afd-bf941d87336b"
    mock_habitica.put(
        f"{DEFAULT_URL}/api/v3/tasks/{task_id}",
        json={"success": True, "data": {}},
    )
    mock_habitica.post(
        f"{DEFAULT_URL}/api/v3/tags",
        status=201,
        json={
            "success": True,
            "data": {
                "name": "Home Assistant",
                "id": "8bc0afbf-ab8e-49a4-982d-67a40557ed1a",
            },
        },
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_UPDATE_TODO,
        service_data={
            ATTR_CONFIG_ENTRY: config_entry.entry_id,
            ATTR_TASK: task_id,
            ATTR_TAG: ["Home Assistant"],
        },
        return_response=True,
        blocking=True,
    )

    mock_call = mock_called_with(
        mock_habitica,
        "POST",
        f"{DEFAULT_URL}/api/v3/tags",
    )
    assert mock_call
    assert mock_call[2] == '{"name": "Home Assistant"}'

    mock_call = mock_called_with(
        mock_habitica,
        "PUT",
        f"{DEFAULT_URL}/api/v3/tasks/{task_id}",
    )
    assert mock_call
    assert (tags := json.loads(mock_call[2]).get("tags"))
    assert len(tags) == 3

    assert set(tags) == {
        "8bc0afbf-ab8e-49a4-982d-67a40557ed1a",
        "20409521-c096-447f-9a90-23e8da615710",
        "8515e4ae-2f4b-455a-b4a4-8939e04b1bfd",
    }


@pytest.mark.parametrize(
    ("status", "exception"),
    [
        (HTTPStatus.TOO_MANY_REQUESTS, ServiceValidationError),
        (HTTPStatus.BAD_GATEWAY, HomeAssistantError),
    ],
)
async def test_create_new_tag_exception(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_habitica: AiohttpClientMocker,
    status: HTTPStatus,
    exception: Exception,
) -> None:
    """Test create new tag exception."""
    task_id = "88de7cd9-af2b-49ce-9afd-bf941d87336b"
    mock_habitica.post(f"{DEFAULT_URL}/api/v3/tags", status=status)
    with pytest.raises(exception):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_UPDATE_TODO,
            service_data={
                ATTR_CONFIG_ENTRY: config_entry.entry_id,
                ATTR_TASK: task_id,
                ATTR_TAG: ["Home Assistant"],
            },
            return_response=True,
            blocking=True,
        )


async def test_remove_tags(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_habitica: AiohttpClientMocker,
) -> None:
    """Test removing tags from a task."""
    task_id = "88de7cd9-af2b-49ce-9afd-bf941d87336b"
    mock_habitica.put(
        f"{DEFAULT_URL}/api/v3/tasks/{task_id}",
        json={"success": True, "data": {}},
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_UPDATE_TODO,
        service_data={
            ATTR_CONFIG_ENTRY: config_entry.entry_id,
            ATTR_TASK: task_id,
            ATTR_REMOVE_TAG: ["arbeit"],
        },
        return_response=True,
        blocking=True,
    )

    mock_call = mock_called_with(
        mock_habitica,
        "PUT",
        f"{DEFAULT_URL}/api/v3/tasks/{task_id}",
    )
    assert mock_call
    assert (tags := json.loads(mock_call[2]).get("tags"))
    assert len(tags) == 1

    assert set(tags) == {"20409521-c096-447f-9a90-23e8da615710"}


async def test_add_checklist(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_habitica: AiohttpClientMocker,
) -> None:
    """Test adding a checklist item."""

    task_id = "564b9ac9-c53d-4638-9e7f-1cd96fe19baa"
    mock_habitica.put(
        f"{DEFAULT_URL}/api/v3/tasks/{task_id}",
        json={"success": True, "data": {}},
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_UPDATE_DAILY,
        service_data={
            ATTR_CONFIG_ENTRY: config_entry.entry_id,
            ATTR_TASK: task_id,
            ATTR_ADD_CHECKLIST_ITEM: ["Checklist-item2"],
        },
        return_response=True,
        blocking=True,
    )

    mock_call = mock_called_with(
        mock_habitica,
        "PUT",
        f"{DEFAULT_URL}/api/v3/tasks/{task_id}",
    )
    assert mock_call
    assert (checklist := json.loads(mock_call[2]).get("checklist"))
    assert len(checklist) == 2
    assert {
        "completed": False,
        "id": "5d1935ff-80c8-443c-b2e9-733c66b44745",
        "text": "Checklist-item2",
    } in checklist


async def test_remove_checklist(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_habitica: AiohttpClientMocker,
) -> None:
    """Test adding a checklist item."""

    task_id = "564b9ac9-c53d-4638-9e7f-1cd96fe19baa"
    mock_habitica.put(
        f"{DEFAULT_URL}/api/v3/tasks/{task_id}",
        json={"success": True, "data": {}},
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_UPDATE_DAILY,
        service_data={
            ATTR_CONFIG_ENTRY: config_entry.entry_id,
            ATTR_TASK: task_id,
            ATTR_REMOVE_CHECKLIST_ITEM: ["Checklist-item1"],
        },
        return_response=True,
        blocking=True,
    )

    mock_call = mock_called_with(
        mock_habitica,
        "PUT",
        f"{DEFAULT_URL}/api/v3/tasks/{task_id}",
    )
    assert mock_call
    checklist = json.loads(mock_call[2]).get("checklist")
    assert len(checklist) == 0


@pytest.mark.parametrize(
    ("service", "task_id", "expected"),
    [
        (ATTR_SCORE_CHECKLIST_ITEM, "564b9ac9-c53d-4638-9e7f-1cd96fe19baa", True),
        (ATTR_UNSCORE_CHECKLIST_ITEM, "2c6d136c-a1c3-4bef-b7c4-fa980784b1e1", False),
    ],
    ids=["score_checklist", "unscore_checklist"],
)
async def test_complete_checklist(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_habitica: AiohttpClientMocker,
    service: str,
    task_id: str,
    expected: bool,
) -> None:
    """Test completing a checklist item."""

    mock_habitica.put(
        f"{DEFAULT_URL}/api/v3/tasks/{task_id}",
        json={"success": True, "data": {}},
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_UPDATE_DAILY,
        service_data={
            ATTR_CONFIG_ENTRY: config_entry.entry_id,
            ATTR_TASK: task_id,
            service: ["Checklist-item1"],
        },
        return_response=True,
        blocking=True,
    )

    mock_call = mock_called_with(
        mock_habitica,
        "PUT",
        f"{DEFAULT_URL}/api/v3/tasks/{task_id}",
    )
    assert mock_call
    checklist = json.loads(mock_call[2]).get("checklist")
    assert len(checklist) == 1
    assert checklist[0]["completed"] is expected
