"""Unit tests for the Todoist integration."""

from http import HTTPStatus
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.todoist.const import (
    ASSIGNEE,
    CONTENT,
    DOMAIN,
    LABELS,
    PROJECT_NAME,
    SERVICE_NEW_TASK,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import PROJECT_ID

from tests.common import MockConfigEntry


async def test_load_unload(
    hass: HomeAssistant,
    setup_integration: None,
    todoist_config_entry: MockConfigEntry | None,
) -> None:
    """Test loading and unloading of the config entry."""
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    assert todoist_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(todoist_config_entry.entry_id)
    assert todoist_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("setup_integration")
async def test_new_task_service_uses_config_entry(
    hass: HomeAssistant,
    api: AsyncMock,
) -> None:
    """Test the new_task service reaches the config entry coordinator."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_NEW_TASK,
        {ASSIGNEE: "user", CONTENT: "task", LABELS: ["Label1"], PROJECT_NAME: "Name"},
        blocking=True,
    )

    api.add_task.assert_called_with(
        "task", project_id=PROJECT_ID, labels=["Label1"], assignee_id="1"
    )


@pytest.mark.parametrize("todoist_api_status", [HTTPStatus.INTERNAL_SERVER_ERROR])
async def test_init_failure(
    hass: HomeAssistant,
    setup_integration: None,
    api: AsyncMock,
    todoist_config_entry: MockConfigEntry | None,
) -> None:
    """Test an initialization error on integration load."""
    assert todoist_config_entry.state is ConfigEntryState.SETUP_RETRY
