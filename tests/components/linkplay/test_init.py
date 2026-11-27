"""Tests for the LinkPlay integration setup."""

from unittest.mock import AsyncMock, patch

from linkplay.exceptions import LinkPlayInvalidDataException, LinkPlayRequestException
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration


@pytest.mark.parametrize(
    "exception",
    [
        LinkPlayRequestException("Error"),
        LinkPlayInvalidDataException("Unexpected JSON (unknown command)"),
    ],
)
async def test_setup_retries_when_the_device_fails(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, exception: Exception
) -> None:
    """Test setup is retried when the device can't be reached or sends bad data."""
    with (
        patch(
            "homeassistant.components.linkplay.async_get_client_session",
            return_value=AsyncMock(),
        ),
        patch(
            "homeassistant.components.linkplay.linkplay_factory_httpapi_bridge",
            side_effect=exception,
        ),
    ):
        await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
