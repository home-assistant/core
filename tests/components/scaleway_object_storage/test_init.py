"""Tests for the Scaleway Object Storage integration config entry initialization."""

from unittest.mock import patch

import pytest
import pytest_asyncio

from homeassistant.components.backup import DOMAIN as BACKUP_DOMAIN
from homeassistant.components.scaleway_object_storage import exceptions
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
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

    assert mock_config_entry.state == ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state == ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    "exception",
    [
        exceptions.ScalewayConnectionError,
        exceptions.ServerUnavailableError,
    ],
)
async def test_setup_entry_retriable_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    exception: exceptions.ScalewayException,
) -> None:
    """Test loading the integration with retriable errors."""
    with patch(
        "homeassistant.components.scaleway_object_storage.helpers.check_connection",
        side_effect=exception,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_auth_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test loading the integration with invalid auth."""
    with patch(
        "homeassistant.components.scaleway_object_storage.helpers.check_connection",
        side_effect=exceptions.InvalidAuthException,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state == ConfigEntryState.SETUP_ERROR


async def test_setup_entry_bucket_not_found(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test loading the integration with a deleted bucket."""
    with patch(
        "homeassistant.components.scaleway_object_storage.helpers.check_connection",
        side_effect=exceptions.BucketNotFoundException,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state == ConfigEntryState.SETUP_ERROR
