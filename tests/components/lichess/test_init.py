"""Test the Lichess initialization."""

from datetime import timedelta
from unittest.mock import AsyncMock

from aiolichess.exceptions import AioLichessError, AuthError
from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.lichess.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration


async def test_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_lichess_client: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Lichess device."""
    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "drnykterstein"), mock_config_entry.entry_id
    )
    assert device
    assert device == snapshot


async def test_setup_entry_failed(
    hass: HomeAssistant,
    mock_lichess_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup fails when API raises an error."""
    mock_lichess_client.get_statistics.side_effect = AioLichessError

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_auth_failed(
    hass: HomeAssistant,
    mock_lichess_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an invalid token during setup starts a reauth flow."""
    mock_lichess_client.get_statistics.side_effect = AuthError

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id


async def test_update_auth_failed(
    hass: HomeAssistant,
    mock_lichess_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an invalid token during a scheduled update starts a reauth flow."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    mock_lichess_client.get_statistics.side_effect = AuthError

    freezer.tick(timedelta(hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id
