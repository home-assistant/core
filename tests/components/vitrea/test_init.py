"""Test the vitrea integration setup and unloading."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vitrea_client: MagicMock,
) -> None:
    """Test successful setup of config entry."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.vitrea.VitreaClient", return_value=mock_vitrea_client
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_vitrea_client.connect.assert_called_once()

    # Verify runtime data is set up correctly (coordinator is stored directly)
    assert hasattr(mock_config_entry, "runtime_data")
    coordinator = mock_config_entry.runtime_data
    assert coordinator is not None
    assert coordinator.client == mock_vitrea_client

    # Verify only cover platform is loaded (simplified integration)
    assert len(hass.config_entries.async_entries("vitrea")) == 1


@pytest.mark.parametrize(
    ("side_effect", "expected_exception"),
    [
        (ConnectionError, ConfigEntryState.SETUP_RETRY),
        (TimeoutError, ConfigEntryState.SETUP_RETRY),
        (RuntimeError, ConfigEntryState.SETUP_ERROR),
    ],
)
async def test_setup_entry_connection_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vitrea_client: MagicMock,
    side_effect: Exception,
    expected_exception: Exception,
) -> None:
    """Test setup fails when connection fails."""
    mock_config_entry.add_to_hass(hass)
    mock_vitrea_client.connect.side_effect = side_effect
    with patch(
        "homeassistant.components.vitrea.VitreaClient", return_value=mock_vitrea_client
    ):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    assert mock_config_entry.state is expected_exception


async def test_unload_entry(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test successful unloading of config entry."""
    assert init_integration.state is ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()
    assert init_integration.state is ConfigEntryState.NOT_LOADED


async def test_reload_entry(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_vitrea_client: MagicMock,
) -> None:
    """Test successful reloading of config entry."""
    assert init_integration.state is ConfigEntryState.LOADED

    # Keep the mock active during reload
    with patch(
        "homeassistant.components.vitrea.VitreaClient", return_value=mock_vitrea_client
    ):
        assert await hass.config_entries.async_reload(init_integration.entry_id)
        await hass.async_block_till_done()

    assert init_integration.state is ConfigEntryState.LOADED


@pytest.mark.parametrize(
    "side_effect",
    [
        ConnectionError("Connection error"),
        TimeoutError("Timeout error"),
    ],
)
async def test_unload_entry_error_handling(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_vitrea_client: MagicMock,
    side_effect: Exception,
) -> None:
    """Test unload entry handles disconnect errors gracefully."""
    assert init_integration.state is ConfigEntryState.LOADED

    mock_vitrea_client.disconnect.side_effect = side_effect

    with patch(
        "homeassistant.components.vitrea.VitreaClient", return_value=mock_vitrea_client
    ):
        assert await hass.config_entries.async_unload(init_integration.entry_id)
        await hass.async_block_till_done()
        assert init_integration.state is ConfigEntryState.NOT_LOADED
