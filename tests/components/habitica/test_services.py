"""Test Habitica actions."""

from collections.abc import Generator
from http import HTTPStatus
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.habitica.const import (
    ATTR_CONFIG_ENTRY,
    ATTR_DIRECTION,
    ATTR_ITEM,
    ATTR_SKILL,
    ATTR_TARGET,
    ATTR_TASK,
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
)
from homeassistant.config_entries import ConfigEntryState
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
