"""Test Wireless Sensor Tag integration setup."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from wirelesstagpy.exceptions import WirelessTagsException

from homeassistant.components.wirelesstag.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry_success(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test successful setup of config entry."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.wirelesstag.WirelessTagAPI") as mock_api_class:
        mock_api = mock_api_class.return_value
        mock_api.async_authenticate = AsyncMock(return_value=True)
        mock_api.async_get_tags = AsyncMock(
            return_value={"tag_1": {"uuid": "test", "is_alive": True}}
        )
        mock_api.async_start_monitoring = AsyncMock()

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Verify coordinator is created and authenticated
    mock_api.async_authenticate.assert_called_once()
    mock_api_class.assert_called_once_with(hass, "test@example.com", "test_password")


async def test_setup_entry_auth_failed(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup with authentication failure."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.wirelesstag.WirelessTagAPI") as mock_api_class:
        mock_api = mock_api_class.return_value
        mock_api.async_authenticate = AsyncMock(return_value=False)
        mock_api.async_get_tags = AsyncMock()
        mock_api.async_start_monitoring = AsyncMock()

        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_coordinator_failure(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup failure due to coordinator error."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.wirelesstag.WirelessTagAPI") as mock_api_class:
        mock_api = mock_api_class.return_value
        mock_api.async_authenticate = AsyncMock(return_value=True)
        mock_api.async_get_tags = AsyncMock(
            side_effect=WirelessTagsException("API Error")
        )
        mock_api.async_start_monitoring = AsyncMock()

        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test successful unload of entry."""
    assert init_integration.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert init_integration.state is ConfigEntryState.NOT_LOADED


async def test_reload_entry(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test successful reload of entry."""
    assert init_integration.state is ConfigEntryState.LOADED

    with patch(
        "homeassistant.components.wirelesstag.coordinator.WirelessTagAPI"
    ) as mock_api_class:
        mock_api = mock_api_class.return_value
        mock_api.async_authenticate.return_value = True
        mock_api.async_get_tags.return_value = {
            "tag_1": {"uuid": "test", "is_alive": True}
        }

        assert await hass.config_entries.async_reload(init_integration.entry_id)
        await hass.async_block_till_done()

    assert init_integration.state is ConfigEntryState.LOADED


async def test_setup_multiple_entries(hass: HomeAssistant) -> None:
    """Test setting up multiple config entries."""
    # For simplicity, just test that multiple entries can exist
    # They won't be set up simultaneously in this test
    entry1 = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: "user1@example.com", CONF_PASSWORD: "pass1"},
        unique_id="user1@example.com",
    )
    entry2 = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: "user2@example.com", CONF_PASSWORD: "pass2"},
        unique_id="user2@example.com",
    )

    entry1.add_to_hass(hass)
    entry2.add_to_hass(hass)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 2
