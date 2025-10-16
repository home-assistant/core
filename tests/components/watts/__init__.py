"""Tests for the Watts Vision integration."""

from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def setup_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_client: AsyncMock,
) -> None:
    """Set up the Watts Vision integration for testing."""
    config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation"
        ) as mock_get_implementation,
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session"
        ) as mock_session,
        patch(
            "homeassistant.components.watts.WattsVisionClient",
            return_value=mock_client,
        ),
        patch(
            "homeassistant.components.watts.WattsVisionAuth",
        ) as mock_auth_class,
    ):
        # Mock OAuth2 implementation
        mock_implementation = AsyncMock()
        mock_implementation.client_id = "test-client-id"
        mock_implementation.client_secret = "test-client-secret"
        mock_get_implementation.return_value = mock_implementation

        # Mock OAuth2 session
        mock_session_instance = AsyncMock()
        mock_session_instance.token = config_entry.data["token"]
        mock_session_instance.async_ensure_token_valid = AsyncMock()
        mock_session.return_value = mock_session_instance

        # Mock auth
        mock_auth_instance = AsyncMock()
        mock_auth_class.return_value = mock_auth_instance

        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
