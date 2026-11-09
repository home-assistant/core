"""Test Habitica actions."""

from collections.abc import Generator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import UUID

from aiohttp import ClientError
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
from pytest_homeassistant.common import MockConfigEntry, async_load_fixture
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.habitica.const import DOMAIN
from homeassistant.components.habitica.services import (
    HabiticaService,
    HabiticaServiceArgument,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .conftest import (
    ERROR_BAD_REQUEST,
    ERROR_NOT_AUTHORIZED,
    ERROR_NOT_FOUND,
    ERROR_TOO_MANY_REQUESTS,
)

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
                HabiticaServiceArgument.TASK: "2f6fcabc-f670-4ec3-ba65-817e8deea490",
                HabiticaServiceArgument.SKILL: "pickpocket",
            },
            {
                "skill": Skill.PICKPOCKET,
                "target_id": UUID("2f6fcabc-f670-4ec3-ba65-817e8deea490"),
            },
        ),
        (
            {
                HabiticaServiceArgument.TASK: "2f6fcabc-f670-4ec3-ba65-817e8deea490",
                HabiticaServiceArgument.SKILL: "backstab",
            },
            {
                "skill": Skill.BACKSTAB,
                "target_id": UUID("2f6fcabc-f670-4ec3-ba65-817e8deea490"),
            },
        ),
        (
            {
                HabiticaServiceArgument.TASK: "2f6fcabc-f670-4ec3-ba65-817e8deea490",
                HabiticaServiceArgument.SKILL: "fireball",
            },
            {
                "skill": Skill.BURST_OF_FLAMES,
                "target_id": UUID("2f6fcabc-f670-4ec3-ba65-817e8deea490"),
            },
        ),
        (
            {
                HabiticaServiceArgument.TASK: "2f6fcabc-f670-4ec3-ba65-817e8deea490",
                HabiticaServiceArgument.SKILL: "smash",
            },
            {
                "skill": Skill.BRUTAL_SMASH,
                "target_id": UUID("2f6fcabc-f670-4ec3-ba65-817e8deea490"),
            },
        ),
        (
            {
                HabiticaServiceArgument.TASK: "Rechnungen bezahlen",
                HabiticaServiceArgument.SKILL: "smash",
            },
            {
                "skill": Skill.BRUTAL_SMASH,
                "target_id": UUID("2f6fcabc-f670-4ec3-ba65-817e8deea490"),
            },
        ),
        (
            {
                HabiticaServiceArgument.TASK: "pay_bills",
                HabiticaServiceArgument.SKILL: "smash",
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
        HabiticaService.CAST_SKILL,
        service_data={
            HabiticaServiceArgument.CONFIG_ENTRY: config_entry.entry_id,
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
                HabiticaServiceArgument.TASK: "task-not-found",
                HabiticaServiceArgument.SKILL: "smash",
            },
            None,
            ServiceValidationError,
            "Unable to complete action, could not find the task 'task-not-found'",
        ),
        (
            {
                HabiticaServiceArgument.TASK: "Rechnungen bezahlen",
                HabiticaServiceArgument.SKILL: "smash",
            },
            ERROR_TOO_MANY_REQUESTS,
            HomeAssistantError,
            RATE_LIMIT_EXCEPTION_MSG,
        ),
        (
            {
                HabiticaServiceArgument.TASK: "Rechnungen bezahlen",
                HabiticaServiceArgument.SKILL: "smash",
            },
            ERROR_NOT_FOUND,
            ServiceValidationError,
            "Unable to cast skill, your character does not have"
            " the skill or spell smash",
        ),
        (
            {
                HabiticaServiceArgument.TASK: "Rechnungen bezahlen",
                HabiticaServiceArgument.SKILL: "smash",
            },
            ERROR_NOT_AUTHORIZED,
            ServiceValidationError,
            "Unable to cast skill, not enough mana. Your character"
            " has 50 MP, but the skill costs 10 MP",
        ),
        (
            {
                HabiticaServiceArgument.TASK: "Rechnungen bezahlen",
                HabiticaServiceArgument.SKILL: "smash",
            },
            ERROR_BAD_REQUEST,
            HomeAssistantError,
            REQUEST_EXCEPTION_MSG,
        ),
        (
            {
                HabiticaServiceArgument.TASK: "Rechnungen bezahlen",
                HabiticaServiceArgument.SKILL: "smash",
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
            HabiticaService.CAST_SKILL,
            service_data={
                HabiticaServiceArgument.CONFIG_ENTRY: config_entry.entry_id,
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

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            HabiticaService.CAST_SKILL,
            service_data={
                HabiticaServiceArgument.CONFIG_ENTRY: "0000000000000000",
                HabiticaServiceArgument.TASK: "2f6fcabc-f670-4ec3-ba65-817e8deea490",
                HabiticaServiceArgument.SKILL: "smash",
            },
            return_response=True,
            blocking=True,
        )
    assert err.value.translation_key == "service_config_entry_not_found"

    assert await hass.config_entries.async_unload(config_entry.entry_id)

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            HabiticaService.CAST_SKILL,
            service_data={
                HabiticaServiceArgument.CONFIG_ENTRY: config_entry.entry_id,
                HabiticaServiceArgument.TASK: "2f6fcabc-f670-4ec3-ba65-817e8deea490",
                HabiticaServiceArgument.SKILL: "smash",
            },
            return_response=True,
            blocking=True,
        )
    assert err.value.translation_key == "service_config_entry_not_loaded"


@pytest.mark.parametrize(
    "service",
    [
        HabiticaService.ABORT_QUEST,
        HabiticaService.ACCEPT_QUEST,
        HabiticaService.CANCEL_QUEST,
        HabiticaService.LEAVE_QUEST,
        HabiticaService.REJECT_QUEST,
        HabiticaService.START_QUEST,
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
        service_data={HabiticaServiceArgument.CONFIG_ENTRY: config_entry.entry_id},
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
            "Action not allowed, only quest leader or group leader"
            " can perform this action",
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
        HabiticaService.ACCEPT_QUEST,
        HabiticaService.ABORT_QUEST,
        HabiticaService.CANCEL_QUEST,
        HabiticaService.LEAVE_QUEST,
        HabiticaService.REJECT_QUEST,
        HabiticaService.START_QUEST,
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
            service_data={HabiticaServiceArgument.CONFIG_ENTRY: config_entry.entry_id},
            return_response=True,
            blocking=True,
        )


@pytest.mark.parametrize(
    ("service", "service_data", "call_args"),
    [
        (
            HabiticaService.SCORE_HABIT,
            {
                HabiticaServiceArgument.TASK: "e97659e0-2c42-4599-a7bb-00282adc410d",
                HabiticaServiceArgument.DIRECTION: "up",
            },
            {
                "task_id": UUID("e97659e0-2c42-4599-a7bb-00282adc410d"),
                "direction": Direction.UP,
            },
        ),
        (
            HabiticaService.SCORE_HABIT,
            {
                HabiticaServiceArgument.TASK: "e97659e0-2c42-4599-a7bb-00282adc410d",
                HabiticaServiceArgument.DIRECTION: "down",
            },
            {
                "task_id": UUID("e97659e0-2c42-4599-a7bb-00282adc410d"),
                "direction": Direction.DOWN,
            },
        ),
        (
            HabiticaService.SCORE_REWARD,
            {
                HabiticaServiceArgument.TASK: "5e2ea1df-f6e6-4ba3-bccb-97c5ec63e99b",
            },
            {
                "task_id": UUID("5e2ea1df-f6e6-4ba3-bccb-97c5ec63e99b"),
                "direction": Direction.UP,
            },
        ),
        (
            HabiticaService.SCORE_HABIT,
            {
                HabiticaServiceArgument.TASK: "Füge eine Aufgabe zu Habitica hinzu",
                HabiticaServiceArgument.DIRECTION: "up",
            },
            {
                "task_id": UUID("e97659e0-2c42-4599-a7bb-00282adc410d"),
                "direction": Direction.UP,
            },
        ),
        (
            HabiticaService.SCORE_HABIT,
            {
                HabiticaServiceArgument.TASK: "create_a_task",
                HabiticaServiceArgument.DIRECTION: "up",
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
            HabiticaServiceArgument.CONFIG_ENTRY: config_entry.entry_id,
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
                HabiticaServiceArgument.TASK: "task does not exist",
                HabiticaServiceArgument.DIRECTION: "up",
            },
            None,
            ServiceValidationError,
            "Unable to complete action, could not find the task 'task does not exist'",
        ),
        (
            {
                HabiticaServiceArgument.TASK: "e97659e0-2c42-4599-a7bb-00282adc410d",
                HabiticaServiceArgument.DIRECTION: "up",
            },
            ERROR_TOO_MANY_REQUESTS,
            HomeAssistantError,
            RATE_LIMIT_EXCEPTION_MSG,
        ),
        (
            {
                HabiticaServiceArgument.TASK: "e97659e0-2c42-4599-a7bb-00282adc410d",
                HabiticaServiceArgument.DIRECTION: "up",
            },
            ERROR_BAD_REQUEST,
            HomeAssistantError,
            REQUEST_EXCEPTION_MSG,
        ),
        (
            {
                HabiticaServiceArgument.TASK: "e97659e0-2c42-4599-a7bb-00282adc410d",
                HabiticaServiceArgument.DIRECTION: "up",
            },
            ClientError,
            HomeAssistantError,
            "Unable to connect to Habitica: ",
        ),
        (
            {
                HabiticaServiceArgument.TASK: "5e2ea1df-f6e6-4ba3-bccb-97c5ec63e99b",
                HabiticaServiceArgument.DIRECTION: "up",
            },
            ERROR_NOT_AUTHORIZED,
            HomeAssistantError,
            "Unable to buy reward, not enough gold. Your character"
            " has 137.63 GP, but the reward costs 10.00 GP",
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
            HabiticaService.SCORE_HABIT,
            service_data={
                HabiticaServiceArgument.CONFIG_ENTRY: config_entry.entry_id,
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
                HabiticaServiceArgument.TARGET: "a380546a-94be-4b8e-8a0b-23e0d5c03303",
                HabiticaServiceArgument.ITEM: "spooky_sparkles",
            },
            {
                "skill": Skill.SPOOKY_SPARKLES,
                "target_id": UUID("a380546a-94be-4b8e-8a0b-23e0d5c03303"),
            },
        ),
        (
            {
                HabiticaServiceArgument.TARGET: "a380546a-94be-4b8e-8a0b-23e0d5c03303",
                HabiticaServiceArgument.ITEM: "shiny_seed",
            },
            {
                "skill": Skill.SHINY_SEED,
                "target_id": UUID("a380546a-94be-4b8e-8a0b-23e0d5c03303"),
            },
        ),
        (
            {
                HabiticaServiceArgument.TARGET: "a380546a-94be-4b8e-8a0b-23e0d5c03303",
                HabiticaServiceArgument.ITEM: "seafoam",
            },
            {
                "skill": Skill.SEAFOAM,
                "target_id": UUID("a380546a-94be-4b8e-8a0b-23e0d5c03303"),
            },
        ),
        (
            {
                HabiticaServiceArgument.TARGET: "a380546a-94be-4b8e-8a0b-23e0d5c03303",
                HabiticaServiceArgument.ITEM: "snowball",
            },
            {
                "skill": Skill.SNOWBALL,
                "target_id": UUID("a380546a-94be-4b8e-8a0b-23e0d5c03303"),
            },
        ),
        (
            {
                HabiticaServiceArgument.TARGET: "test-user",
                HabiticaServiceArgument.ITEM: "spooky_sparkles",
            },
            {
                "skill": Skill.SPOOKY_SPARKLES,
                "target_id": UUID("a380546a-94be-4b8e-8a0b-23e0d5c03303"),
            },
        ),
        (
            {
                HabiticaServiceArgument.TARGET: "test-username",
                HabiticaServiceArgument.ITEM: "spooky_sparkles",
            },
            {
                "skill": Skill.SPOOKY_SPARKLES,
                "target_id": UUID("a380546a-94be-4b8e-8a0b-23e0d5c03303"),
            },
        ),
        (
            {
                HabiticaServiceArgument.TARGET: "ffce870c-3ff3-4fa4-bad1-87612e52b8e7",
                HabiticaServiceArgument.ITEM: "spooky_sparkles",
            },
            {
                "skill": Skill.SPOOKY_SPARKLES,
                "target_id": UUID("ffce870c-3ff3-4fa4-bad1-87612e52b8e7"),
            },
        ),
        (
            {
                HabiticaServiceArgument.TARGET: "test-partymember-username",
                HabiticaServiceArgument.ITEM: "spooky_sparkles",
            },
            {
                "skill": Skill.SPOOKY_SPARKLES,
                "target_id": UUID("ffce870c-3ff3-4fa4-bad1-87612e52b8e7"),
            },
        ),
        (
            {
                HabiticaServiceArgument.TARGET: "test-partymember-displayname",
                HabiticaServiceArgument.ITEM: "spooky_sparkles",
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
        HabiticaService.TRANSFORMATION,
        service_data={
            HabiticaServiceArgument.CONFIG_ENTRY: config_entry.entry_id,
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
                HabiticaServiceArgument.TARGET: "user-not-found",
                HabiticaServiceArgument.ITEM: "spooky_sparkles",
            },
            None,
            None,
            ServiceValidationError,
            "Unable to find target 'user-not-found' in your party",
        ),
        (
            {
                HabiticaServiceArgument.TARGET: "test-partymember-username",
                HabiticaServiceArgument.ITEM: "spooky_sparkles",
            },
            ERROR_NOT_FOUND,
            None,
            ServiceValidationError,
            "Unable to find target, you are currently not in a"
            " party. You can only target yourself",
        ),
        (
            {
                HabiticaServiceArgument.TARGET: "test-partymember-username",
                HabiticaServiceArgument.ITEM: "spooky_sparkles",
            },
            ERROR_BAD_REQUEST,
            None,
            HomeAssistantError,
            REQUEST_EXCEPTION_MSG,
        ),
        (
            {
                HabiticaServiceArgument.TARGET: "test-partymember-username",
                HabiticaServiceArgument.ITEM: "spooky_sparkles",
            },
            None,
            ERROR_TOO_MANY_REQUESTS,
            HomeAssistantError,
            RATE_LIMIT_EXCEPTION_MSG,
        ),
        (
            {
                HabiticaServiceArgument.TARGET: "test-partymember-username",
                HabiticaServiceArgument.ITEM: "spooky_sparkles",
            },
            None,
            ERROR_NOT_AUTHORIZED,
            ServiceValidationError,
            "Unable to use spooky_sparkles, you don't own this item",
        ),
        (
            {
                HabiticaServiceArgument.TARGET: "test-partymember-username",
                HabiticaServiceArgument.ITEM: "spooky_sparkles",
            },
            None,
            ERROR_BAD_REQUEST,
            HomeAssistantError,
            REQUEST_EXCEPTION_MSG,
        ),
        (
            {
                HabiticaServiceArgument.TARGET: "test-partymember-username",
                HabiticaServiceArgument.ITEM: "spooky_sparkles",
            },
            None,
            ClientError,
            HomeAssistantError,
            "Unable to connect to Habitica: ",
        ),
        (
            {
                HabiticaServiceArgument.TARGET: "test-partymember-username",
                HabiticaServiceArgument.ITEM: "spooky_sparkles",
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
            HabiticaService.TRANSFORMATION,
            service_data={
                HabiticaServiceArgument.CONFIG_ENTRY: config_entry.entry_id,
                **service_data,
            },
            return_response=True,
            blocking=True,
        )


@pytest.mark.parametrize(
    ("service_data"),
    [
        {},
        {HabiticaServiceArgument.TYPE: ["daily"]},
        {HabiticaServiceArgument.TYPE: ["habit"]},
        {HabiticaServiceArgument.TYPE: ["todo"]},
        {HabiticaServiceArgument.TYPE: ["reward"]},
        {HabiticaServiceArgument.TYPE: ["daily", "habit"]},
        {HabiticaServiceArgument.TYPE: ["todo", "reward"]},
        {HabiticaServiceArgument.PRIORITY: "trivial"},
        {HabiticaServiceArgument.PRIORITY: "easy"},
        {HabiticaServiceArgument.PRIORITY: "medium"},
        {HabiticaServiceArgument.PRIORITY: "hard"},
        {
            HabiticaServiceArgument.TASK: [
                "Zahnseide benutzen",
                "Eine kurze Pause machen",
            ]
        },
        {HabiticaServiceArgument.TASK: ["f2c85972-1a19-4426-bc6d-ce3337b9d99f"]},
        {HabiticaServiceArgument.TASK: ["alias_zahnseide_benutzen"]},
        {HabiticaServiceArgument.TAG: ["Training", "Gesundheit + Wohlbefinden"]},
        {HabiticaServiceArgument.KEYWORD: "gewohnheit"},
        {HabiticaServiceArgument.TAG: ["Home Assistant"]},
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
        HabiticaService.GET_TASKS,
        service_data={
            HabiticaServiceArgument.CONFIG_ENTRY: config_entry.entry_id,
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
        (HabiticaService.UPDATE_REWARD, "5e2ea1df-f6e6-4ba3-bccb-97c5ec63e99b"),
        (HabiticaService.UPDATE_HABIT, "f21fa608-cfc6-4413-9fc7-0eb1b48ca43a"),
        (HabiticaService.UPDATE_TODO, "88de7cd9-af2b-49ce-9afd-bf941d87336b"),
        (HabiticaService.UPDATE_DAILY, "6e53f1f5-a315-4edd-984d-8d762e4a08ef"),
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
                HabiticaServiceArgument.CONFIG_ENTRY: config_entry.entry_id,
                HabiticaServiceArgument.TASK: task_id,
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
        HabiticaService.CREATE_DAILY,
        HabiticaService.CREATE_HABIT,
        HabiticaService.CREATE_REWARD,
        HabiticaService.CREATE_TODO,
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
                HabiticaServiceArgument.CONFIG_ENTRY: config_entry.entry_id,
                HabiticaServiceArgument.NAME: "TITLE",
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
        match=(
            "Unable to complete action, could not find the task"
            " '7f902bbc-eb3d-4a8f-82cf-4e2025d69af1'"
        ),
    ):
        await hass.services.async_call(
            DOMAIN,
            HabiticaService.UPDATE_REWARD,
            service_data={
                HabiticaServiceArgument.CONFIG_ENTRY: config_entry.entry_id,
                HabiticaServiceArgument.TASK: task_id,
            },
            return_response=True,
            blocking=True,
        )


@pytest.mark.parametrize(
    ("service_data", "call_args"),
    [
        (
            {
                HabiticaServiceArgument.COST: 100,
            },
            Task(value=100),
        ),
        (
            {
                HabiticaServiceArgument.RENAME: "RENAME",
            },
            Task(text="RENAME"),
        ),
        (
            {
                HabiticaServiceArgument.NOTES: "NOTES",
            },
            Task(notes="NOTES"),
        ),
        (
            {
                HabiticaServiceArgument.ALIAS: "ALIAS",
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
        await async_load_fixture(hass, "task.json", DOMAIN)
    )
    await hass.services.async_call(
        DOMAIN,
        HabiticaService.UPDATE_REWARD,
        service_data={
            HabiticaServiceArgument.CONFIG_ENTRY: config_entry.entry_id,
            HabiticaServiceArgument.TASK: task_id,
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
                HabiticaServiceArgument.NAME: "TITLE",
                HabiticaServiceArgument.COST: 100,
            },
            Task(type=TaskType.REWARD, text="TITLE", value=100),
        ),
        (
            {
                HabiticaServiceArgument.NAME: "TITLE",
            },
            Task(type=TaskType.REWARD, text="TITLE"),
        ),
        (
            {
                HabiticaServiceArgument.NAME: "TITLE",
                HabiticaServiceArgument.NOTES: "NOTES",
            },
            Task(type=TaskType.REWARD, text="TITLE", notes="NOTES"),
        ),
        (
            {
                HabiticaServiceArgument.NAME: "TITLE",
                HabiticaServiceArgument.ALIAS: "ALIAS",
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
        HabiticaService.CREATE_REWARD,
        service_data={
            HabiticaServiceArgument.CONFIG_ENTRY: config_entry.entry_id,
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
                HabiticaServiceArgument.RENAME: "RENAME",
            },
            Task(text="RENAME"),
        ),
        (
            {
                HabiticaServiceArgument.NOTES: "NOTES",
            },
            Task(notes="NOTES"),
        ),
        (
            {
                HabiticaServiceArgument.UP_DOWN: [""],
            },
            Task(up=False, down=False),
        ),
        (
            {
                HabiticaServiceArgument.UP_DOWN: ["up"],
            },
            Task(up=True, down=False),
        ),
        (
            {
                HabiticaServiceArgument.UP_DOWN: ["down"],
            },
            Task(up=False, down=True),
        ),
        (
            {
                HabiticaServiceArgument.PRIORITY: "trivial",
            },
            Task(priority=TaskPriority.TRIVIAL),
        ),
        (
            {
                HabiticaServiceArgument.FREQUENCY: "daily",
            },
            Task(frequency=Frequency.DAILY),
        ),
        (
            {
                HabiticaServiceArgument.COUNTER_UP: 1,
                HabiticaServiceArgument.COUNTER_DOWN: 2,
            },
            Task(counterUp=1, counterDown=2),
        ),
        (
            {
                HabiticaServiceArgument.ALIAS: "ALIAS",
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
        HabiticaService.UPDATE_HABIT,
        service_data={
            HabiticaServiceArgument.CONFIG_ENTRY: config_entry.entry_id,
            HabiticaServiceArgument.TASK: task_id,
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
                HabiticaServiceArgument.NAME: "TITLE",
            },
            Task(type=TaskType.HABIT, text="TITLE"),
        ),
        (
            {
                HabiticaServiceArgument.NAME: "TITLE",
                HabiticaServiceArgument.NOTES: "NOTES",
            },
            Task(type=TaskType.HABIT, text="TITLE", notes="NOTES"),
        ),
        (
            {
                HabiticaServiceArgument.NAME: "TITLE",
                HabiticaServiceArgument.UP_DOWN: [""],
            },
            Task(type=TaskType.HABIT, text="TITLE", up=False, down=False),
        ),
        (
            {
                HabiticaServiceArgument.NAME: "TITLE",
                HabiticaServiceArgument.UP_DOWN: ["up"],
            },
            Task(type=TaskType.HABIT, text="TITLE", up=True, down=False),
        ),
        (
            {
                HabiticaServiceArgument.NAME: "TITLE",
                HabiticaServiceArgument.UP_DOWN: ["down"],
            },
            Task(type=TaskType.HABIT, text="TITLE", up=False, down=True),
        ),
        (
            {
                HabiticaServiceArgument.NAME: "TITLE",
                HabiticaServiceArgument.PRIORITY: "trivial",
            },
            Task(type=TaskType.HABIT, text="TITLE", priority=TaskPriority.TRIVIAL),
        ),
        (
            {
                HabiticaServiceArgument.NAME: "TITLE",
                HabiticaServiceArgument.FREQUENCY: "daily",
            },
            Task(type=TaskType.HABIT, text="TITLE", frequency=Frequency.DAILY),
        ),
        (
            {
                HabiticaServiceArgument.NAME: "TITLE",
                HabiticaServiceArgument.ALIAS: "ALIAS",
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
        HabiticaService.CREATE_HABIT,
        service_data={
            HabiticaServiceArgument.CONFIG_ENTRY: config_entry.entry_id,
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
                HabiticaServiceArgument.RENAME: "RENAME",
            },
            Task(text="RENAME"),
        ),
        (
            {
                HabiticaServiceArgument.NOTES: "NOTES",
            },
            Task(notes="NOTES"),
        ),
        (
            {
                HabiticaServiceArgument.ADD_CHECKLIST_ITEM: "Checklist-item",
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
                HabiticaServiceArgument.REMOVE_CHECKLIST_ITEM: "Checklist-item1",
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
                HabiticaServiceArgument.SCORE_CHECKLIST_ITEM: "Checklist-item1",
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
                HabiticaServiceArgument.UNSCORE_CHECKLIST_ITEM: "Checklist-item2",
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
                HabiticaServiceArgument.PRIORITY: "trivial",
            },
            Task(priority=TaskPriority.TRIVIAL),
        ),
        (
            {
                HabiticaServiceArgument.DATE: "2025-03-05",
            },
            Task(date=datetime(2025, 3, 5)),
        ),
        (
            {
                HabiticaServiceArgument.CLEAR_DATE: True,
            },
            Task(date=None),
        ),
        (
            {
                HabiticaServiceArgument.REMINDER: ["2025-02-25T00:00"],
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
                HabiticaServiceArgument.REMOVE_REMINDER: ["2025-02-25T00:00"],
            },
            Task({"reminders": []}),
        ),
        (
            {
                HabiticaServiceArgument.CLEAR_REMINDER: True,
            },
            Task({"reminders": []}),
        ),
        (
            {
                HabiticaServiceArgument.ALIAS: "ALIAS",
            },
            Task(alias="ALIAS"),
        ),
        (
            {
                HabiticaServiceArgument.COLLAPSE_CHECKLIST: "collapsed",
            },
            Task(collapseChecklist=True),
        ),
        (
            {
                HabiticaServiceArgument.COLLAPSE_CHECKLIST: "expanded",
            },
            Task(collapseChecklist=False),
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
        HabiticaService.UPDATE_TODO,
        service_data={
            HabiticaServiceArgument.CONFIG_ENTRY: config_entry.entry_id,
            HabiticaServiceArgument.TASK: task_id,
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
                HabiticaServiceArgument.NAME: "TITLE",
            },
            Task(type=TaskType.TODO, text="TITLE"),
        ),
        (
            {
                HabiticaServiceArgument.NAME: "TITLE",
                HabiticaServiceArgument.NOTES: "NOTES",
            },
            Task(type=TaskType.TODO, text="TITLE", notes="NOTES"),
        ),
        (
            {
                HabiticaServiceArgument.NAME: "TITLE",
                HabiticaServiceArgument.ADD_CHECKLIST_ITEM: "Checklist-item",
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
                HabiticaServiceArgument.NAME: "TITLE",
                HabiticaServiceArgument.PRIORITY: "trivial",
            },
            Task(type=TaskType.TODO, text="TITLE", priority=TaskPriority.TRIVIAL),
        ),
        (
            {
                HabiticaServiceArgument.NAME: "TITLE",
                HabiticaServiceArgument.DATE: "2025-03-05",
            },
            Task(type=TaskType.TODO, text="TITLE", date=datetime(2025, 3, 5)),
        ),
        (
            {
                HabiticaServiceArgument.NAME: "TITLE",
                HabiticaServiceArgument.REMINDER: ["2025-02-25T00:00"],
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
                HabiticaServiceArgument.NAME: "TITLE",
                HabiticaServiceArgument.ALIAS: "ALIAS",
            },
            Task(type=TaskType.TODO, text="TITLE", alias="ALIAS"),
        ),
        (
            {
                HabiticaServiceArgument.NAME: "TITLE",
                HabiticaServiceArgument.COLLAPSE_CHECKLIST: "collapsed",
            },
            Task(type=TaskType.TODO, text="TITLE", collapseChecklist=True),
        ),
        (
            {
                HabiticaServiceArgument.NAME: "TITLE",
                HabiticaServiceArgument.COLLAPSE_CHECKLIST: "expanded",
            },
            Task(type=TaskType.TODO, text="TITLE", collapseChecklist=False),
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
        HabiticaService.CREATE_TODO,
        service_data={
            HabiticaServiceArgument.CONFIG_ENTRY: config_entry.entry_id,
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
                HabiticaServiceArgument.RENAME: "RENAME",
            },
            Task(text="RENAME"),
        ),
        (
            {
                HabiticaServiceArgument.NOTES: "NOTES",
            },
            Task(notes="NOTES"),
        ),
        (
            {
                HabiticaServiceArgument.ADD_CHECKLIST_ITEM: "Checklist-item",
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
                HabiticaServiceArgument.REMOVE_CHECKLIST_ITEM: "Checklist-item1",
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
                HabiticaServiceArgument.SCORE_CHECKLIST_ITEM: "Checklist-item1",
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
                HabiticaServiceArgument.UNSCORE_CHECKLIST_ITEM: "Checklist-item2",
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
                HabiticaServiceArgument.PRIORITY: "trivial",
            },
            Task(priority=TaskPriority.TRIVIAL),
        ),
        (
            {
                HabiticaServiceArgument.START_DATE: "2025-03-05",
            },
            Task(startDate=datetime(2025, 3, 5)),
        ),
        (
            {
                HabiticaServiceArgument.FREQUENCY: "weekly",
            },
            Task(frequency=Frequency.WEEKLY),
        ),
        (
            {
                HabiticaServiceArgument.EVERY_X: 5,
            },
            Task(everyX=5),
        ),
        (
            {
                HabiticaServiceArgument.EVERY_X: 0,
            },
            Task(everyX=0),
        ),
        (
            {
                HabiticaServiceArgument.FREQUENCY: "weekly",
                HabiticaServiceArgument.REPEAT: ["m", "t", "w", "th"],
            },
            Task(
                frequency=Frequency.WEEKLY,
                repeat=Repeat(m=True, t=True, w=True, th=True),
            ),
        ),
        (
            {
                HabiticaServiceArgument.FREQUENCY: "monthly",
                HabiticaServiceArgument.REPEAT_MONTHLY: "day_of_month",
            },
            Task(frequency=Frequency.MONTHLY, daysOfMonth=[20], weeksOfMonth=[]),
        ),
        (
            {
                HabiticaServiceArgument.FREQUENCY: "monthly",
                HabiticaServiceArgument.REPEAT_MONTHLY: "day_of_week",
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
                HabiticaServiceArgument.REMINDER: ["10:00"],
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
                HabiticaServiceArgument.REMOVE_REMINDER: ["10:00"],
            },
            Task({"reminders": []}),
        ),
        (
            {
                HabiticaServiceArgument.CLEAR_REMINDER: True,
            },
            Task({"reminders": []}),
        ),
        (
            {
                HabiticaServiceArgument.STREAK: 10,
            },
            Task(streak=10),
        ),
        (
            {
                HabiticaServiceArgument.ALIAS: "ALIAS",
            },
            Task(alias="ALIAS"),
        ),
    ],
)
@pytest.mark.usefixtures("mock_uuid4")
@pytest.mark.freeze_time("2025-02-25T22:00:00.000Z")
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
        HabiticaService.UPDATE_DAILY,
        service_data={
            HabiticaServiceArgument.CONFIG_ENTRY: config_entry.entry_id,
            HabiticaServiceArgument.TASK: task_id,
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
                HabiticaServiceArgument.NAME: "TITLE",
            },
            Task(type=TaskType.DAILY, text="TITLE"),
        ),
        (
            {
                HabiticaServiceArgument.NAME: "TITLE",
                HabiticaServiceArgument.NOTES: "NOTES",
            },
            Task(type=TaskType.DAILY, text="TITLE", notes="NOTES"),
        ),
        (
            {
                HabiticaServiceArgument.NAME: "TITLE",
                HabiticaServiceArgument.ADD_CHECKLIST_ITEM: "Checklist-item",
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
                HabiticaServiceArgument.NAME: "TITLE",
                HabiticaServiceArgument.PRIORITY: "trivial",
            },
            Task(type=TaskType.DAILY, text="TITLE", priority=TaskPriority.TRIVIAL),
        ),
        (
            {
                HabiticaServiceArgument.NAME: "TITLE",
                HabiticaServiceArgument.START_DATE: "2025-03-05",
            },
            Task(type=TaskType.DAILY, text="TITLE", startDate=datetime(2025, 3, 5)),
        ),
        (
            {
                HabiticaServiceArgument.NAME: "TITLE",
                HabiticaServiceArgument.FREQUENCY: "weekly",
            },
            Task(type=TaskType.DAILY, text="TITLE", frequency=Frequency.WEEKLY),
        ),
        (
            {
                HabiticaServiceArgument.NAME: "TITLE",
                HabiticaServiceArgument.EVERY_X: 5,
            },
            Task(type=TaskType.DAILY, text="TITLE", everyX=5),
        ),
        (
            {
                HabiticaServiceArgument.NAME: "TITLE",
                HabiticaServiceArgument.FREQUENCY: "weekly",
                HabiticaServiceArgument.REPEAT: ["m", "t", "w", "th"],
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
                HabiticaServiceArgument.NAME: "TITLE",
                HabiticaServiceArgument.FREQUENCY: "monthly",
                HabiticaServiceArgument.REPEAT_MONTHLY: "day_of_month",
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
                HabiticaServiceArgument.NAME: "TITLE",
                HabiticaServiceArgument.FREQUENCY: "monthly",
                HabiticaServiceArgument.REPEAT_MONTHLY: "day_of_week",
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
                HabiticaServiceArgument.NAME: "TITLE",
                HabiticaServiceArgument.REMINDER: ["10:00"],
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
                HabiticaServiceArgument.NAME: "TITLE",
                HabiticaServiceArgument.REMOVE_REMINDER: ["10:00"],
            },
            Task(type=TaskType.DAILY, text="TITLE", reminders=[]),
        ),
        (
            {
                HabiticaServiceArgument.NAME: "TITLE",
                HabiticaServiceArgument.CLEAR_REMINDER: True,
            },
            Task(type=TaskType.DAILY, text="TITLE", reminders=[]),
        ),
        (
            {
                HabiticaServiceArgument.NAME: "TITLE",
                HabiticaServiceArgument.STREAK: 10,
            },
            Task(type=TaskType.DAILY, text="TITLE", streak=10),
        ),
        (
            {
                HabiticaServiceArgument.NAME: "TITLE",
                HabiticaServiceArgument.ALIAS: "ALIAS",
            },
            Task(type=TaskType.DAILY, text="TITLE", alias="ALIAS"),
        ),
    ],
)
@pytest.mark.usefixtures("mock_uuid4")
@pytest.mark.freeze_time("2025-02-25T22:00:00.000Z")
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
        HabiticaService.CREATE_DAILY,
        service_data={
            HabiticaServiceArgument.CONFIG_ENTRY: config_entry.entry_id,
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
            HabiticaServiceArgument.FREQUENCY: "daily",
            HabiticaServiceArgument.REPEAT: ["m", "t", "w", "th"],
        },
        {
            HabiticaServiceArgument.FREQUENCY: "weekly",
            HabiticaServiceArgument.REPEAT_MONTHLY: "day_of_month",
        },
        {
            HabiticaServiceArgument.FREQUENCY: "weekly",
            HabiticaServiceArgument.REPEAT_MONTHLY: "day_of_week",
        },
    ],
)
@pytest.mark.usefixtures("mock_uuid4")
@pytest.mark.freeze_time("2025-02-25T22:00:00.000Z")
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
            HabiticaService.UPDATE_DAILY,
            service_data={
                HabiticaServiceArgument.CONFIG_ENTRY: config_entry.entry_id,
                HabiticaServiceArgument.TASK: task_id,
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
        HabiticaService.UPDATE_REWARD,
        service_data={
            HabiticaServiceArgument.CONFIG_ENTRY: config_entry.entry_id,
            HabiticaServiceArgument.TASK: task_id,
            HabiticaServiceArgument.TAG: ["Schule"],
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
        HabiticaService.UPDATE_REWARD,
        service_data={
            HabiticaServiceArgument.CONFIG_ENTRY: config_entry.entry_id,
            HabiticaServiceArgument.TASK: task_id,
            HabiticaServiceArgument.TAG: ["Home Assistant"],
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
            HabiticaService.UPDATE_REWARD,
            service_data={
                HabiticaServiceArgument.CONFIG_ENTRY: config_entry.entry_id,
                HabiticaServiceArgument.TASK: task_id,
                HabiticaServiceArgument.TAG: ["Home Assistant"],
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
        HabiticaService.UPDATE_REWARD,
        service_data={
            HabiticaServiceArgument.CONFIG_ENTRY: config_entry.entry_id,
            HabiticaServiceArgument.TASK: task_id,
            HabiticaServiceArgument.REMOVE_TAG: ["Kreativität"],
        },
        return_response=True,
        blocking=True,
    )

    call_args = habitica.update_task.call_args[0]
    assert call_args[0] == UUID(task_id)
    assert set(call_args[1]["tags"]) == {UUID("b2780f82-b3b5-49a3-a677-48f2c8c7e3bb")}
