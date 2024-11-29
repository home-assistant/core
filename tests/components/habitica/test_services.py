"""Test Habitica actions."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import UUID

from habiticalib import Direction, Skill
import pytest

from homeassistant.components.habitica.const import (
    ATTR_CONFIG_ENTRY,
    ATTR_DIRECTION,
    ATTR_ITEM,
    ATTR_SKILL,
    ATTR_TARGET,
    ATTR_TASK,
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

from .conftest import (
    ERROR_BAD_REQUEST,
    ERROR_NOT_AUTHORIZED,
    ERROR_NOT_FOUND,
    ERROR_TOO_MANY_REQUESTS,
)

from tests.common import MockConfigEntry

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
            "Unable to connect to Habitica, try again later",
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
            "Unable to connect to Habitica, try again later",
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
