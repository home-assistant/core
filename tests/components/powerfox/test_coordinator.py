"""Test the Powerfox data update coordinators."""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from powerfox import PowerfoxAuthenticationError, PowerfoxConnectionError
import pytest

from homeassistant.components.powerfox.const import DOMAIN
from homeassistant.components.powerfox.coordinator import PowerfoxAuthState
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util import dt as dt_util

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_stale_authentication_verification_does_not_reauthenticate(
    hass: HomeAssistant,
    mock_powerfox_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a delayed verification cannot override a successful update."""

    await setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data[0]
    auth_state = coordinator.auth_state

    mock_powerfox_client.device.side_effect = PowerfoxAuthenticationError

    # Establish an existing authentication failure interval.
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()

    assert auth_state.failure_since is not None

    # Advance beyond the authentication grace period.
    freezer.tick(timedelta(seconds=310))

    # Simulate another coordinator recovering while verification is pending.
    async def delayed_authentication_error(*args, **kwargs):
        auth_state.record_success()
        raise PowerfoxAuthenticationError

    mock_powerfox_client.all_devices.side_effect = delayed_authentication_error

    # A stale verification must not trigger reauthentication.
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()

    assert auth_state.failure_since is None
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert not hass.config_entries.flow.async_progress()


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
    """Test persistent authentication errors remain retryable."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

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

    # Even a prolonged HTTP 401 must not force reauthentication.
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert not hass.config_entries.flow.async_progress()


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


async def test_concurrent_authentication_verification_is_serialized(
    hass: HomeAssistant,
    mock_powerfox_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test concurrent coordinators perform only one credential verification."""
    await setup_integration(hass, mock_config_entry)

    coordinators = mock_config_entry.runtime_data
    first, second = coordinators[:2]
    auth_state = first.auth_state

    # Avoid waiting for the actual five-minute grace period.
    auth_state.failure_since = dt_util.utcnow() - timedelta(minutes=6)

    started = asyncio.Event()
    release = asyncio.Event()

    async def delayed_verification() -> None:
        started.set()
        await release.wait()
        raise PowerfoxConnectionError

    mock_powerfox_client.all_devices.side_effect = delayed_verification

    first._async_fetch_data = AsyncMock(side_effect=PowerfoxAuthenticationError)
    second._async_fetch_data = AsyncMock(side_effect=PowerfoxAuthenticationError)

    initial_calls = mock_powerfox_client.all_devices.call_count

    first_task = asyncio.create_task(first._async_update_data())
    await started.wait()

    second_task = asyncio.create_task(second._async_update_data())

    try:
        await asyncio.sleep(0)

        # The second coordinator must wait rather than call the API.
        assert mock_powerfox_client.all_devices.call_count == initial_calls + 1

    finally:
        release.set()
        results = await asyncio.gather(first_task, second_task, return_exceptions=True)

    assert all(isinstance(result, UpdateFailed) for result in results)
    assert mock_powerfox_client.all_devices.call_count == initial_calls + 1
    assert auth_state.last_verification is not None


async def test_successful_verification_preserves_authentication_failure(
    hass: HomeAssistant,
    mock_powerfox_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Successful account verification must not reset a failing device."""
    await setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data[0]
    auth_state = coordinator.auth_state

    # Simulate a persistent authentication failure beyond the grace period.
    failure_since = dt_util.utcnow() - timedelta(minutes=6)
    auth_state.failure_since = failure_since
    auth_state.last_verification = None

    # Account verification succeeds, but the device still returns HTTP 401.
    mock_powerfox_client.all_devices.reset_mock()
    mock_powerfox_client.all_devices.side_effect = None

    coordinator._async_fetch_data = AsyncMock(side_effect=PowerfoxAuthenticationError)

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()

    mock_powerfox_client.all_devices.assert_awaited_once()

    # The original failure timestamp must survive account verification.
    assert auth_state.failure_since == failure_since
    assert auth_state.last_verification is not None

    # Another device failure within one minute must not verify again.
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()

    mock_powerfox_client.all_devices.assert_awaited_once()
    assert auth_state.failure_since == failure_since


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
    original_report_side_effect = mock_powerfox_client.report.side_effect
    mock_powerfox_client.device.side_effect = PowerfoxAuthenticationError
    mock_powerfox_client.report.side_effect = PowerfoxAuthenticationError

    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert auth_state.failure_since is not None

    # Restore the original device responses from the test fixture.
    mock_powerfox_client.device.side_effect = original_device_side_effect
    mock_powerfox_client.report.side_effect = original_report_side_effect

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


async def test_persistent_auth_failure_threshold() -> None:
    """Test the shared authentication state reaches the 30-minute threshold."""
    state = PowerfoxAuthState()
    start = datetime(2026, 1, 1, tzinfo=UTC)

    state.record_failure(start)

    assert not state.has_persistent_failure(start + timedelta(minutes=29))
    assert not state.has_persistent_failure(start + timedelta(minutes=29, seconds=59))
    assert state.has_persistent_failure(start + timedelta(minutes=30))

    state.record_success()

    assert not state.has_persistent_failure(start + timedelta(minutes=31))


async def test_persistent_auth_failure_repair_issue(
    hass: HomeAssistant,
    mock_powerfox_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a persistent authentication error creates and clears a repair issue."""
    await setup_integration(hass, mock_config_entry)

    coordinator = mock_config_entry.runtime_data[0]
    issue_id = f"persistent_auth_failure_{mock_config_entry.entry_id}"

    mock_powerfox_client.device.side_effect = PowerfoxAuthenticationError

    # Start the authentication failure interval.
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()

    # No repair issue before the 30-minute threshold.
    freezer.tick(timedelta(minutes=29, seconds=59))

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()

    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is None

    # The next authentication error reaches the threshold.
    freezer.tick(timedelta(seconds=1))

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()

    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is not None

    # Restore the original successful device response.
    mock_powerfox_client.device.side_effect = None

    await coordinator._async_update_data()

    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is None
    assert coordinator.auth_state.failure_since is None
