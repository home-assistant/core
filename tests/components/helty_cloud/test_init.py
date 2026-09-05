"""Test the Helty Flow Cloud setup."""

from unittest.mock import AsyncMock

from pyheltycloud import (
    HeltyCloudAuthError,
    HeltyCloudConnectionError,
    HeltyCloudNoDataError,
)
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_setup_and_unload(
    hass: HomeAssistant,
    mock_helty_cloud: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a config entry sets up and tears down cleanly."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_connection_error(
    hass: HomeAssistant,
    mock_helty_cloud: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a cloud error during setup leads to a retry."""
    mock_helty_cloud.get_devices.side_effect = HeltyCloudConnectionError

    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_auth_error_starts_reauth(
    hass: HomeAssistant,
    mock_helty_cloud: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test rejected credentials ask the user to authenticate again."""
    mock_helty_cloud.get_devices.side_effect = HeltyCloudAuthError

    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == "reauth"


@pytest.mark.parametrize("error", [HeltyCloudNoDataError, HeltyCloudConnectionError])
async def test_a_unit_with_nothing_to_read_still_loads(
    hass: HomeAssistant,
    mock_helty_cloud: AsyncMock,
    mock_config_entry: MockConfigEntry,
    error: type[Exception],
) -> None:
    """Test one unreadable unit does not hold back the rest of the account."""
    mock_helty_cloud.get_last_telemetry.side_effect = error

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_expired_session_on_poll_starts_reauth(
    hass: HomeAssistant,
    mock_helty_cloud: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test credentials rejected while reading ask the user to authenticate again."""
    mock_helty_cloud.get_last_telemetry.side_effect = HeltyCloudAuthError

    await setup_integration(hass, mock_config_entry)

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == "reauth"
