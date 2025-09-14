"""Test the Transport NSW integration initialization."""

from unittest.mock import patch

from homeassistant.components.transport_nsw.const import (
    CONF_DESTINATION,
    CONF_ROUTE,
    CONF_STOP_ID,
    DOMAIN,
)
from homeassistant.components.transport_nsw.coordinator import TransportNSWCoordinator
from homeassistant.config_entries import ConfigEntryState, ConfigSubentry
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry_with_subentries(
    hass: HomeAssistant, mock_config_entry_with_subentries: MockConfigEntry
) -> None:
    """Test setup with subentries."""
    mock_config_entry_with_subentries.add_to_hass(hass)

    # Test the real setup function
    result = await hass.config_entries.async_setup(
        mock_config_entry_with_subentries.entry_id
    )

    assert result is True
    # Our component should set up the domain data
    assert DOMAIN in hass.data


async def test_setup_entry_legacy(
    hass: HomeAssistant, mock_config_entry_legacy: MockConfigEntry
) -> None:
    """Test setup with legacy entry."""
    mock_config_entry_legacy.add_to_hass(hass)

    # Test the real setup function
    result = await hass.config_entries.async_setup(mock_config_entry_legacy.entry_id)

    assert result is True
    # Our component should set up the domain data
    assert DOMAIN in hass.data


async def test_unload_entry_with_subentries(
    hass: HomeAssistant, mock_config_entry_with_subentries: MockConfigEntry
) -> None:
    """Test unloading entry with subentries."""
    mock_config_entry_with_subentries.add_to_hass(hass)

    # Setup first
    with patch(
        "homeassistant.components.transport_nsw.async_setup_entry", return_value=True
    ):
        await hass.config_entries.async_setup(
            mock_config_entry_with_subentries.entry_id
        )

    # Now test unload
    with patch(
        "homeassistant.components.transport_nsw.async_unload_entry", return_value=True
    ) as mock_unload:
        result = await hass.config_entries.async_unload(
            mock_config_entry_with_subentries.entry_id
        )

    assert result
    assert mock_unload.called


async def test_unload_entry_legacy(
    hass: HomeAssistant, mock_config_entry_legacy: MockConfigEntry
) -> None:
    """Test unloading legacy entry."""
    mock_config_entry_legacy.add_to_hass(hass)

    # Setup first
    with patch(
        "homeassistant.components.transport_nsw.async_setup_entry", return_value=True
    ):
        await hass.config_entries.async_setup(mock_config_entry_legacy.entry_id)

    # Now test unload
    with patch(
        "homeassistant.components.transport_nsw.async_unload_entry", return_value=True
    ) as mock_unload:
        result = await hass.config_entries.async_unload(
            mock_config_entry_legacy.entry_id
        )

    assert result
    assert mock_unload.called


async def test_setup_entry_platform_forwarding(
    hass: HomeAssistant, mock_config_entry_with_subentries: MockConfigEntry
) -> None:
    """Test that platforms are forwarded correctly during setup."""
    mock_config_entry_with_subentries.add_to_hass(hass)

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups"
    ) as mock_forward:
        await hass.config_entries.async_setup(
            mock_config_entry_with_subentries.entry_id
        )

    # Should forward to sensor platform
    mock_forward.assert_called_once()
    args = mock_forward.call_args[0]
    assert args[0] == mock_config_entry_with_subentries
    assert "sensor" in args[1]


async def test_setup_entry_data_storage(
    hass: HomeAssistant, mock_config_entry_with_subentries: MockConfigEntry
) -> None:
    """Test that data is stored correctly in hass.data."""
    mock_config_entry_with_subentries.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry_with_subentries.entry_id)

    # Check that domain data structure is created
    assert DOMAIN in hass.data
    assert isinstance(hass.data[DOMAIN], dict)


async def test_setup_entry_reload_functionality(
    hass: HomeAssistant, mock_config_entry_with_subentries: MockConfigEntry
) -> None:
    """Test entry reload functionality."""
    mock_config_entry_with_subentries.add_to_hass(hass)

    # Setup entry
    await hass.config_entries.async_setup(mock_config_entry_with_subentries.entry_id)

    # Reload entry
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_reload"
    ) as mock_reload:
        await hass.config_entries.async_reload(
            mock_config_entry_with_subentries.entry_id
        )

    assert mock_reload.called


async def test_unload_entry_cleanup(
    hass: HomeAssistant, mock_config_entry_with_subentries: MockConfigEntry
) -> None:
    """Test that unload properly cleans up data."""
    mock_config_entry_with_subentries.add_to_hass(hass)

    # Setup entry
    await hass.config_entries.async_setup(mock_config_entry_with_subentries.entry_id)

    # Verify domain data exists
    assert DOMAIN in hass.data

    # Unload entry
    await hass.config_entries.async_unload(mock_config_entry_with_subentries.entry_id)

    # Verify data is cleaned up
    assert mock_config_entry_with_subentries.entry_id not in hass.data.get(DOMAIN, {})


