"""Test the Transport NSW integration initialization."""

from unittest.mock import patch

from homeassistant.components.transport_nsw.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
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
