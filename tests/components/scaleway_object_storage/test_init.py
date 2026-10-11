"""Tests for the Scaleway Object Storage integration config entry initialization."""

from unittest.mock import patch

import pytest
import pytest_asyncio

from homeassistant.components.backup import DOMAIN as BACKUP_DOMAIN, BackupAgentError
from homeassistant.components.scaleway_object_storage import ScalewayNotReadyException
from homeassistant.components.scaleway_object_storage.const import DOMAIN
from homeassistant.components.scaleway_object_storage.exceptions import (
    InvalidBucketException,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest_asyncio.fixture(autouse=True)
async def setup_config(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Set up integration config entry and backup component."""
    assert await async_setup_component(hass, BACKUP_DOMAIN, {})
    mock_config_entry.add_to_hass(hass)


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test loading and unloading the integration."""
    with patch(
        "homeassistant.components.scaleway_object_storage.helpers.check_connection",
        return_value=None,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("exception", "expected_state"),
    [
        (
            ScalewayNotReadyException(
                translation_domain=DOMAIN, translation_key="cannot_connect"
            ),
            ConfigEntryState.SETUP_RETRY,
        ),
        (
            ScalewayNotReadyException(
                translation_domain=DOMAIN, translation_key="server_unavailable"
            ),
            ConfigEntryState.SETUP_RETRY,
        ),
        (BackupAgentError, ConfigEntryState.SETUP_ERROR),
        (ConfigEntryAuthFailed, ConfigEntryState.SETUP_ERROR),
        (InvalidBucketException, ConfigEntryState.SETUP_ERROR),
    ],
)
async def test_setup_entry_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test integration init behavior if a connection error is raised."""
    with patch(
        "homeassistant.components.scaleway_object_storage.helpers.check_connection",
        side_effect=exception,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is expected_state
