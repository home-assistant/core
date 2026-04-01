"""Tests for the Huum __init__."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from huum.exceptions import Forbidden, NotAuthenticated, RequestError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.huum.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.usefixtures("init_integration")
async def test_loading_and_unloading_config_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test loading and unloading a config entry."""
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    "exception",
    [
        Forbidden("Forbidden"),
        NotAuthenticated("Not authenticated"),
    ],
)
async def test_setup_entry_auth_error(
    hass: HomeAssistant,
    mock_huum_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
) -> None:
    """Test setup triggers reauth on auth errors."""
    mock_config_entry.add_to_hass(hass)
    mock_huum_client.status.side_effect = exception

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH


async def test_setup_entry_connection_error(
    hass: HomeAssistant,
    mock_huum_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup retries on connection error."""
    mock_config_entry.add_to_hass(hass)
    mock_huum_client.status.side_effect = RequestError("Request error")

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert hass.config_entries.flow.async_progress_by_handler(DOMAIN) == []


@pytest.mark.usefixtures("init_integration")
async def test_device_entry(
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test device registry entry."""
    assert (
        device_entry := device_registry.async_get_device(
            identifiers={(DOMAIN, mock_config_entry.entry_id)}
        )
    )
    assert device_entry == snapshot


@pytest.mark.parametrize(
    "side_effect",
    [
        Forbidden("Forbidden"),
        NotAuthenticated("Not authenticated"),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_coordinator_update_auth_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_huum_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
    side_effect: Exception,
) -> None:
    """Test that an auth error during coordinator refresh triggers reauth."""
    mock_huum_client.status.side_effect = side_effect

    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
