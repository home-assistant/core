"""Test squeezebox initialization."""

from http import HTTPStatus
from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_init_api_fail(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test init fail due to API fail."""

    # Setup component to fail...
    with (
        patch(
            "homeassistant.components.squeezebox.Server.async_query",
            return_value=False,
        ),
    ):
        assert not await hass.config_entries.async_setup(config_entry.entry_id)


async def test_init_timeout_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test init fail due to TimeoutError."""

    # Setup component to raise TimeoutError
    with (
        patch(
            "homeassistant.components.squeezebox.Server.async_query",
            side_effect=TimeoutError,
        ),
    ):
        assert not await hass.config_entries.async_setup(config_entry.entry_id)
        assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_init_unauthorized(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test init fail due to unauthorized error."""

    # Setup component to simulate unauthorized response
    with (
        patch(
            "homeassistant.components.squeezebox.Server.async_query",
            return_value=False,  # async_query returns False on auth failure
        ),
        patch(
            "homeassistant.components.squeezebox.Server",  # Patch the Server class itself
            autospec=True,
        ) as mock_server_instance,
    ):
        mock_server_instance.return_value.http_status = HTTPStatus.UNAUTHORIZED
        assert not await hass.config_entries.async_setup(config_entry.entry_id)
        assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_init_missing_uuid(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test init fail due to missing UUID in server status."""
    # A response that is truthy but does not contain STATUS_QUERY_UUID
    mock_status_without_uuid = {"name": "Test Server"}

    with patch(
        "homeassistant.components.squeezebox.Server.async_query",
        return_value=mock_status_without_uuid,
    ) as mock_async_query:
        # ConfigEntryError is raised, caught by setup, and returns False
        assert not await hass.config_entries.async_setup(config_entry.entry_id)
        assert config_entry.state is ConfigEntryState.SETUP_ERROR
        mock_async_query.assert_called_once_with(
            "serverstatus", "-", "-", "prefs:libraryname"
        )
