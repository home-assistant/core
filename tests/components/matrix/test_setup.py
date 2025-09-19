"""Test the Matrix integration setup and migration."""

from unittest.mock import AsyncMock, Mock, patch

from homeassistant.components.matrix import (
    DOMAIN,
    async_setup_entry,
    async_unload_entry,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

TEST_YAML_CONFIG = {
    DOMAIN: {
        "homeserver": "https://matrix.example.com",
        "username": "@user:example.com",
        "password": "password",
        "verify_ssl": True,
        "rooms": ["#test:example.com"],
        "commands": [
            {
                "word": "hello",
                "name": "test_command",
            }
        ],
    }
}


async def test_async_setup_no_config(hass: HomeAssistant) -> None:
    """Test setup with no configuration."""
    result = await async_setup_component(hass, DOMAIN, {})
    assert result is True


async def test_async_setup_with_yaml_creates_import_flow(hass: HomeAssistant) -> None:
    """Test that YAML config creates an import flow."""
    with (
        patch("homeassistant.components.matrix.MatrixBot") as mock_matrix_bot,
        patch(
            "homeassistant.components.matrix.async_setup_services"
        ) as mock_setup_services,
        patch.object(hass.config_entries.flow, "async_init") as mock_flow_init,
    ):
        mock_matrix_bot.return_value = Mock()
        mock_flow_init.return_value = Mock()

        result = await async_setup_component(hass, DOMAIN, TEST_YAML_CONFIG)

        assert result is True
        mock_flow_init.assert_called_once_with(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                "homeserver": "https://matrix.example.com",
                "username": "@user:example.com",
                "password": "password",
                "verify_ssl": True,
            },
        )
        mock_matrix_bot.assert_called_once()
        mock_setup_services.assert_called_once()


async def test_async_setup_with_existing_config_entry(hass: HomeAssistant) -> None:
    """Test that YAML config doesn't create import flow when config entry exists."""
    # Create an existing config entry
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="@user:example.com",
        data={
            "homeserver": "https://matrix.example.com",
            "username": "@user:example.com",
            "password": "password",
            "verify_ssl": True,
        },
    )
    entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.matrix.MatrixBot") as mock_matrix_bot,
        patch(
            "homeassistant.components.matrix.async_setup_services"
        ) as mock_setup_services,
        patch.object(hass.config_entries.flow, "async_init") as mock_flow_init,
    ):
        mock_matrix_bot.return_value = Mock()

        result = await async_setup_component(hass, DOMAIN, TEST_YAML_CONFIG)

        assert result is True
        # Should not create import flow since config entry exists
        mock_flow_init.assert_not_called()
        # Should still set up both YAML and config entry bots
        assert mock_matrix_bot.call_count >= 1
        # Services get set up twice - once for YAML, once for config entry
        assert mock_setup_services.call_count >= 1


async def test_async_setup_entry(hass: HomeAssistant) -> None:
    """Test async_setup_entry success."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "homeserver": "https://matrix.example.com",
            "username": "@testuser:example.com",
            "password": "testpass",
            "verify_ssl": True,
        },
        unique_id="@testuser:example.com",
    )

    with (
        patch("homeassistant.components.matrix.MatrixBot") as mock_bot_class,
    ):
        mock_bot = Mock()
        mock_bot.api.login.return_value = AsyncMock()
        mock_bot.api.sync.return_value = AsyncMock()
        mock_bot_class.return_value = mock_bot

        result = await async_setup_entry(hass, config_entry)

        assert result is True
        mock_bot_class.assert_called_once()


async def test_async_unload_entry(hass: HomeAssistant) -> None:
    """Test unloading a config entry."""
    # Setup a matrix bot in runtime_data
    mock_matrix_bot = Mock()
    mock_matrix_bot.async_close = AsyncMock()
    hass.data[DOMAIN] = mock_matrix_bot

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="@user:example.com",
        data={
            "homeserver": "https://matrix.example.com",
            "username": "@user:example.com",
            "password": "password",
            "verify_ssl": True,
        },
    )
    # Set runtime_data to simulate proper setup
    entry.runtime_data = mock_matrix_bot

    result = await async_unload_entry(hass, entry)

    assert result is True
    mock_matrix_bot.async_close.assert_called_once()
    assert DOMAIN not in hass.data


async def test_async_unload_entry_no_matrix_bot(hass: HomeAssistant) -> None:
    """Test unloading a config entry when no matrix bot exists."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="@user:example.com",
        data={
            "homeserver": "https://matrix.example.com",
            "username": "@user:example.com",
            "password": "password",
            "verify_ssl": True,
        },
    )

    result = await async_unload_entry(hass, entry)

    assert result is True
    assert DOMAIN not in hass.data
