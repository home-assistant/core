"""Test Habitica actions."""

from collections.abc import Generator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import UUID

from aiohttp import ClientError
from freezegun.api import freeze_time
from habiticalib import (
    Checklist,
    Direction,
    Frequency,
    HabiticaTaskResponse,
    Reminders,
    Repeat,
    Skill,
    Task,
    TaskPriority,
    TaskType,
)
import pytest
from syrupy.assertion import SnapshotAssertion

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
    ATTR_FREQUENCY,
    ATTR_INTERVAL,
    ATTR_ITEM,
    ATTR_KEYWORD,
    ATTR_NOTES,
    ATTR_PRIORITY,
    ATTR_REMINDER,
    ATTR_REMOVE_CHECKLIST_ITEM,
    ATTR_REMOVE_REMINDER,
    ATTR_REMOVE_TAG,
    ATTR_REPEAT,
    ATTR_REPEAT_MONTHLY,
    ATTR_SCORE_CHECKLIST_ITEM,
    ATTR_SKILL,
    ATTR_START_DATE,
    ATTR_STREAK,
    ATTR_TAG,
    ATTR_TARGET,
    ATTR_TASK,
    ATTR_TYPE,
    ATTR_UNSCORE_CHECKLIST_ITEM,
    ATTR_UP_DOWN,
    DOMAIN,
    SERVICE_ABORT_QUEST,
    SERVICE_ACCEPT_QUEST,
    SERVICE_CANCEL_QUEST,
    SERVICE_CAST_SKILL,
    SERVICE_CREATE_DAILY,
    SERVICE_CREATE_HABIT,
    SERVICE_CREATE_REWARD,
    SERVICE_CREATE_TODO,
    SERVICE_GET_TASKS,
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
from homeassistant.components.todo import ATTR_RENAME
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_DATE, ATTR_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .conftest import (
    ERROR_BAD_REQUEST,
    ERROR_NOT_AUTHORIZED,
    ERROR_NOT_FOUND,
    ERROR_TOO_MANY_REQUESTS,
)

from tests.common import MockConfigEntry, load_fixture

REQUEST_EXCEPTION_MSG = "Unable to connect to Habitica: reason"
RATE_LIMIT_EXCEPTION_MSG = "Rate limit exceeded, try again in 5 seconds"


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
    habitica: AsyncMock,
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
    (
        "service_data",
        "call_args",
    ),
    [
        (
            {
                ATTR_TASK: "2f6fcabc-f670-4ec3-ba65-817e8deea490",
                ATTR_SKILL: "pickpocket",
            },
            {
                "skill": Skill.PICKPOCKET,
                "target_id": UUID("2f6fcabc-f670-4ec3-ba65-817e8deea490"),
            },
        ),
        (
            {
                ATTR_TASK: "2f6fcabc-f670-4ec3-ba65-817e8deea490",
                ATTR_SKILL: "backstab",
            },
            {
                "skill": Skill.BACKSTAB,
                "target_id": UUID("2f6fcabc-f670-4ec3-ba65-817e8deea490"),
            },
        ),
        (
            {
                ATTR_TASK: "2f6fcabc-f670-4ec3-ba65-817e8deea490",
                ATTR_SKILL: "fireball",
            },
            {
                "skill": Skill.BURST_OF_FLAMES,
                "target_id": UUID("2f6fcabc-f670-4ec3-ba65-817e8deea490"),
            },
        ),
        (
            {
                ATTR_TASK: "2f6fcabc-f670-4ec3-ba65-817e8deea490",
                ATTR_SKILL: "smash",
            },
            {
                "skill": Skill.BRUTAL_SMASH,
                "target_id": UUID("2f6fcabc-f670-4ec3-ba65-817e8deea490"),
            },
        ),
        (
            {
                ATTR_TASK: "Rechnungen bezahlen",
                ATTR_SKILL: "smash",
            },
            {
                "skill": Skill.BRUTAL_SMASH,
                "target_id": UUID("2f6fcabc-f670-4ec3-ba65-817e8deea490"),
            },
        ),
        (
            {
                ATTR_TASK: "pay_bills",
                ATTR_SKILL: "smash",
            },
            {
                "skill": Skill.BRUTAL_SMASH,
                "target_id": UUID("2f6fcabc-f670-4ec3-ba65-817e8deea490"),
            },
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
    habitica: AsyncMock,
    service_data: dict[str, Any],
    call_args: dict[str, Any],
) -> None:
    """Test Habitica cast skill action."""

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
    habitica.cast_skill.assert_awaited_once_with(**call_args)


@pytest.mark.parametrize(
    (
        "service_data",
        "raise_exception",
        "expected_exception",
        "expected_exception_msg",
    ),
    [
        (
            {
                ATTR_TASK: "task-not-found",
                ATTR_SKILL: "smash",
            },
            None,
            ServiceValidationError,
            "Unable to complete action, could not find the task 'task-not-found'",
        ),
        (
            {
                ATTR_TASK: "Rechnungen bezahlen",
                ATTR_SKILL: "smash",
            },
            ERROR_TOO_MANY_REQUESTS,
            HomeAssistantError,
            RATE_LIMIT_EXCEPTION_MSG,
        ),
        (
            {
                ATTR_TASK: "Rechnungen bezahlen",
                ATTR_SKILL: "smash",
            },
            ERROR_NOT_FOUND,
            ServiceValidationError,
            "Unable to cast skill, your character does not have the skill or spell smash",
        ),
        (
            {
                ATTR_TASK: "Rechnungen bezahlen",
                ATTR_SKILL: "smash",
            },
            ERROR_NOT_AUTHORIZED,
            ServiceValidationError,
            "Unable to cast skill, not enough mana. Your character has 50 MP, but the skill costs 10 MP",
        ),
        (
            {
                ATTR_TASK: "Rechnungen bezahlen",
                ATTR_SKILL: "smash",
            },
            ERROR_BAD_REQUEST,
            HomeAssistantError,
            REQUEST_EXCEPTION_MSG,
        ),
        (
            {
                ATTR_TASK: "Rechnungen bezahlen",
                ATTR_SKILL: "smash",
            },
            ClientError,
            HomeAssistantError,
            "Unable to connect to Habitica: ",
        ),
    ],
)
async def test_cast_skill_exceptions(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    habitica: AsyncMock,
    service_data: dict[str, Any],
    raise_exception: Exception,
    expected_exception: Exception,
    expected_exception_msg: str,
) -> None:
    """Test Habitica cast skill action exceptions."""

    habitica.cast_skill.side_effect = raise_exception
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


async def test_get_config_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
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
    "service",
    [
        SERVICE_ABORT_QUEST,
        SERVICE_ACCEPT_QUEST,
        SERVICE_CANCEL_QUEST,
        SERVICE_LEAVE_QUEST,
        SERVICE_REJECT_QUEST,
        SERVICE_START_QUEST,
    ],
)
async def test_handle_quests(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    habitica: AsyncMock,
    service: str,
) -> None:
    """Test Habitica actions for quest handling."""

    await hass.services.async_call(
        DOMAIN,
        service,
        service_data={ATTR_CONFIG_ENTRY: config_entry.entry_id},
        return_response=True,
        blocking=True,
    )

    getattr(habitica, service).assert_awaited_once()


