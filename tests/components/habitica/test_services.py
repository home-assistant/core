"""Test Habitica actions."""

from collections.abc import Generator
from http import HTTPStatus
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.habitica.const import (
    ATTR_CONFIG_ENTRY,
    ATTR_SKILL,
    ATTR_TASK,
    DEFAULT_URL,
    DOMAIN,
    SERVICE_CAST_SKILL,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .conftest import mock_called_with

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


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
            "Unable to cast skill, could not find the task 'task-not-found",
        ),
        (
            {
                ATTR_TASK: "Rechnungen bezahlen",
                ATTR_SKILL: "smash",
            },
            HTTPStatus.TOO_MANY_REQUESTS,
            ServiceValidationError,
            "Rate limit exceeded, try again later",
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
            "Unable to connect to Habitica, try again later",
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
