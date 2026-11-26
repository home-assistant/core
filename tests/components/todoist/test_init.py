"""Unit tests for the Todoist integration."""

from http import HTTPStatus
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from todoist_api_python.models import Project

from homeassistant.components.todoist.const import DOMAIN
from homeassistant.components.todoist.services import (
    TodoistService,
    TodoistServiceArgument,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import PROJECT_ID, make_api_response


async def test_load_unload(
    hass: HomeAssistant,
    setup_integration: None,
    api: AsyncMock,
    todoist_config_entry: MockConfigEntry | None,
) -> None:
    """Test loading and unloading of the config entry."""
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    assert todoist_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(todoist_config_entry.entry_id)
    assert todoist_config_entry.state is ConfigEntryState.NOT_LOADED
    api.close.assert_awaited_once()


async def test_shutdown_closes_api(
    hass: HomeAssistant,
    setup_integration: None,
    api: AsyncMock,
    todoist_config_entry: MockConfigEntry | None,
) -> None:
    """Test the API client is closed when Home Assistant stops."""
    assert todoist_config_entry.state is ConfigEntryState.LOADED
    api.close.assert_not_awaited()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    api.close.assert_awaited_once()


@pytest.mark.usefixtures("setup_integration")
async def test_new_task_service_uses_config_entry(
    hass: HomeAssistant,
    api: AsyncMock,
) -> None:
    """Test the new_task service reaches the config entry coordinator."""
    await hass.services.async_call(
        DOMAIN,
        TodoistService.NEW_TASK,
        {
            TodoistServiceArgument.ASSIGNEE: "user",
            TodoistServiceArgument.CONTENT: "task",
            TodoistServiceArgument.LABELS: ["Label1"],
            TodoistServiceArgument.PROJECT: "Name",
        },
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


@pytest.mark.parametrize(
    "view_style", ["list", "board", "calendar", "table", "future_layout"]
)
async def test_project_deserialization_setup(
    hass: HomeAssistant,
    api: AsyncMock,
    todoist_config_entry: MockConfigEntry,
    view_style: str,
    entity_registry: er.EntityRegistry,
) -> None:
    """Deserialize API projects before setting up both platforms."""
    project = Project.from_dict(
        {
            "id": PROJECT_ID,
            "name": "Synthetic project",
            "description": "",
            "child_order": 1,
            "color": "blue",
            "collapsed": False,
            "shared": False,
            "is_favorite": False,
            "is_archived": False,
            "can_assign_tasks": False,
            "view_style": view_style,
            "created_at": "2026-01-01T00:00:00.000000Z",
            "updated_at": "2026-01-01T00:00:00.000000Z",
        }
    )
    api.get_projects.side_effect = make_api_response([project])
    todoist_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.todoist.TodoistAPIAsync", return_value=api):
        assert await hass.config_entries.async_setup(todoist_config_entry.entry_id)
        await hass.async_block_till_done()

    assert todoist_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get("todo.synthetic_project") is not None
    assert hass.states.get("calendar.synthetic_project") is not None
    assert entity_registry.async_get("todo.synthetic_project").unique_id == (
        f"{todoist_config_entry.entry_id}-{PROJECT_ID}"
    )
    assert (
        entity_registry.async_get("calendar.synthetic_project").unique_id == PROJECT_ID
    )