@pytest.mark.parametrize(
    (
        "raise_exception",
        "expected_exception",
        "expected_exception_msg",
    ),
    [
        (
            ERROR_TOO_MANY_REQUESTS,
            HomeAssistantError,
            RATE_LIMIT_EXCEPTION_MSG,
        ),
        (
            ERROR_NOT_FOUND,
            ServiceValidationError,
            "Unable to complete action, quest or group not found",
        ),
        (
            ERROR_NOT_AUTHORIZED,
            ServiceValidationError,
            "Action not allowed, only quest leader or group leader can perform this action",
        ),
        (
            ERROR_BAD_REQUEST,
            HomeAssistantError,
            REQUEST_EXCEPTION_MSG,
        ),
        (
            ClientError,
            HomeAssistantError,
            "Unable to connect to Habitica: ",
        ),
    ],
)
@pytest.mark.parametrize(
    "service",
    [
        SERVICE_ACCEPT_QUEST,
        SERVICE_ABORT_QUEST,
        SERVICE_CANCEL_QUEST,
        SERVICE_LEAVE_QUEST,
        SERVICE_REJECT_QUEST,
        SERVICE_START_QUEST,
    ],
)
async def test_handle_quests_exceptions(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    habitica: AsyncMock,
    raise_exception: Exception,
    service: str,
    expected_exception: Exception,
    expected_exception_msg: str,
) -> None:
    """Test Habitica handle quests action exceptions."""

    getattr(habitica, service).side_effect = raise_exception
    with pytest.raises(expected_exception, match=expected_exception_msg):
        await hass.services.async_call(
            DOMAIN,
            service,
            service_data={ATTR_CONFIG_ENTRY: config_entry.entry_id},
            return_response=True,
            blocking=True,
        )


