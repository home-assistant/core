"""Test the Powerfox data update coordinators."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from powerfox import PowerfoxAuthenticationError, PowerfoxConnectionError
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.parametrize("method", ["device", "report"])
async def test_transient_authentication_error(
    hass: HomeAssistant,
    mock_powerfox_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    method: str,
) -> None:
    """Test transient authentication errors do not trigger reauthentication."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    api_method = getattr(mock_powerfox_client, method)
    api_method.side_effect = PowerfoxAuthenticationError

    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert not hass.config_entries.flow.async_progress()


@pytest.mark.parametrize("method", ["device", "report"])
async def test_persistent_authentication_error(
    hass: HomeAssistant,
    mock_powerfox_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    method: str,
) -> None:
    """Test persistent authentication errors trigger reauthentication."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Simulate an account-wide authentication failure.
    mock_powerfox_client.device.side_effect = PowerfoxAuthenticationError
    mock_powerfox_client.report.side_effect = PowerfoxAuthenticationError
    mock_powerfox_client.all_devices.side_effect = PowerfoxAuthenticationError

    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_powerfox_client.all_devices.call_count == 1
    assert not hass.config_entries.flow.async_progress()

    freezer.tick(timedelta(seconds=310))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"


@pytest.mark.parametrize("method", ["device", "report"])
async def test_authentication_recheck_succeeds(
    hass: HomeAssistant,
    mock_powerfox_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    method: str,
) -> None:
    """Test successful credential recheck prevents reauthentication."""
    await setup_integration(hass, mock_config_entry)

    api_method = getattr(mock_powerfox_client, method)
    api_method.side_effect = PowerfoxAuthenticationError

    # Simulate an account-wide outage, including the other devices.
    if method == "report":
        mock_powerfox_client.device.side_effect = PowerfoxAuthenticationError
    else:
        mock_powerfox_client.report.side_effect = PowerfoxAuthenticationError

    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    freezer.tick(timedelta(seconds=310))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_powerfox_client.all_devices.call_count >= 2
    assert not hass.config_entries.flow.async_progress()


@pytest.mark.parametrize("method", ["device", "report"])
async def test_authentication_failure_timer_resets(
    hass: HomeAssistant,
    mock_powerfox_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    method: str,
) -> None:
    """Test successful updates reset the authentication failure timer."""
    await setup_integration(hass, mock_config_entry)

    api_method = getattr(mock_powerfox_client, method)

    # First authentication failure.
    api_method.side_effect = PowerfoxAuthenticationError
    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Successful update resets the timer.
    api_method.side_effect = None
    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # A new authentication failure starts a fresh timer.
    api_method.side_effect = PowerfoxAuthenticationError
    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Only 50 seconds have passed since the new failure.
    freezer.tick(timedelta(seconds=50))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_powerfox_client.all_devices.call_count == 1
    assert not hass.config_entries.flow.async_progress()


@pytest.mark.parametrize("method", ["device", "report"])
async def test_authentication_recheck_connection_error(
    hass: HomeAssistant,
    mock_powerfox_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    method: str,
) -> None:
    """Test a connection error during credential recheck does not trigger reauth."""
    await setup_integration(hass, mock_config_entry)

    api_method = getattr(mock_powerfox_client, method)
    api_method.side_effect = PowerfoxAuthenticationError

    # Simulate an account-wide outage, including the other devices.
    if method == "report":
        mock_powerfox_client.device.side_effect = PowerfoxAuthenticationError
    else:
        mock_powerfox_client.report.side_effect = PowerfoxAuthenticationError
    mock_powerfox_client.all_devices.side_effect = PowerfoxConnectionError

    # First authentication failure starts the grace period.
    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_powerfox_client.all_devices.call_count == 1
    assert not hass.config_entries.flow.async_progress()

    # After five minutes, credential verification encounters a connection error.
    freezer.tick(timedelta(seconds=310))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_powerfox_client.all_devices.call_count >= 2
    assert not hass.config_entries.flow.async_progress()


async def test_coordinators_share_authentication_state(
    hass: HomeAssistant,
    mock_powerfox_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test all coordinators share one account authentication state."""
    await setup_integration(hass, mock_config_entry)

    coordinators = mock_config_entry.runtime_data

    assert len(coordinators) == 4

    # Every device belongs to the same Powerfox account.
    auth_states = [coordinator.auth_state for coordinator in coordinators]

    assert all(state is auth_states[0] for state in auth_states)


@pytest.mark.parametrize("method", ["device", "report"])
async def test_authentication_investigation_grace_period(
    hass: HomeAssistant,
    mock_powerfox_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    method: str,
) -> None:
    """Test repeated HTTP 401 responses remain under investigation for 5 minutes."""
    await setup_integration(hass, mock_config_entry)

    api_method = getattr(mock_powerfox_client, method)
    api_method.side_effect = PowerfoxAuthenticationError
    mock_powerfox_client.all_devices.side_effect = PowerfoxAuthenticationError

    # First HTTP 401 starts the investigation.
    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert not hass.config_entries.flow.async_progress()

    # Repeated HTTP 401 after 70 seconds must not trigger reauthentication.
    freezer.tick(timedelta(seconds=70))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert not hass.config_entries.flow.async_progress()


async def test_authentication_investigation_resets_on_success(
    hass: HomeAssistant,
    mock_powerfox_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a successful request resets the shared authentication investigation."""
    await setup_integration(hass, mock_config_entry)

    coordinators = mock_config_entry.runtime_data
    auth_state = coordinators[0].auth_state

    original_device_side_effect = mock_powerfox_client.device.side_effect
    mock_powerfox_client.device.side_effect = PowerfoxAuthenticationError

    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert auth_state.failure_since is not None

    # Restore the original device responses from the test fixture.
    mock_powerfox_client.device.side_effect = original_device_side_effect

    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert auth_state.failure_since is None
    assert not hass.config_entries.flow.async_progress()


async def test_single_device_authentication_failure_does_not_reauthenticate(
    hass: HomeAssistant,
    mock_powerfox_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a failing report does not invalidate working account credentials."""
    await setup_integration(hass, mock_config_entry)

    # Only the gas meter fails; the other three devices remain available.
    mock_powerfox_client.report.side_effect = PowerfoxAuthenticationError
    mock_powerfox_client.all_devices.side_effect = PowerfoxAuthenticationError

    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert not hass.config_entries.flow.async_progress()

    # More than five minutes later, working devices still prevent reauth.
    freezer.tick(timedelta(seconds=310))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert not hass.config_entries.flow.async_progress()
