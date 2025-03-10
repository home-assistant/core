"""Test the s3 storage integration."""

from unittest.mock import patch

import pytest

from homeassistant.components.s3._api import (
    CannotConnectError,
    InvalidBucketNameError,
    InvalidCredentialsError,
    InvalidEndpointURLError,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test loading and unloading the integration."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("exception", "state"),
    [
        (InvalidCredentialsError, ConfigEntryState.SETUP_ERROR),
        (InvalidBucketNameError, ConfigEntryState.SETUP_ERROR),
        (InvalidEndpointURLError, ConfigEntryState.SETUP_ERROR),
        (CannotConnectError, ConfigEntryState.SETUP_ERROR),
    ],
)
async def test_setup_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    state: ConfigEntryState,
) -> None:
    """Test various setup errors."""
    with patch(
        "homeassistant.components.s3.get_client",
        side_effect=exception,
    ):
        await setup_integration(hass, mock_config_entry)
        assert mock_config_entry.state is state