@pytest.mark.parametrize(
    ("service", "service_data", "call_args"),
    [
        (
            SERVICE_SCORE_HABIT,
            {
                ATTR_TASK: "e97659e0-2c42-4599-a7bb-00282adc410d",
                ATTR_DIRECTION: "up",
            },
            {
                "task_id": UUID("e97659e0-2c42-4599-a7bb-00282adc410d"),
                "direction": Direction.UP,
            },
        ),
        (
            SERVICE_SCORE_HABIT,
            {
                ATTR_TASK: "e97659e0-2c42-4599-a7bb-00282adc410d",
                ATTR_DIRECTION: "down",
            },
            {
                "task_id": UUID("e97659e0-2c42-4599-a7bb-00282adc410d"),
                "direction": Direction.DOWN,
            },
        ),
        (
            SERVICE_SCORE_REWARD,
            {
                ATTR_TASK: "5e2ea1df-f6e6-4ba3-bccb-97c5ec63e99b",
            },
            {
                "task_id": UUID("5e2ea1df-f6e6-4ba3-bccb-97c5ec63e99b"),
                "direction": Direction.UP,
            },
        ),
        (
            SERVICE_SCORE_HABIT,
            {
                ATTR_TASK: "Füge eine Aufgabe zu Habitica hinzu",
                ATTR_DIRECTION: "up",
            },
            {
                "task_id": UUID("e97659e0-2c42-4599-a7bb-00282adc410d"),
                "direction": Direction.UP,
            },
        ),
        (
            SERVICE_SCORE_HABIT,
            {
                ATTR_TASK: "create_a_task",
                ATTR_DIRECTION: "up",
            },
            {
                "task_id": UUID("e97659e0-2c42-4599-a7bb-00282adc410d"),
                "direction": Direction.UP,
            },
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
    habitica: AsyncMock,
    service: str,
    service_data: dict[str, Any],
    call_args: dict[str, Any],
) -> None:
    """Test Habitica score task action."""

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

    habitica.update_score.assert_awaited_once_with(**call_args)


@pytest.mark.parametrize(
    (
        "service_data",
        "raise_exception",
        "expected_exception",
        "expected_exception_msg",
    ),
    [
        (
            {
                ATTR_TASK: "task does not exist",
                ATTR_DIRECTION: "up",
            },
            None,
            ServiceValidationError,
            "Unable to complete action, could not find the task 'task does not exist'",
        ),
        (
            {
                ATTR_TASK: "e97659e0-2c42-4599-a7bb-00282adc410d",
                ATTR_DIRECTION: "up",
            },
            ERROR_TOO_MANY_REQUESTS,
            HomeAssistantError,
            RATE_LIMIT_EXCEPTION_MSG,
        ),
        (
            {
                ATTR_TASK: "e97659e0-2c42-4599-a7bb-00282adc410d",
                ATTR_DIRECTION: "up",
            },
            ERROR_BAD_REQUEST,
            HomeAssistantError,
            REQUEST_EXCEPTION_MSG,
        ),
        (
            {
                ATTR_TASK: "e97659e0-2c42-4599-a7bb-00282adc410d",
                ATTR_DIRECTION: "up",
            },
            ClientError,
            HomeAssistantError,
            "Unable to connect to Habitica: ",
        ),
        (
            {
                ATTR_TASK: "5e2ea1df-f6e6-4ba3-bccb-97c5ec63e99b",
                ATTR_DIRECTION: "up",
            },
            ERROR_NOT_AUTHORIZED,
            HomeAssistantError,
            "Unable to buy reward, not enough gold. Your character has 137.63 GP, but the reward costs 10.00 GP",
        ),
    ],
)
async def test_score_task_exceptions(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    habitica: AsyncMock,
    service_data: dict[str, Any],
    raise_exception: Exception,
    expected_exception: Exception,
    expected_exception_msg: str,
) -> None:
    """Test Habitica score task action exceptions."""

    habitica.update_score.side_effect = raise_exception
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
    ("service_data", "call_args"),
    [
        (
            {
                ATTR_TARGET: "a380546a-94be-4b8e-8a0b-23e0d5c03303",
                ATTR_ITEM: "spooky_sparkles",
            },
            {
                "skill": Skill.SPOOKY_SPARKLES,
                "target_id": UUID("a380546a-94be-4b8e-8a0b-23e0d5c03303"),
            },
        ),
        (
            {
                ATTR_TARGET: "a380546a-94be-4b8e-8a0b-23e0d5c03303",
                ATTR_ITEM: "shiny_seed",
            },
            {
                "skill": Skill.SHINY_SEED,
                "target_id": UUID("a380546a-94be-4b8e-8a0b-23e0d5c03303"),
            },
        ),
        (
            {
                ATTR_TARGET: "a380546a-94be-4b8e-8a0b-23e0d5c03303",
                ATTR_ITEM: "seafoam",
            },
            {
                "skill": Skill.SEAFOAM,
                "target_id": UUID("a380546a-94be-4b8e-8a0b-23e0d5c03303"),
            },
        ),
        (
            {
                ATTR_TARGET: "a380546a-94be-4b8e-8a0b-23e0d5c03303",
                ATTR_ITEM: "snowball",
            },
            {
                "skill": Skill.SNOWBALL,
                "target_id": UUID("a380546a-94be-4b8e-8a0b-23e0d5c03303"),
            },
        ),
        (
            {
                ATTR_TARGET: "test-user",
                ATTR_ITEM: "spooky_sparkles",
            },
            {
                "skill": Skill.SPOOKY_SPARKLES,
                "target_id": UUID("a380546a-94be-4b8e-8a0b-23e0d5c03303"),
            },
        ),
        (
            {
                ATTR_TARGET: "test-username",
                ATTR_ITEM: "spooky_sparkles",
            },
            {
                "skill": Skill.SPOOKY_SPARKLES,
                "target_id": UUID("a380546a-94be-4b8e-8a0b-23e0d5c03303"),
            },
        ),
        (
            {
                ATTR_TARGET: "ffce870c-3ff3-4fa4-bad1-87612e52b8e7",
                ATTR_ITEM: "spooky_sparkles",
            },
            {
                "skill": Skill.SPOOKY_SPARKLES,
                "target_id": UUID("ffce870c-3ff3-4fa4-bad1-87612e52b8e7"),
            },
        ),
        (
            {
                ATTR_TARGET: "test-partymember-username",
                ATTR_ITEM: "spooky_sparkles",
            },
            {
                "skill": Skill.SPOOKY_SPARKLES,
                "target_id": UUID("ffce870c-3ff3-4fa4-bad1-87612e52b8e7"),
            },
        ),
        (
            {
                ATTR_TARGET: "test-partymember-displayname",
                ATTR_ITEM: "spooky_sparkles",
            },
            {
                "skill": Skill.SPOOKY_SPARKLES,
                "target_id": UUID("ffce870c-3ff3-4fa4-bad1-87612e52b8e7"),
            },
        ),
    ],
    ids=[
        "use spooky sparkles/select self by id",
        "use shiny seed",
        "use seafoam",
        "use snowball",
        "select self by displayname",
        "select self by username",
        "select partymember by id",
        "select partymember by username",
        "select partymember by displayname",
    ],
)
async def test_transformation(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    habitica: AsyncMock,
    service_data: dict[str, Any],
    call_args: dict[str, Any],
) -> None:
    """Test Habitica use transformation item action."""

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

    habitica.cast_skill.assert_awaited_once_with(**call_args)


@pytest.mark.parametrize(
    (
        "service_data",
        "raise_exception_members",
        "raise_exception_cast",
        "expected_exception",
        "expected_exception_msg",
    ),
    [
        (
            {
                ATTR_TARGET: "user-not-found",
                ATTR_ITEM: "spooky_sparkles",
            },
            None,
            None,
            ServiceValidationError,
            "Unable to find target 'user-not-found' in your party",
        ),
        (
            {
                ATTR_TARGET: "test-partymember-username",
                ATTR_ITEM: "spooky_sparkles",
            },
            ERROR_NOT_FOUND,
            None,
            ServiceValidationError,
            "Unable to find target, you are currently not in a party. You can only target yourself",
        ),
        (
            {
                ATTR_TARGET: "test-partymember-username",
                ATTR_ITEM: "spooky_sparkles",
            },
            ERROR_BAD_REQUEST,
            None,
            HomeAssistantError,
            REQUEST_EXCEPTION_MSG,
        ),
        (
            {
                ATTR_TARGET: "test-partymember-username",
                ATTR_ITEM: "spooky_sparkles",
            },
            None,
            ERROR_TOO_MANY_REQUESTS,
            HomeAssistantError,
            RATE_LIMIT_EXCEPTION_MSG,
        ),
        (
            {
                ATTR_TARGET: "test-partymember-username",
                ATTR_ITEM: "spooky_sparkles",
            },
            None,
            ERROR_NOT_AUTHORIZED,
            ServiceValidationError,
            "Unable to use spooky_sparkles, you don't own this item",
        ),
        (
            {
                ATTR_TARGET: "test-partymember-username",
                ATTR_ITEM: "spooky_sparkles",
            },
            None,
            ERROR_BAD_REQUEST,
            HomeAssistantError,
            REQUEST_EXCEPTION_MSG,
        ),
        (
            {
                ATTR_TARGET: "test-partymember-username",
                ATTR_ITEM: "spooky_sparkles",
            },
            None,
            ClientError,
            HomeAssistantError,
            "Unable to connect to Habitica: ",
        ),
        (
            {
                ATTR_TARGET: "test-partymember-username",
                ATTR_ITEM: "spooky_sparkles",
            },
            ClientError,
            None,
            HomeAssistantError,
            "Unable to connect to Habitica: ",
        ),
    ],
)
async def test_transformation_exceptions(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    habitica: AsyncMock,
    service_data: dict[str, Any],
    raise_exception_members: Exception,
    raise_exception_cast: Exception,
    expected_exception: Exception,
    expected_exception_msg: str,
) -> None:
    """Test Habitica transformation action exceptions."""

    habitica.cast_skill.side_effect = raise_exception_cast
    habitica.get_group_members.side_effect = raise_exception_members
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
    ("service_data"),
    [
        {},
        {ATTR_TYPE: ["daily"]},
        {ATTR_TYPE: ["habit"]},
        {ATTR_TYPE: ["todo"]},
        {ATTR_TYPE: ["reward"]},
        {ATTR_TYPE: ["daily", "habit"]},
        {ATTR_TYPE: ["todo", "reward"]},
        {ATTR_PRIORITY: "trivial"},
        {ATTR_PRIORITY: "easy"},
        {ATTR_PRIORITY: "medium"},
        {ATTR_PRIORITY: "hard"},
        {ATTR_TASK: ["Zahnseide benutzen", "Eine kurze Pause machen"]},
        {ATTR_TASK: ["f2c85972-1a19-4426-bc6d-ce3337b9d99f"]},
        {ATTR_TASK: ["alias_zahnseide_benutzen"]},
        {ATTR_TAG: ["Training", "Gesundheit + Wohlbefinden"]},
        {ATTR_KEYWORD: "gewohnheit"},
        {ATTR_TAG: ["Home Assistant"]},
    ],
    ids=[
        "all_tasks",
        "only dailies",
        "only habits",
        "only todos",
        "only rewards",
        "only dailies and habits",
        "only todos and rewards",
        "trivial tasks",
        "easy tasks",
        "medium tasks",
        "hard tasks",
        "by task name",
        "by task ID",
        "by alias",
        "by tag",
        "by keyword",
        "empty result",
    ],
)
@pytest.mark.usefixtures("habitica")
async def test_get_tasks(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    service_data: dict[str, Any],
) -> None:
    """Test Habitica get_tasks action."""

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_TASKS,
        service_data={
            ATTR_CONFIG_ENTRY: config_entry.entry_id,
            **service_data,
        },
        return_response=True,
        blocking=True,
    )

    assert response == snapshot


