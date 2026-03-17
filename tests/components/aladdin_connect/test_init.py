"""Tests for the Aladdin Connect integration."""

import http
from unittest.mock import AsyncMock, patch

from aiohttp import ClientConnectionError, RequestInfo
from aiohttp.client_exceptions import ClientResponseError
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.aladdin_connect import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import init_integration

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_setup_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test a successful setup entry."""
    await init_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test a successful unload entry."""
    await init_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("status", "expected_state"),
    [
        (http.HTTPStatus.UNAUTHORIZED, ConfigEntryState.SETUP_ERROR),
        (http.HTTPStatus.INTERNAL_SERVER_ERROR, ConfigEntryState.SETUP_RETRY),
    ],
    ids=["auth_failure", "server_error"],
)
async def test_setup_entry_token_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    status: http.HTTPStatus,
    expected_state: ConfigEntryState,
) -> None:
    """Test setup entry fails when token validation fails."""
    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        side_effect=ClientResponseError(
            RequestInfo("", "POST", {}, ""), None, status=status
        ),
    ):
        await init_integration(hass, mock_config_entry)

    assert mock_config_entry.state is expected_state


async def test_setup_entry_token_connection_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup entry retries when token validation has a connection error."""
    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        side_effect=ClientConnectionError(),
    ):
        await init_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    ("status", "expected_state"),
    [
        (http.HTTPStatus.UNAUTHORIZED, ConfigEntryState.SETUP_ERROR),
        (http.HTTPStatus.INTERNAL_SERVER_ERROR, ConfigEntryState.SETUP_RETRY),
    ],
    ids=["auth_failure", "server_error"],
)
async def test_setup_entry_api_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aladdin_connect_api: AsyncMock,
    status: http.HTTPStatus,
    expected_state: ConfigEntryState,
) -> None:
    """Test setup entry fails when API call fails."""
    mock_aladdin_connect_api.get_doors.side_effect = ClientResponseError(
        RequestInfo("", "GET", {}, ""), None, status=status
    )
    await init_integration(hass, mock_config_entry)
    assert mock_config_entry.state is expected_state


async def test_setup_entry_api_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aladdin_connect_api: AsyncMock,
) -> None:
    """Test setup entry retries when API has a connection error."""
    mock_aladdin_connect_api.get_doors.side_effect = ClientConnectionError()
    await init_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_remove_stale_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test stale devices are removed on setup."""
    mock_config_entry.add_to_hass(hass)

    # Create a device that the API will no longer return
    device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "stale_device_id")},
    )
    device_entries = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert len(device_entries) == 1

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # The stale device should be gone, only the real door remains
    device_entries = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert len(device_entries) == 1
    assert device_entries[0].identifiers == {(DOMAIN, "test_device_id-1")}


async def test_dynamic_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_aladdin_connect_api: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test new devices are automatically discovered on coordinator refresh."""
    await init_integration(hass, mock_config_entry)

    # Initially one door -> one cover entity + one sensor entity
    device_entries = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert len(device_entries) == 1
    assert hass.states.get("cover.test_door") is not None

    # Simulate a new door appearing on the API
    mock_door_2 = AsyncMock()
    mock_door_2.device_id = "test_device_id_2"
    mock_door_2.door_number = 1
    mock_door_2.name = "Test Door 2"
    mock_door_2.status = "open"
    mock_door_2.link_status = "connected"
    mock_door_2.battery_level = 80
    mock_door_2.unique_id = f"{mock_door_2.device_id}-{mock_door_2.door_number}"

    existing_door = mock_aladdin_connect_api.get_doors.return_value[0]
    mock_aladdin_connect_api.get_doors.return_value = [existing_door, mock_door_2]

    # Trigger coordinator refresh
    freezer.tick(15)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Now two devices should exist
    device_entries = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert len(device_entries) == 2

    # New cover entity should exist
    assert hass.states.get("cover.test_door_2") is not None