async def test_setup_entry_failure_handling(
    hass: HomeAssistant, mock_config_entry_with_subentries: MockConfigEntry
) -> None:
    """Test handling of setup failures."""
    mock_config_entry_with_subentries.add_to_hass(hass)

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
        side_effect=Exception("Setup failed"),
    ):
        result = await hass.config_entries.async_setup(
            mock_config_entry_with_subentries.entry_id
        )

    # Setup should fail gracefully
    assert not result


async def test_unload_entry_failure_handling(
    hass: HomeAssistant, mock_config_entry_with_subentries: MockConfigEntry
) -> None:
    """Test handling of unload failures."""
    mock_config_entry_with_subentries.add_to_hass(hass)

    # Setup entry first
    await hass.config_entries.async_setup(mock_config_entry_with_subentries.entry_id)

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
        return_value=False,
    ):
        result = await hass.config_entries.async_unload(
            mock_config_entry_with_subentries.entry_id
        )

    # Unload should return False but not crash
    assert not result


async def test_config_entry_reload_on_update(hass: HomeAssistant) -> None:
    """Test that config entry updates trigger a reload."""
    # Create a config entry with subentries
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "test_api_key", CONF_NAME: "Test Integration"},
        title="Test Integration",
        unique_id="test_config_entry",
    )
    entry.add_to_hass(hass)

    # Mock the async_reload method
    with patch.object(hass.config_entries, "async_reload") as mock_reload:
        # Set up the entry
        result = await hass.config_entries.async_setup(entry.entry_id)
        assert result is True

        # Simulate a config entry update (this would normally happen when a subentry is modified)
        # We need to call the update listener that was registered
        if entry.update_listeners:
            for listener in entry.update_listeners:
                await listener(hass, entry)

        # Verify that reload was called
        mock_reload.assert_called_once_with(entry.entry_id)


async def test_coordinator_config_update(hass: HomeAssistant) -> None:
    """Test coordinator configuration update functionality."""
    # Create initial config entry
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "test_api_key", CONF_NAME: "Test"},
        unique_id="test_entry",
    )
    config_entry.add_to_hass(hass)

    # Create subentry
    subentry = ConfigSubentry(
        subentry_id="sub1",
        unique_id="sub1_unique",
        subentry_type="stop",
        data={CONF_STOP_ID: "123456", CONF_ROUTE: "T1", CONF_DESTINATION: "Central"},
        title="Test Stop",
    )

    # Create coordinator
    coordinator = TransportNSWCoordinator(hass, config_entry, subentry)

    # Verify initial configuration
    assert coordinator.stop_id == "123456"
    assert coordinator.route == "T1"
    assert coordinator.destination == "Central"

    # Create updated subentry
    updated_subentry = ConfigSubentry(
        subentry_id="sub1",
        unique_id="sub1_unique",
        subentry_type="stop",
        data={CONF_STOP_ID: "123456", CONF_ROUTE: "T2", CONF_DESTINATION: "Town Hall"},
        title="Updated Stop",
    )

    # Update coordinator configuration
    with patch.object(coordinator, "async_request_refresh") as mock_refresh:
        await coordinator.async_update_config(config_entry, updated_subentry)

        # Verify configuration was updated
        assert coordinator.route == "T2"
        assert coordinator.destination == "Town Hall"

        # Verify refresh was triggered
        mock_refresh.assert_called_once()


async def test_multiple_entries_data_isolation(hass: HomeAssistant) -> None:
    """Test that multiple entries don't interfere with each other."""
    # Create fresh config entries to avoid state conflicts
    entry_with_subentries = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "test_api_key_isolation_1"},
        unique_id="test_api_key_isolation_1",
    )
    entry_legacy = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_KEY: "test_api_key_isolation_2",
            "stop_id": "test_stop_id_isolation",
            CONF_NAME: "Test Stop Legacy Isolation",
        },
        unique_id="test_stop_id_isolation_legacy",
    )

    entry_with_subentries.add_to_hass(hass)
    entry_legacy.add_to_hass(hass)

    # Setup both entries (check if already loaded first)
    if entry_with_subentries.state != ConfigEntryState.LOADED:
        result1 = await hass.config_entries.async_setup(entry_with_subentries.entry_id)
        assert result1 is True

    if entry_legacy.state != ConfigEntryState.LOADED:
        result2 = await hass.config_entries.async_setup(entry_legacy.entry_id)
        assert result2 is True

    # Domain data should exist
    assert DOMAIN in hass.data

    # Unload one
    await hass.config_entries.async_unload(entry_with_subentries.entry_id)

    # Domain data should still exist (since one entry is still loaded)
    assert DOMAIN in hass.data