@pytest.mark.parametrize(
    ("exception", "expected_exception", "exception_msg"),
    [
        (
            ERROR_TOO_MANY_REQUESTS,
            HomeAssistantError,
            RATE_LIMIT_EXCEPTION_MSG,
        ),
        (
            ERROR_BAD_REQUEST,
            HomeAssistantError,
            REQUEST_EXCEPTION_MSG,
        ),
        (
            ClientError,
            HomeAssistantError,
            "Unable to connect to Habitica: ",
        ),
    ],
)
@pytest.mark.parametrize(
    ("service", "task_id"),
    [
        (SERVICE_UPDATE_REWARD, "5e2ea1df-f6e6-4ba3-bccb-97c5ec63e99b"),
        (SERVICE_UPDATE_HABIT, "f21fa608-cfc6-4413-9fc7-0eb1b48ca43a"),
        (SERVICE_UPDATE_TODO, "88de7cd9-af2b-49ce-9afd-bf941d87336b"),
        (SERVICE_UPDATE_DAILY, "6e53f1f5-a315-4edd-984d-8d762e4a08ef"),
    ],
)
@pytest.mark.usefixtures("habitica")
async def test_update_task_exceptions(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    habitica: AsyncMock,
    exception: Exception,
    expected_exception: Exception,
    exception_msg: str,
    service: str,
    task_id: str,
) -> None:
    """Test Habitica task action exceptions."""

    habitica.update_task.side_effect = exception
    with pytest.raises(expected_exception, match=exception_msg):
        await hass.services.async_call(
            DOMAIN,
            service,
            service_data={
                ATTR_CONFIG_ENTRY: config_entry.entry_id,
                ATTR_TASK: task_id,
            },
            return_response=True,
            blocking=True,
        )


@pytest.mark.parametrize(
    ("exception", "expected_exception", "exception_msg"),
    [
        (
            ERROR_TOO_MANY_REQUESTS,
            HomeAssistantError,
            RATE_LIMIT_EXCEPTION_MSG,
        ),
        (
            ERROR_BAD_REQUEST,
            HomeAssistantError,
            REQUEST_EXCEPTION_MSG,
        ),
        (
            ClientError,
            HomeAssistantError,
            "Unable to connect to Habitica: ",
        ),
    ],
)
@pytest.mark.parametrize(
    "service",
    [
        SERVICE_CREATE_DAILY,
        SERVICE_CREATE_HABIT,
        SERVICE_CREATE_REWARD,
        SERVICE_CREATE_TODO,
    ],
)
@pytest.mark.usefixtures("habitica")
async def test_create_task_exceptions(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    habitica: AsyncMock,
    exception: Exception,
    expected_exception: Exception,
    exception_msg: str,
    service: str,
) -> None:
    """Test Habitica task create action exceptions."""

    habitica.create_task.side_effect = exception
    with pytest.raises(expected_exception, match=exception_msg):
        await hass.services.async_call(
            DOMAIN,
            service,
            service_data={
                ATTR_CONFIG_ENTRY: config_entry.entry_id,
                ATTR_NAME: "TITLE",
            },
            return_response=True,
            blocking=True,
        )


@pytest.mark.usefixtures("habitica")
async def test_task_not_found(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    habitica: AsyncMock,
) -> None:
    """Test Habitica task not found exceptions."""
    task_id = "7f902bbc-eb3d-4a8f-82cf-4e2025d69af1"

    with pytest.raises(
        ServiceValidationError,
        match="Unable to complete action, could not find the task '7f902bbc-eb3d-4a8f-82cf-4e2025d69af1'",
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_UPDATE_REWARD,
            service_data={
                ATTR_CONFIG_ENTRY: config_entry.entry_id,
                ATTR_TASK: task_id,
            },
            return_response=True,
            blocking=True,
        )


@pytest.mark.parametrize(
    ("service_data", "call_args"),
    [
        (
            {
                ATTR_COST: 100,
            },
            Task(value=100),
        ),
        (
            {
                ATTR_RENAME: "RENAME",
            },
            Task(text="RENAME"),
        ),
        (
            {
                ATTR_NOTES: "NOTES",
            },
            Task(notes="NOTES"),
        ),
        (
            {
                ATTR_ALIAS: "ALIAS",
            },
            Task(alias="ALIAS"),
        ),
    ],
)
async def test_update_reward(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    habitica: AsyncMock,
    service_data: dict[str, Any],
    call_args: Task,
) -> None:
    """Test Habitica update_reward action."""
    task_id = "5e2ea1df-f6e6-4ba3-bccb-97c5ec63e99b"

    habitica.update_task.return_value = HabiticaTaskResponse.from_json(
        load_fixture("task.json", DOMAIN)
    )
    await hass.services.async_call(
        DOMAIN,
        SERVICE_UPDATE_REWARD,
        service_data={
            ATTR_CONFIG_ENTRY: config_entry.entry_id,
            ATTR_TASK: task_id,
            **service_data,
        },
        return_response=True,
        blocking=True,
    )
    habitica.update_task.assert_awaited_with(UUID(task_id), call_args)


