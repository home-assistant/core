"""Test the Powerfox init module."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from powerfox import PowerfoxAuthenticationError, PowerfoxConnectionError
import pytest

from homeassistant.components.powerfox import async_remove_entry, reset_auth_state
from homeassistant.components.powerfox.const import DOMAIN
from homeassistant.components.powerfox.coordinator import PowerfoxAuthState
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_powerfox_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test load and unload entry."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_config_entry_not_ready(
    hass: HomeAssistant,
    mock_powerfox_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Powerfox configuration entry not ready."""
    mock_powerfox_client.all_devices.side_effect = PowerfoxConnectionError
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize("method", ["all_devices", "device"])
async def test_config_entry_auth_failed(
    hass: HomeAssistant,
    mock_powerfox_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    method: str,
) -> None:
    """Test persistent authentication failures trigger reauthentication."""
    getattr(mock_powerfox_client, method).side_effect = PowerfoxAuthenticationError

    # Device failures must also fail the account-level authentication check.
    if method == "device":
        mock_powerfox_client.all_devices.side_effect = PowerfoxAuthenticationError

    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # A single authentication failure must not trigger reauthentication.
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert not hass.config_entries.flow.async_progress()

    # Authentication is still failing after the five-minute grace period.
    freezer.tick(timedelta(seconds=310))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"


async def test_transient_authentication_error_during_setup(
    hass: HomeAssistant,
    mock_powerfox_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test transient authentication errors during setup allow recovery."""
    # Establish that the credentials have worked successfully.
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED

    # Simulate a temporary HTTP 401 during the next setup.
    mock_powerfox_client.all_devices.side_effect = PowerfoxAuthenticationError

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # A previously working entry should retry instead of requesting new credentials.
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert not hass.config_entries.flow.async_progress()

    # The API recovers before the next setup attempt.
    mock_powerfox_client.all_devices.side_effect = None

    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert not hass.config_entries.flow.async_progress()


async def test_transient_authentication_error_during_reload(
    hass: HomeAssistant,
    mock_powerfox_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a previously working entry survives a transient 401 on reload."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # The API temporarily returns HTTP 401 during reload.
    mock_powerfox_client.all_devices.side_effect = PowerfoxAuthenticationError

    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert not hass.config_entries.flow.async_progress()

    # The API recovers before Home Assistant's automatic retry.
    mock_powerfox_client.all_devices.side_effect = None

    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert not hass.config_entries.flow.async_progress()


async def test_reset_auth_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test resetting an existing authentication investigation."""

    state = PowerfoxAuthState()

    state.record_failure(dt_util.utcnow())
    hass.data.setdefault(DOMAIN, {})[mock_config_entry.entry_id] = state

    reset_auth_state(hass, mock_config_entry.entry_id)

    assert state.failure_since is None
    assert hass.data[DOMAIN][mock_config_entry.entry_id] is state


async def test_remove_auth_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test removing authentication state when an entry is deleted."""

    state = PowerfoxAuthState()
    hass.data.setdefault(DOMAIN, {})[mock_config_entry.entry_id] = state

    await async_remove_entry(hass, mock_config_entry)

    assert mock_config_entry.entry_id not in hass.data[DOMAIN]
