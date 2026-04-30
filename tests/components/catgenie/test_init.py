"""Test the CatGenie integration setup."""

from unittest.mock import MagicMock

from catgenie import Device
from catgenie.auth import CatGenieAuthenticationError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import MOCK_DEVICE_DATA, MOCK_ENTRY_DATA

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant,
    mock_catgenie_auth_init: MagicMock,
    mock_catgenie_client: MagicMock,
) -> None:
    """Test successful setup of a config entry."""
    entry = MockConfigEntry(
        domain="catgenie",
        data=MOCK_ENTRY_DATA,
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED


async def test_setup_entry_auth_error(
    hass: HomeAssistant,
    mock_catgenie_auth_init: MagicMock,
    mock_catgenie_client: MagicMock,
) -> None:
    """Test setup fails with auth error."""
    mock_catgenie_auth_init.refresh.side_effect = CatGenieAuthenticationError(
        "bad refresh"
    )

    entry = MockConfigEntry(
        domain="catgenie",
        data=MOCK_ENTRY_DATA,
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_connection_error(
    hass: HomeAssistant,
    mock_catgenie_auth_init: MagicMock,
    mock_catgenie_client: MagicMock,
) -> None:
    """Test setup retries on connection error."""
    mock_catgenie_auth_init.refresh.side_effect = ConnectionError("timeout")

    entry = MockConfigEntry(
        domain="catgenie",
        data=MOCK_ENTRY_DATA,
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant,
    mock_catgenie_auth_init: MagicMock,
    mock_catgenie_client: MagicMock,
) -> None:
    """Test successful unload of a config entry."""
    entry = MockConfigEntry(
        domain="catgenie",
        data=MOCK_ENTRY_DATA,
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_entry_device_fetch_error(
    hass: HomeAssistant,
    mock_catgenie_auth_init: MagicMock,
    mock_catgenie_client: MagicMock,
) -> None:
    """Test setup retries when device fetch fails."""
    mock_catgenie_client.get_devices.side_effect = RuntimeError("API unavailable")

    entry = MockConfigEntry(
        domain="catgenie",
        data=MOCK_ENTRY_DATA,
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_coordinator_auth_error_triggers_refresh(
    hass: HomeAssistant,
    mock_catgenie_auth_init: MagicMock,
    mock_catgenie_client: MagicMock,
) -> None:
    """Test coordinator retries with token refresh on auth error."""
    entry = MockConfigEntry(
        domain="catgenie",
        data=MOCK_ENTRY_DATA,
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    # Simulate auth error on next update, then success after refresh
    devices = [Device.model_validate(MOCK_DEVICE_DATA)]
    mock_catgenie_client.get_devices.side_effect = [
        CatGenieAuthenticationError("expired"),
        devices,
    ]

    coordinator = entry.runtime_data.coordinator
    await coordinator.async_refresh()

    assert coordinator.last_update_success
    mock_catgenie_auth_init.refresh.assert_called()


async def test_coordinator_auth_error_refresh_fails(
    hass: HomeAssistant,
    mock_catgenie_auth_init: MagicMock,
    mock_catgenie_client: MagicMock,
) -> None:
    """Test coordinator raises ConfigEntryAuthFailed when refresh also fails."""
    entry = MockConfigEntry(
        domain="catgenie",
        data=MOCK_ENTRY_DATA,
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    # Both get_devices and refresh fail with auth error
    mock_catgenie_client.get_devices.side_effect = CatGenieAuthenticationError(
        "expired"
    )
    mock_catgenie_auth_init.refresh.side_effect = CatGenieAuthenticationError(
        "bad token"
    )

    coordinator = entry.runtime_data.coordinator
    await coordinator.async_refresh()

    assert not coordinator.last_update_success


async def test_coordinator_communication_error(
    hass: HomeAssistant,
    mock_catgenie_auth_init: MagicMock,
    mock_catgenie_client: MagicMock,
) -> None:
    """Test coordinator raises UpdateFailed on communication error."""
    entry = MockConfigEntry(
        domain="catgenie",
        data=MOCK_ENTRY_DATA,
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    mock_catgenie_client.get_devices.side_effect = RuntimeError("network error")

    coordinator = entry.runtime_data.coordinator
    await coordinator.async_refresh()

    assert not coordinator.last_update_success


async def test_coordinator_empty_device_list(
    hass: HomeAssistant,
    mock_catgenie_auth_init: MagicMock,
    mock_catgenie_client: MagicMock,
) -> None:
    """Test coordinator handles empty device list gracefully."""
    entry = MockConfigEntry(
        domain="catgenie",
        data=MOCK_ENTRY_DATA,
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    # Return empty device list
    mock_catgenie_client.get_devices.return_value = []

    coordinator = entry.runtime_data.coordinator
    await coordinator.async_refresh()

    assert coordinator.last_update_success
    assert coordinator.data == {}