@pytest.mark.parametrize(
    ("service_data", "call_args"),
    [
        (
            {
                ATTR_NAME: "TITLE",
                ATTR_COST: 100,
            },
            Task(type=TaskType.REWARD, text="TITLE", value=100),
        ),
        (
            {
                ATTR_NAME: "TITLE",
            },
            Task(type=TaskType.REWARD, text="TITLE"),
        ),
        (
            {
                ATTR_NAME: "TITLE",
                ATTR_NOTES: "NOTES",
            },
            Task(type=TaskType.REWARD, text="TITLE", notes="NOTES"),
        ),
        (
            {
                ATTR_NAME: "TITLE",
                ATTR_ALIAS: "ALIAS",
            },
            Task(type=TaskType.REWARD, text="TITLE", alias="ALIAS"),
        ),
    ],
)
async def test_create_reward(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    habitica: AsyncMock,
    service_data: dict[str, Any],
    call_args: Task,
) -> None:
    """Test Habitica create_reward action."""

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CREATE_REWARD,
        service_data={
            ATTR_CONFIG_ENTRY: config_entry.entry_id,
            **service_data,
        },
        return_response=True,
        blocking=True,
    )
    habitica.create_task.assert_awaited_with(call_args)


@pytest.mark.parametrize(
    ("service_data", "call_args"),
    [
        (
            {
                ATTR_RENAME: "RENAME",
            },
            Task(text="RENAME"),
        ),
        (
            {
                ATTR_NOTES: "NOTES",
            },
            Task(notes="NOTES"),
        ),
        (
            {
                ATTR_UP_DOWN: [""],
            },
            Task(up=False, down=False),
        ),
        (
            {
                ATTR_UP_DOWN: ["up"],
            },
            Task(up=True, down=False),
        ),
        (
            {
                ATTR_UP_DOWN: ["down"],
            },
            Task(up=False, down=True),
        ),
        (
            {
                ATTR_PRIORITY: "trivial",
            },
            Task(priority=TaskPriority.TRIVIAL),
        ),
        (
            {
                ATTR_FREQUENCY: "daily",
            },
            Task(frequency=Frequency.DAILY),
        ),
        (
            {
                ATTR_COUNTER_UP: 1,
                ATTR_COUNTER_DOWN: 2,
            },
            Task(counterUp=1, counterDown=2),
        ),
        (
            {
                ATTR_ALIAS: "ALIAS",
            },
            Task(alias="ALIAS"),
        ),
    ],
)
async def test_update_habit(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    habitica: AsyncMock,
    service_data: dict[str, Any],
    call_args: Task,
) -> None:
    """Test Habitica habit action."""
    task_id = "f21fa608-cfc6-4413-9fc7-0eb1b48ca43a"

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
    habitica.update_task.assert_awaited_with(UUID(task_id), call_args)


@pytest.mark.parametrize(
    ("service_data", "call_args"),
    [
        (
            {
                ATTR_NAME: "TITLE",
            },
            Task(type=TaskType.HABIT, text="TITLE"),
        ),
        (
            {
                ATTR_NAME: "TITLE",
                ATTR_NOTES: "NOTES",
            },
            Task(type=TaskType.HABIT, text="TITLE", notes="NOTES"),
        ),
        (
            {
                ATTR_NAME: "TITLE",
                ATTR_UP_DOWN: [""],
            },
            Task(type=TaskType.HABIT, text="TITLE", up=False, down=False),
        ),
        (
            {
                ATTR_NAME: "TITLE",
                ATTR_UP_DOWN: ["up"],
            },
            Task(type=TaskType.HABIT, text="TITLE", up=True, down=False),
        ),
        (
            {
                ATTR_NAME: "TITLE",
                ATTR_UP_DOWN: ["down"],
            },
            Task(type=TaskType.HABIT, text="TITLE", up=False, down=True),
        ),
        (
            {
                ATTR_NAME: "TITLE",
                ATTR_PRIORITY: "trivial",
            },
            Task(type=TaskType.HABIT, text="TITLE", priority=TaskPriority.TRIVIAL),
        ),
        (
            {
                ATTR_NAME: "TITLE",
                ATTR_FREQUENCY: "daily",
            },
            Task(type=TaskType.HABIT, text="TITLE", frequency=Frequency.DAILY),
        ),
        (
            {
                ATTR_NAME: "TITLE",
                ATTR_ALIAS: "ALIAS",
            },
            Task(type=TaskType.HABIT, text="TITLE", alias="ALIAS"),
        ),
    ],
)
async def test_create_habit(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    habitica: AsyncMock,
    service_data: dict[str, Any],
    call_args: Task,
) -> None:
    """Test Habitica create_habit action."""

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CREATE_HABIT,
        service_data={
            ATTR_CONFIG_ENTRY: config_entry.entry_id,
            **service_data,
        },
        return_response=True,
        blocking=True,
    )
    habitica.create_task.assert_awaited_with(call_args)


