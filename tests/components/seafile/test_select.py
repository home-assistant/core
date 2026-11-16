"""Test the Seafile select platform."""

import dataclasses
from unittest.mock import AsyncMock, patch

from aioseafile import SeafileConnectionError, SeafilePermissionError
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.seafile.coordinator import UPDATE_INTERVAL
from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SelectService,
    SelectServiceArgument,
)
from homeassistant.const import STATE_UNAVAILABLE, CommonServiceArgument, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import LIBRARY_ID

HISTORY = "select.documents_history"


@pytest.mark.usefixtures("mock_seafile_client")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all select entities."""
    with patch("homeassistant.components.seafile.PLATFORMS", [Platform.SELECT]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("keep_days", "option"),
    [
        pytest.param(-1, "keep_all", id="keep_all"),
        pytest.param(0, "keep_none", id="keep_none"),
        pytest.param(45, "limited", id="limited"),
    ],
)
async def test_current_option(
    hass: HomeAssistant,
    mock_seafile_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    keep_days: int,
    option: str,
) -> None:
    """Test the history mode follows the days of history the library keeps."""
    mock_seafile_client.get_library_history_limit.return_value = keep_days
    await setup_integration(hass, mock_config_entry)

    assert (state := hass.states.get(HISTORY))
    assert state.state == option


@pytest.mark.parametrize(
    ("keep_days", "option", "new_keep_days"),
    [
        pytest.param(-1, "keep_none", 0, id="keep_none"),
        pytest.param(0, "keep_all", -1, id="keep_all"),
        pytest.param(-1, "limited", 30, id="limited"),
    ],
)
async def test_select_option(
    hass: HomeAssistant,
    mock_seafile_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    keep_days: int,
    option: str,
    new_keep_days: int,
) -> None:
    """Test selecting a history mode sets the days of history to keep."""
    mock_seafile_client.get_library_history_limit.return_value = keep_days
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SelectService.SELECT_OPTION,
        {
            CommonServiceArgument.ENTITY_ID: HISTORY,
            SelectServiceArgument.OPTION: option,
        },
        blocking=True,
    )

    mock_seafile_client.set_library_history_limit.assert_awaited_once_with(
        LIBRARY_ID, new_keep_days
    )
    assert (state := hass.states.get(HISTORY))
    assert state.state == option


async def test_select_limited_keeps_days(
    hass: HomeAssistant,
    mock_seafile_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test selecting a period of history keeps the days the library already has."""
    mock_seafile_client.get_library_history_limit.return_value = 45
    await setup_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SelectService.SELECT_OPTION,
        {
            CommonServiceArgument.ENTITY_ID: HISTORY,
            SelectServiceArgument.OPTION: "limited",
        },
        blocking=True,
    )

    mock_seafile_client.set_library_history_limit.assert_not_awaited()
    assert (state := hass.states.get(HISTORY))
    assert state.state == "limited"


async def test_select_option_error(
    hass: HomeAssistant,
    mock_seafile_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a failed change is raised as a translated error."""
    await setup_integration(hass, mock_config_entry)
    mock_seafile_client.set_library_history_limit.side_effect = SeafileConnectionError

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            SELECT_DOMAIN,
            SelectService.SELECT_OPTION,
            {
                CommonServiceArgument.ENTITY_ID: HISTORY,
                SelectServiceArgument.OPTION: "keep_none",
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "api_error"
    assert (state := hass.states.get(HISTORY))
    assert state.state == "keep_all"


@pytest.mark.parametrize(
    ("permission", "has_select"),
    [
        pytest.param("rw", False, id="read_write"),
        pytest.param("r", False, id="read_only"),
        pytest.param("admin", True, id="admin"),
    ],
)
async def test_shared_library(
    hass: HomeAssistant,
    mock_seafile_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    permission: str,
    has_select: bool,
) -> None:
    """Test a shared library only has a history select when shared as admin."""
    mock_seafile_client.get_libraries.return_value = [
        dataclasses.replace(library, type="srepo", permission=permission)
        for library in mock_seafile_client.get_libraries.return_value
    ]
    await setup_integration(hass, mock_config_entry)

    assert (hass.states.get(HISTORY) is not None) is has_select


async def test_no_select_without_history_setting(
    hass: HomeAssistant,
    mock_seafile_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test there is no history select when the library has no history setting."""
    mock_seafile_client.get_library_history_limit.side_effect = SeafilePermissionError
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(HISTORY) is None
    assert hass.states.get("sensor.documents_size") is not None


async def test_select_unavailable_without_access(
    hass: HomeAssistant,
    mock_seafile_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the select is unavailable when the account loses access to the setting."""
    await setup_integration(hass, mock_config_entry)
    mock_seafile_client.get_library_history_limit.side_effect = SeafilePermissionError

    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (state := hass.states.get(HISTORY))
    assert state.state == STATE_UNAVAILABLE


async def test_select_added_when_shared_as_admin(
    hass: HomeAssistant,
    mock_seafile_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the select is added once the library is shared with the account as admin."""
    libraries = mock_seafile_client.get_libraries.return_value
    mock_seafile_client.get_libraries.return_value = [
        dataclasses.replace(library, type="srepo", permission="rw")
        for library in libraries
    ]
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(HISTORY) is None

    mock_seafile_client.get_libraries.return_value = [
        dataclasses.replace(library, type="srepo", permission="admin")
        for library in libraries
    ]
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (state := hass.states.get(HISTORY))
    assert state.state == "keep_all"
