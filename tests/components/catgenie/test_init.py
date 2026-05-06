"""Test the CatGenie integration setup."""

from unittest.mock import MagicMock

from catgenie import Credentials
from catgenie.exceptions import CatGenieAPIError, CatGenieAuthenticationError
from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.catgenie.const import DOMAIN
from homeassistant.components.catgenie.coordinator import SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_catgenie_auth: MagicMock,
    mock_catgenie_client: MagicMock,
) -> None:
    """Test successful setup of a config entry."""
    entry = mock_config_entry
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED


async def test_setup_entry_auth_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_catgenie_auth: MagicMock,
    mock_catgenie_client: MagicMock,
) -> None:
    """Test setup fails with auth error."""
    mock_catgenie_auth.refresh.side_effect = CatGenieAuthenticationError("bad refresh")

    entry = mock_config_entry
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_catgenie_auth: MagicMock,
    mock_catgenie_client: MagicMock,
) -> None:
    """Test setup retries on connection error."""
    mock_catgenie_auth.refresh.side_effect = ConnectionError("timeout")

    entry = mock_config_entry
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_catgenie_auth: MagicMock,
    mock_catgenie_client: MagicMock,
) -> None:
    """Test successful unload of a config entry."""
    entry = mock_config_entry
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_entry_device_fetch_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_catgenie_auth: MagicMock,
    mock_catgenie_client: MagicMock,
) -> None:
    """Test setup retries when device fetch fails."""
    mock_catgenie_client.get_devices.side_effect = RuntimeError("API unavailable")

    entry = mock_config_entry
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_coordinator_auth_error_triggers_refresh(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_catgenie_auth: MagicMock,
    mock_catgenie_client: MagicMock,
) -> None:
    """Test coordinator retries with token refresh on auth error."""
    entry = mock_config_entry
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    # Simulate auth error on next scheduled update, then success after refresh
    mock_catgenie_client.get_devices.side_effect = [
        CatGenieAuthenticationError("expired"),
        mock_catgenie_client.get_devices.return_value,
    ]

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_catgenie_auth.refresh.assert_called()

    state = hass.states.get("sensor.catgenie_litter_box_status")
    assert state is not None
    assert state.state == "cleaning"


async def test_coordinator_auth_error_refresh_fails(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_catgenie_auth: MagicMock,
    mock_catgenie_client: MagicMock,
) -> None:
    """Test coordinator raises ConfigEntryAuthFailed when refresh also fails."""
    entry = mock_config_entry
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    # Both get_devices and refresh fail with auth error
    mock_catgenie_client.get_devices.side_effect = CatGenieAuthenticationError(
        "expired"
    )
    mock_catgenie_auth.refresh.side_effect = CatGenieAuthenticationError("bad token")

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0].get("step_id") == "reauth_confirm"


async def test_coordinator_communication_error(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_catgenie_auth: MagicMock,
    mock_catgenie_client: MagicMock,
) -> None:
    """Test coordinator raises UpdateFailed on communication error."""
    entry = mock_config_entry
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    mock_catgenie_client.get_devices.side_effect = RuntimeError("network error")

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.catgenie_litter_box_status")
    assert state is not None
    assert state.state == "unavailable"


async def test_setup_entry_token_rotation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_catgenie_auth: MagicMock,
    mock_catgenie_client: MagicMock,
) -> None:
    """Test that a rotated refresh token is persisted to the config entry."""
    rotated_credentials = Credentials(
        access_token="new-access-token",
        refresh_token="rotated-refresh-token",
        token_expiration=9999999999.0,
        account_id="test-account-id",
        user_id="test-user-id",
        tenant_id="test-tenant-id",
    )
    mock_catgenie_auth.refresh.return_value = rotated_credentials

    entry = mock_config_entry
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.data[CONF_TOKEN] == "rotated-refresh-token"


async def test_coordinator_api_error(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_catgenie_auth: MagicMock,
    mock_catgenie_client: MagicMock,
) -> None:
    """Test coordinator raises UpdateFailed on CatGenieAPIError."""
    entry = mock_config_entry
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    mock_catgenie_client.get_devices.side_effect = CatGenieAPIError("server error")

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.catgenie_litter_box_status")
    assert state is not None
    assert state.state == "unavailable"


async def test_coordinator_empty_device_list(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_catgenie_auth: MagicMock,
    mock_catgenie_client: MagicMock,
) -> None:
    """Test coordinator handles empty device list gracefully."""
    entry = mock_config_entry
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    # Return empty device list
    mock_catgenie_client.get_devices.return_value = []

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.catgenie_litter_box_status")
    assert state is not None
    assert state.state == "unavailable"