@pytest.mark.parametrize(
    ("service_data", "call_args"),
    [
        (
            {
                ATTR_RENAME: "RENAME",
            },
            Task(text="RENAME"),
        ),
        (
            {
                ATTR_NOTES: "NOTES",
            },
            Task(notes="NOTES"),
        ),
        (
            {
                ATTR_ADD_CHECKLIST_ITEM: "Checklist-item",
            },
            Task(
                {
                    "checklist": [
                        Checklist(
                            id=UUID("fccc26f2-1e2b-4bf8-9dd0-a405be261036"),
                            text="Checklist-item1",
                            completed=False,
                        ),
                        Checklist(
                            id=UUID("5a897af4-ea94-456a-a2bd-f336bcd79509"),
                            text="Checklist-item2",
                            completed=True,
                        ),
                        Checklist(
                            id=UUID("12345678-1234-5678-1234-567812345678"),
                            text="Checklist-item",
                            completed=False,
                        ),
                    ]
                }
            ),
        ),
        (
            {
                ATTR_REMOVE_CHECKLIST_ITEM: "Checklist-item1",
            },
            Task(
                {
                    "checklist": [
                        Checklist(
                            id=UUID("5a897af4-ea94-456a-a2bd-f336bcd79509"),
                            text="Checklist-item2",
                            completed=True,
                        ),
                    ]
                }
            ),
        ),
        (
            {
                ATTR_SCORE_CHECKLIST_ITEM: "Checklist-item1",
            },
            Task(
                {
                    "checklist": [
                        Checklist(
                            id=UUID("fccc26f2-1e2b-4bf8-9dd0-a405be261036"),
                            text="Checklist-item1",
                            completed=True,
                        ),
                        Checklist(
                            id=UUID("5a897af4-ea94-456a-a2bd-f336bcd79509"),
                            text="Checklist-item2",
                            completed=True,
                        ),
                    ]
                }
            ),
        ),
        (
            {
                ATTR_UNSCORE_CHECKLIST_ITEM: "Checklist-item2",
            },
            Task(
                {
                    "checklist": [
                        Checklist(
                            id=UUID("fccc26f2-1e2b-4bf8-9dd0-a405be261036"),
                            text="Checklist-item1",
                            completed=False,
                        ),
                        Checklist(
                            id=UUID("5a897af4-ea94-456a-a2bd-f336bcd79509"),
                            text="Checklist-item2",
                            completed=False,
                        ),
                    ]
                }
            ),
        ),
        (
            {
                ATTR_PRIORITY: "trivial",
            },
            Task(priority=TaskPriority.TRIVIAL),
        ),
        (
            {
                ATTR_DATE: "2025-03-05",
            },
            Task(date=datetime(2025, 3, 5)),
        ),
        (
            {
                ATTR_CLEAR_DATE: True,
            },
            Task(date=None),
        ),
        (
            {
                ATTR_REMINDER: ["2025-02-25T00:00"],
            },
            Task(
                {
                    "reminders": [
                        Reminders(
                            id=UUID("12345678-1234-5678-1234-567812345678"),
                            time=datetime(2025, 2, 25, 0, 0),
                            startDate=None,
                        )
                    ]
                }
            ),
        ),
        (
            {
                ATTR_REMOVE_REMINDER: ["2025-02-25T00:00"],
            },
            Task({"reminders": []}),
        ),
        (
            {
                ATTR_CLEAR_REMINDER: True,
            },
            Task({"reminders": []}),
        ),
        (
            {
                ATTR_ALIAS: "ALIAS",
            },
            Task(alias="ALIAS"),
        ),
    ],
)
@pytest.mark.usefixtures("mock_uuid4")
async def test_update_todo(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    habitica: AsyncMock,
    service_data: dict[str, Any],
    call_args: Task,
) -> None:
    """Test Habitica update todo action."""
    task_id = "88de7cd9-af2b-49ce-9afd-bf941d87336b"

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
    habitica.update_task.assert_awaited_with(UUID(task_id), call_args)


@pytest.mark.parametrize(
    ("service_data", "call_args"),
    [
        (
            {
                ATTR_NAME: "TITLE",
            },
            Task(type=TaskType.TODO, text="TITLE"),
        ),
        (
            {
                ATTR_NAME: "TITLE",
                ATTR_NOTES: "NOTES",
            },
            Task(type=TaskType.TODO, text="TITLE", notes="NOTES"),
        ),
        (
            {
                ATTR_NAME: "TITLE",
                ATTR_ADD_CHECKLIST_ITEM: "Checklist-item",
            },
            Task(
                type=TaskType.TODO,
                text="TITLE",
                checklist=[
                    Checklist(
                        id=UUID("12345678-1234-5678-1234-567812345678"),
                        text="Checklist-item",
                        completed=False,
                    ),
                ],
            ),
        ),
        (
            {
                ATTR_NAME: "TITLE",
                ATTR_PRIORITY: "trivial",
            },
            Task(type=TaskType.TODO, text="TITLE", priority=TaskPriority.TRIVIAL),
        ),
        (
            {
                ATTR_NAME: "TITLE",
                ATTR_DATE: "2025-03-05",
            },
            Task(type=TaskType.TODO, text="TITLE", date=datetime(2025, 3, 5)),
        ),
        (
            {
                ATTR_NAME: "TITLE",
                ATTR_REMINDER: ["2025-02-25T00:00"],
            },
            Task(
                type=TaskType.TODO,
                text="TITLE",
                reminders=[
                    Reminders(
                        id=UUID("12345678-1234-5678-1234-567812345678"),
                        time=datetime(2025, 2, 25, 0, 0),
                        startDate=None,
                    )
                ],
            ),
        ),
        (
            {
                ATTR_NAME: "TITLE",
                ATTR_ALIAS: "ALIAS",
            },
            Task(type=TaskType.TODO, text="TITLE", alias="ALIAS"),
        ),
    ],
)
@pytest.mark.usefixtures("mock_uuid4")
async def test_create_todo(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    habitica: AsyncMock,
    service_data: dict[str, Any],
    call_args: Task,
) -> None:
    """Test Habitica create todo action."""

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CREATE_TODO,
        service_data={
            ATTR_CONFIG_ENTRY: config_entry.entry_id,
            **service_data,
        },
        return_response=True,
        blocking=True,
    )
    habitica.create_task.assert_awaited_with(call_args)


