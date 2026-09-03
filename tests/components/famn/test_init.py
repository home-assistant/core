"""Tests for the Famn integration setup."""

from datetime import timedelta
from unittest.mock import AsyncMock

from famn_sdk import ApiError, DeviceTokenResponse, TaskListPaginateResponse
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.famn.const import CONF_REFRESH_TOKEN, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.util import dt as dt_util

from . import setup_integration
from .conftest import SPACE_ID

from tests.common import MockConfigEntry, load_json_object_fixture

pytestmark = [pytest.mark.usefixtures("mock_famn")]


async def test_load_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test loading and unloading a config entry."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_device_info(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that a service device is registered for the paired space."""
    await setup_integration(hass, mock_config_entry)

    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, SPACE_ID), mock_config_entry.entry_id
    )
    assert device_entry is not None
    assert device_entry.name == "Home Assistant"
    assert device_entry.manufacturer == "Famn"


async def test_setup_retries_on_connection_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_tasks_api: AsyncMock
) -> None:
    """Test that setup is retried when Famn is unreachable."""
    mock_tasks_api.get_task_lists_endpoint.side_effect = ApiError(500, "boom")

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_starts_reauth_on_invalid_token(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_tasks_api: AsyncMock
) -> None:
    """Test that an expired device registration triggers a reauth flow."""
    mock_tasks_api.get_task_lists_endpoint.side_effect = ApiError(401, "unauthorized")

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert any(mock_config_entry.async_get_active_flows(hass, {"reauth"}))


async def test_rotated_refresh_token_is_persisted(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_device_api: AsyncMock
) -> None:
    """Test that a rotated refresh token is written back to the config entry."""
    mock_device_api.rotate_device_refresh_token_endpoint.return_value = (
        DeviceTokenResponse(
            access_token="new-access-token",
            refresh_token="new-refresh-token",
            access_token_expires_at=dt_util.utcnow() + timedelta(minutes=10),
        )
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.data[CONF_REFRESH_TOKEN] == "new-refresh-token"


async def test_setup_retries_on_token_rotation_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_device_api: AsyncMock
) -> None:
    """Test that setup is retried when the token cannot be rotated."""
    mock_device_api.rotate_device_refresh_token_endpoint.side_effect = ApiError(
        500, "boom"
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_reauth_on_incomplete_token_response(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_device_api: AsyncMock
) -> None:
    """Test that a token response without tokens triggers a reauth flow."""
    mock_device_api.rotate_device_refresh_token_endpoint.return_value = (
        DeviceTokenResponse(status="revoked")
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert any(mock_config_entry.async_get_active_flows(hass, {"reauth"}))


@pytest.mark.parametrize("status", [401, 403, 409, 410])
async def test_reauth_on_rejected_refresh_token(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device_api: AsyncMock,
    status: int,
) -> None:
    """Test that a revoked device registration triggers a reauth flow."""
    mock_device_api.rotate_device_refresh_token_endpoint.side_effect = ApiError(
        status, "rejected"
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert any(mock_config_entry.async_get_active_flows(hass, {"reauth"}))


async def test_valid_token_is_not_rotated_again(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device_api: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a still-valid access token is not refreshed on every update."""
    freezer.move_to("2026-08-12T12:00:00Z")
    await setup_integration(hass, mock_config_entry)
    assert mock_device_api.rotate_device_refresh_token_endpoint.call_count == 1

    await mock_config_entry.runtime_data.chores.async_refresh()
    assert mock_device_api.rotate_device_refresh_token_endpoint.call_count == 1


async def test_task_list_pagination(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_tasks_api: AsyncMock
) -> None:
    """Test that all pages of chore lists are fetched."""
    page = TaskListPaginateResponse.from_dict(
        load_json_object_fixture("task_lists.json", DOMAIN)
    )
    page.total_pages = 2
    empty = TaskListPaginateResponse(items=[], total_pages=1)
    # Two pages of chore lists, then one (empty) page of todo lists.
    mock_tasks_api.get_task_lists_endpoint.side_effect = [page, page, empty]

    await setup_integration(hass, mock_config_entry)

    assert mock_tasks_api.get_task_lists_endpoint.call_count == 3
