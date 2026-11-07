"""Tests for TFA.me: test of __init__.py."""

from unittest.mock import MagicMock

import pytest
from tfa_me_ha_local.client import (
    TFAmeConnectionError,
    TFAmeException,
    TFAmeHTTPError,
    TFAmeJSONError,
    TFAmeTimeoutError,
)

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_full_entry_setup(
    hass: HomeAssistant,
    tfa_me_config_entry: MockConfigEntry,
    mock_tfa_me_client: MagicMock,
) -> None:
    """Test full setup of the integration."""
    assert await hass.config_entries.async_setup(tfa_me_config_entry.entry_id)
    await hass.async_block_till_done()

    assert tfa_me_config_entry.state is ConfigEntryState.LOADED


async def test_async_unload_entry(
    hass: HomeAssistant,
    tfa_me_config_entry: MockConfigEntry,
    mock_tfa_me_client: MagicMock,
) -> None:
    """Test unload of the integration."""
    assert await hass.config_entries.async_setup(tfa_me_config_entry.entry_id)
    await hass.async_block_till_done()

    assert tfa_me_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(tfa_me_config_entry.entry_id)
    await hass.async_block_till_done()

    assert tfa_me_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_first_refresh_failure(
    hass: HomeAssistant,
    tfa_me_config_entry: MockConfigEntry,
    mock_tfa_me_client: MagicMock,
) -> None:
    """Test config entry setup retries when the first refresh fails."""
    mock_tfa_me_client.side_effect = TFAmeConnectionError("Connection failed")

    await hass.config_entries.async_setup(tfa_me_config_entry.entry_id)
    await hass.async_block_till_done()

    assert tfa_me_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    "exception",
    [
        TFAmeHTTPError("HTTP error"),
        TFAmeJSONError("JSON error"),
        TFAmeTimeoutError("Timeout"),
        TFAmeConnectionError("Connection error"),
        TFAmeException("Client error"),
    ],
    ids=[
        "http_error",
        "json_error",
        "timeout",
        "connection_error",
        "client_error",
    ],
)
async def test_setup_retry_on_client_error(
    hass: HomeAssistant,
    tfa_me_config_entry: MockConfigEntry,
    mock_tfa_me_client: MagicMock,
    exception: TFAmeException,
) -> None:
    """Test setup retries when the station cannot be updated."""
    mock_tfa_me_client.side_effect = exception

    await hass.config_entries.async_setup(tfa_me_config_entry.entry_id)
    await hass.async_block_till_done()

    assert tfa_me_config_entry.state is ConfigEntryState.SETUP_RETRY
