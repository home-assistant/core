"""Test Autoskope setup and unload."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.autoskope.const import DOMAIN

# Import runtime data model
from homeassistant.components.autoskope.models import (
    AutoskopeRuntimeData,
    CannotConnect,
    InvalidAuth,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

# Remove ConfigEntryNotReady import as we won't catch it directly
# from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest.fixture
def mock_api() -> AsyncMock:
    """Return a mock Autoskope API instance."""
    api = AsyncMock()
    api.authenticate = AsyncMock(return_value=True)
    # Mock get_vehicles needed by coordinator's _async_update_data
    api.get_vehicles = AsyncMock(return_value=[])
    return api


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a mock config entry."""
    # Return the MockConfigEntry directly
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            "username": "test-user",
            "password": "test-pass",
            "host": "https://example.com",
        },
        entry_id="test-entry-id-init",
    )


async def test_async_setup(hass: HomeAssistant) -> None:
    """Test component setup."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()


async def test_async_setup_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: AsyncMock
) -> None:
    """Test successful setup of the config entry."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.autoskope.AutoskopeApi", return_value=mock_api
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    # Check that runtime_data is stored and contains the coordinator
    assert isinstance(mock_config_entry.runtime_data, AutoskopeRuntimeData)
    assert mock_config_entry.runtime_data.coordinator is not None
    # Remove checks for hass.data
    # assert DOMAIN in hass.data
    # assert mock_config_entry.entry_id in hass.data[DOMAIN]
    # assert "coordinator" in hass.data[DOMAIN][mock_config_entry.entry_id]


async def test_async_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: AsyncMock
) -> None:
    """Test successful unload of the config entry."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.autoskope.AutoskopeApi", return_value=mock_api
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data is not None

    # Unload the entry
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    # runtime_data should be cleared on successful unload
    assert not hasattr(mock_config_entry, "runtime_data")
    # Check safely if entry_id is not in the domain data (which might not exist)
    assert mock_config_entry.entry_id not in hass.data.get(DOMAIN, {})


async def test_async_unload_entry_failure(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: AsyncMock
) -> None:
    """Test failure during unload of the config entry."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.autoskope.AutoskopeApi", return_value=mock_api
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data is not None

    # Simulate failure during platform unload by patching the forwarding function
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_unload",
        return_value=False,  # Simulate unload failure for a platform
    ):
        assert not await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Entry should be in FAILED_UNLOAD state if unload fails
    assert mock_config_entry.state is ConfigEntryState.FAILED_UNLOAD
    # runtime_data might still exist if unload failed partially
    assert mock_config_entry.runtime_data is not None
    # Remove check for hass.data
    # assert mock_config_entry.entry_id in hass.data[DOMAIN]


async def test_setup_entry_authentication_fails(
    hass: HomeAssistant, mock_config_entry, mock_api: AsyncMock
) -> None:
    """Test entry setup failing due to authentication issues."""
    mock_config_entry.add_to_hass(hass)
    # Configure the mock API to raise InvalidAuth during coordinator update
    mock_api.get_vehicles.side_effect = InvalidAuth("Bad credentials")

    with patch(
        "homeassistant.components.autoskope.AutoskopeApi", return_value=mock_api
    ):
        # Setup should fail and raise ConfigEntryAuthFailed, resulting in SETUP_ERROR state
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Check that the entry state reflects the authentication error
    assert mock_config_entry.state == ConfigEntryState.SETUP_ERROR


async def test_setup_entry_cannot_connect_exception(
    hass: HomeAssistant, mock_config_entry, mock_api: AsyncMock
) -> None:
    """Test entry setup failing due to CannotConnect exception."""
    mock_config_entry.add_to_hass(hass)
    # Configure the mock API to raise CannotConnect during coordinator update
    mock_api.get_vehicles.side_effect = CannotConnect("Connection refused")

    with patch(
        "homeassistant.components.autoskope.AutoskopeApi", return_value=mock_api
    ):
        # Setup should fail because coordinator raises UpdateFailed,
        # which is caught by first_refresh and raises ConfigEntryNotReady,
        # which is caught by async_setup, returning False.
        result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
        assert not result
        await hass.async_block_till_done()

    # Check that the entry state reflects the need for retry
    assert mock_config_entry.state == ConfigEntryState.SETUP_RETRY


async def test_setup_entry_generic_api_exception(
    hass: HomeAssistant, mock_config_entry, mock_api: AsyncMock
) -> None:
    """Test entry setup failing due to generic API exceptions during coordinator update."""
    mock_config_entry.add_to_hass(hass)
    # Configure the mock API to raise a generic Exception during coordinator update
    mock_api.get_vehicles.side_effect = Exception("Unexpected API Error")

    with patch(
        "homeassistant.components.autoskope.AutoskopeApi", return_value=mock_api
    ):
        # Setup should fail because coordinator raises UpdateFailed,
        # which is caught by first_refresh and raises ConfigEntryNotReady,
        # which is caught by async_setup, returning False.
        result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
        assert not result
        await hass.async_block_till_done()

    # Check that the entry state reflects the setup retry state
    assert mock_config_entry.state == ConfigEntryState.SETUP_RETRY


async def test_reload_entry(
    hass: HomeAssistant, mock_config_entry, mock_api: AsyncMock
) -> None:
    """Test reloading the config entry."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.autoskope.AutoskopeApi", return_value=mock_api
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state == ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data is not None
    # Remove check for hass.data
    # assert mock_config_entry.entry_id in hass.data[DOMAIN]

    # Store original runtime_data object id to check if it changes after reload
    original_runtime_data_id = id(mock_config_entry.runtime_data)

    with (
        patch("homeassistant.components.autoskope.AutoskopeApi", return_value=mock_api),
        # Ensure listeners are called during reload test if needed by platforms
        # patch("homeassistant.config_entries.ConfigEntries.async_update_entry"),
    ):
        assert await hass.config_entries.async_reload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state == ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data is not None
    # Check that runtime_data object was recreated
    assert id(mock_config_entry.runtime_data) != original_runtime_data_id
    # Remove check for hass.data
    # assert mock_config_entry.entry_id in hass.data[DOMAIN]


async def test_setup_entry_platform_setup_fails(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_api: AsyncMock
) -> None:
    """Test entry setup when a platform setup fails."""
    mock_config_entry.add_to_hass(hass)

    # Patch API instantiation and platform setup forwarding
    with (
        patch("homeassistant.components.autoskope.AutoskopeApi", return_value=mock_api),
        patch(  # Simulate platform setup failure
            "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
            side_effect=Exception("Platform setup failed"),
        ),
    ):
        # Setup should fail
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Check the entry state - platform setup failure usually results in SETUP_ERROR
    assert mock_config_entry.state == ConfigEntryState.SETUP_ERROR
    # runtime_data might have been created before platform setup failed
    # assert not hasattr(mock_config_entry, "runtime_data") # This might be True or False