@pytest.mark.parametrize(
    ("service_data", "call_args"),
    [
        (
            {
                ATTR_RENAME: "RENAME",
            },
            Task(text="RENAME"),
        ),
        (
            {
                ATTR_NOTES: "NOTES",
            },
            Task(notes="NOTES"),
        ),
        (
            {
                ATTR_ADD_CHECKLIST_ITEM: "Checklist-item",
            },
            Task(
                {
                    "checklist": [
                        Checklist(
                            id=UUID("a2a6702d-58e1-46c2-a3ce-422d525cc0b6"),
                            text="Checklist-item1",
                            completed=False,
                        ),
                        Checklist(
                            id=UUID("9f64e1cd-b0ab-4577-8344-c7a5e1827997"),
                            text="Checklist-item2",
                            completed=True,
                        ),
                        Checklist(
                            id=UUID("12345678-1234-5678-1234-567812345678"),
                            text="Checklist-item",
                            completed=False,
                        ),
                    ]
                }
            ),
        ),
        (
            {
                ATTR_REMOVE_CHECKLIST_ITEM: "Checklist-item1",
            },
            Task(
                {
                    "checklist": [
                        Checklist(
                            id=UUID("9f64e1cd-b0ab-4577-8344-c7a5e1827997"),
                            text="Checklist-item2",
                            completed=True,
                        ),
                    ]
                }
            ),
        ),
        (
            {
                ATTR_SCORE_CHECKLIST_ITEM: "Checklist-item1",
            },
            Task(
                {
                    "checklist": [
                        Checklist(
                            id=UUID("a2a6702d-58e1-46c2-a3ce-422d525cc0b6"),
                            text="Checklist-item1",
                            completed=True,
                        ),
                        Checklist(
                            id=UUID("9f64e1cd-b0ab-4577-8344-c7a5e1827997"),
                            text="Checklist-item2",
                            completed=True,
                        ),
                    ]
                }
            ),
        ),
        (
            {
                ATTR_UNSCORE_CHECKLIST_ITEM: "Checklist-item2",
            },
            Task(
                {
                    "checklist": [
                        Checklist(
                            id=UUID("a2a6702d-58e1-46c2-a3ce-422d525cc0b6"),
                            text="Checklist-item1",
                            completed=False,
                        ),
                        Checklist(
                            id=UUID("9f64e1cd-b0ab-4577-8344-c7a5e1827997"),
                            text="Checklist-item2",
                            completed=False,
                        ),
                    ]
                }
            ),
        ),
        (
            {
                ATTR_PRIORITY: "trivial",
            },
            Task(priority=TaskPriority.TRIVIAL),
        ),
        (
            {
                ATTR_START_DATE: "2025-03-05",
            },
            Task(startDate=datetime(2025, 3, 5)),
        ),
        (
            {
                ATTR_FREQUENCY: "weekly",
            },
            Task(frequency=Frequency.WEEKLY),
        ),
        (
            {
                ATTR_INTERVAL: 5,
            },
            Task(everyX=5),
        ),
        (
            {
                ATTR_FREQUENCY: "weekly",
                ATTR_REPEAT: ["m", "t", "w", "th"],
            },
            Task(
                frequency=Frequency.WEEKLY,
                repeat=Repeat(m=True, t=True, w=True, th=True),
            ),
        ),
        (
            {
                ATTR_FREQUENCY: "monthly",
                ATTR_REPEAT_MONTHLY: "day_of_month",
            },
            Task(frequency=Frequency.MONTHLY, daysOfMonth=[20], weeksOfMonth=[]),
        ),
        (
            {
                ATTR_FREQUENCY: "monthly",
                ATTR_REPEAT_MONTHLY: "day_of_week",
            },
            Task(
                frequency=Frequency.MONTHLY,
                daysOfMonth=[],
                weeksOfMonth=[2],
                repeat=Repeat(
                    m=False, t=False, w=False, th=False, f=True, s=False, su=False
                ),
            ),
        ),
        (
            {
                ATTR_REMINDER: ["10:00"],
            },
            Task(
                {
                    "reminders": [
                        Reminders(
                            id=UUID("12345678-1234-5678-1234-567812345678"),
                            time=datetime(2025, 2, 25, 10, 0, tzinfo=UTC),
                            startDate=None,
                        )
                    ]
                }
            ),
        ),
        (
            {
                ATTR_REMOVE_REMINDER: ["10:00"],
            },
            Task({"reminders": []}),
        ),
        (
            {
                ATTR_CLEAR_REMINDER: True,
            },
            Task({"reminders": []}),
        ),
        (
            {
                ATTR_STREAK: 10,
            },
            Task(streak=10),
        ),
        (
            {
                ATTR_ALIAS: "ALIAS",
            },
            Task(alias="ALIAS"),
        ),
    ],
)
@pytest.mark.usefixtures("mock_uuid4")
@freeze_time("2025-02-25T22:00:00.000Z")
async def test_update_daily(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    habitica: AsyncMock,
    service_data: dict[str, Any],
    call_args: Task,
) -> None:
    """Test Habitica update daily action."""
    task_id = "6e53f1f5-a315-4edd-984d-8d762e4a08ef"

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
    habitica.update_task.assert_awaited_with(UUID(task_id), call_args)


@pytest.mark.parametrize(
    ("service_data", "call_args"),
    [
        (
            {
                ATTR_NAME: "TITLE",
            },
            Task(type=TaskType.DAILY, text="TITLE"),
        ),
        (
            {
                ATTR_NAME: "TITLE",
                ATTR_NOTES: "NOTES",
            },
            Task(type=TaskType.DAILY, text="TITLE", notes="NOTES"),
        ),
        (
            {
                ATTR_NAME: "TITLE",
                ATTR_ADD_CHECKLIST_ITEM: "Checklist-item",
            },
            Task(
                type=TaskType.DAILY,
                text="TITLE",
                checklist=[
                    Checklist(
                        id=UUID("12345678-1234-5678-1234-567812345678"),
                        text="Checklist-item",
                        completed=False,
                    ),
                ],
            ),
        ),
        (
            {
                ATTR_NAME: "TITLE",
                ATTR_PRIORITY: "trivial",
            },
            Task(type=TaskType.DAILY, text="TITLE", priority=TaskPriority.TRIVIAL),
        ),
        (
            {
                ATTR_NAME: "TITLE",
                ATTR_START_DATE: "2025-03-05",
            },
            Task(type=TaskType.DAILY, text="TITLE", startDate=datetime(2025, 3, 5)),
        ),
        (
            {
                ATTR_NAME: "TITLE",
                ATTR_FREQUENCY: "weekly",
            },
            Task(type=TaskType.DAILY, text="TITLE", frequency=Frequency.WEEKLY),
        ),
        (
            {
                ATTR_NAME: "TITLE",
                ATTR_INTERVAL: 5,
            },
            Task(type=TaskType.DAILY, text="TITLE", everyX=5),
        ),
        (
            {
                ATTR_NAME: "TITLE",
                ATTR_FREQUENCY: "weekly",
                ATTR_REPEAT: ["m", "t", "w", "th"],
            },
            Task(
                type=TaskType.DAILY,
                text="TITLE",
                frequency=Frequency.WEEKLY,
                repeat=Repeat(m=True, t=True, w=True, th=True),
            ),
        ),
        (
            {
                ATTR_NAME: "TITLE",
                ATTR_FREQUENCY: "monthly",
                ATTR_REPEAT_MONTHLY: "day_of_month",
            },
            Task(
                type=TaskType.DAILY,
                text="TITLE",
                frequency=Frequency.MONTHLY,
                daysOfMonth=[25],
                weeksOfMonth=[],
            ),
        ),
        (
            {
                ATTR_NAME: "TITLE",
                ATTR_FREQUENCY: "monthly",
                ATTR_REPEAT_MONTHLY: "day_of_week",
            },
            Task(
                type=TaskType.DAILY,
                text="TITLE",
                frequency=Frequency.MONTHLY,
                daysOfMonth=[],
                weeksOfMonth=[3],
                repeat=Repeat(
                    m=False, t=True, w=False, th=False, f=False, s=False, su=False
                ),
            ),
        ),
        (
            {
                ATTR_NAME: "TITLE",
                ATTR_REMINDER: ["10:00"],
            },
            Task(
                type=TaskType.DAILY,
                text="TITLE",
                reminders=[
                    Reminders(
                        id=UUID("12345678-1234-5678-1234-567812345678"),
                        time=datetime(2025, 2, 25, 10, 0, tzinfo=UTC),
                        startDate=None,
                    )
                ],
            ),
        ),
        (
            {
                ATTR_NAME: "TITLE",
                ATTR_REMOVE_REMINDER: ["10:00"],
            },
            Task(type=TaskType.DAILY, text="TITLE", reminders=[]),
        ),
        (
            {
                ATTR_NAME: "TITLE",
                ATTR_CLEAR_REMINDER: True,
            },
            Task(type=TaskType.DAILY, text="TITLE", reminders=[]),
        ),
        (
            {
                ATTR_NAME: "TITLE",
                ATTR_STREAK: 10,
            },
            Task(type=TaskType.DAILY, text="TITLE", streak=10),
        ),
        (
            {
                ATTR_NAME: "TITLE",
                ATTR_ALIAS: "ALIAS",
            },
            Task(type=TaskType.DAILY, text="TITLE", alias="ALIAS"),
        ),
    ],
)
@pytest.mark.usefixtures("mock_uuid4")
@freeze_time("2025-02-25T22:00:00.000Z")
async def test_create_daily(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    habitica: AsyncMock,
    service_data: dict[str, Any],
    call_args: Task,
) -> None:
    """Test Habitica create daily action."""

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CREATE_DAILY,
        service_data={
            ATTR_CONFIG_ENTRY: config_entry.entry_id,
            **service_data,
        },
        return_response=True,
        blocking=True,
    )
    habitica.create_task.assert_awaited_with(call_args)


@pytest.mark.parametrize(
    "service_data",
    [
        {
            ATTR_FREQUENCY: "daily",
            ATTR_REPEAT: ["m", "t", "w", "th"],
        },
        {
            ATTR_FREQUENCY: "weekly",
            ATTR_REPEAT_MONTHLY: "day_of_month",
        },
        {
            ATTR_FREQUENCY: "weekly",
            ATTR_REPEAT_MONTHLY: "day_of_week",
        },
    ],
)
@pytest.mark.usefixtures("mock_uuid4")
@freeze_time("2025-02-25T22:00:00.000Z")
async def test_update_daily_service_validation_errors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    habitica: AsyncMock,
    service_data: dict[str, Any],
) -> None:
    """Test Habitica update daily action."""
    task_id = "6e53f1f5-a315-4edd-984d-8d762e4a08ef"

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


async def test_tags(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    habitica: AsyncMock,
) -> None:
    """Test adding tags to a task."""
    task_id = "5e2ea1df-f6e6-4ba3-bccb-97c5ec63e99b"

    await hass.services.async_call(
        DOMAIN,
        SERVICE_UPDATE_REWARD,
        service_data={
            ATTR_CONFIG_ENTRY: config_entry.entry_id,
            ATTR_TASK: task_id,
            ATTR_TAG: ["Schule"],
        },
        return_response=True,
        blocking=True,
    )

    call_args = habitica.update_task.call_args[0]
    assert call_args[0] == UUID(task_id)
    assert set(call_args[1]["tags"]) == {
        UUID("2ac458af-0833-4f3f-bf04-98a0c33ef60b"),
        UUID("3450351f-1323-4c7e-9fd2-0cdff25b3ce0"),
        UUID("b2780f82-b3b5-49a3-a677-48f2c8c7e3bb"),
    }


async def test_create_new_tag(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    habitica: AsyncMock,
) -> None:
    """Test adding a non-existent tag and create it as new."""
    task_id = "5e2ea1df-f6e6-4ba3-bccb-97c5ec63e99b"

    await hass.services.async_call(
        DOMAIN,
        SERVICE_UPDATE_REWARD,
        service_data={
            ATTR_CONFIG_ENTRY: config_entry.entry_id,
            ATTR_TASK: task_id,
            ATTR_TAG: ["Home Assistant"],
        },
        return_response=True,
        blocking=True,
    )

    habitica.create_tag.assert_awaited_with("Home Assistant")

    call_args = habitica.update_task.call_args[0]
    assert call_args[0] == UUID(task_id)
    assert set(call_args[1]["tags"]) == {
        UUID("8bc0afbf-ab8e-49a4-982d-67a40557ed1a"),
        UUID("3450351f-1323-4c7e-9fd2-0cdff25b3ce0"),
        UUID("b2780f82-b3b5-49a3-a677-48f2c8c7e3bb"),
    }


@pytest.mark.parametrize(
    ("exception", "expected_exception", "exception_msg"),
    [
        (
            ERROR_TOO_MANY_REQUESTS,
            HomeAssistantError,
            RATE_LIMIT_EXCEPTION_MSG,
        ),
        (
            ERROR_BAD_REQUEST,
            HomeAssistantError,
            REQUEST_EXCEPTION_MSG,
        ),
        (
            ClientError,
            HomeAssistantError,
            "Unable to connect to Habitica: ",
        ),
    ],
)
async def test_create_new_tag_exception(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    habitica: AsyncMock,
    exception: Exception,
    expected_exception: Exception,
    exception_msg: str,
) -> None:
    """Test create new tag exception."""
    task_id = "5e2ea1df-f6e6-4ba3-bccb-97c5ec63e99b"

    habitica.create_tag.side_effect = exception
    with pytest.raises(expected_exception, match=exception_msg):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_UPDATE_REWARD,
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
    habitica: AsyncMock,
) -> None:
    """Test removing tags from a task."""
    task_id = "5e2ea1df-f6e6-4ba3-bccb-97c5ec63e99b"

    await hass.services.async_call(
        DOMAIN,
        SERVICE_UPDATE_REWARD,
        service_data={
            ATTR_CONFIG_ENTRY: config_entry.entry_id,
            ATTR_TASK: task_id,
            ATTR_REMOVE_TAG: ["Kreativität"],
        },
        return_response=True,
        blocking=True,
    )

    call_args = habitica.update_task.call_args[0]
    assert call_args[0] == UUID(task_id)
    assert set(call_args[1]["tags"]) == {UUID("b2780f82-b3b5-49a3-a677-48f2c8c7e3bb")}
