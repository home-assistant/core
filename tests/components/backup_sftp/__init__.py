"""Tests SFTP Backup Storage integration."""

from collections.abc import AsyncGenerator
from unittest.mock import patch

import pytest

from homeassistant.components.backup import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.backup import async_initialize_backup
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def setup_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Set up the backup_sftp integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


@pytest.fixture(autouse=True)
async def setup_backup_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> AsyncGenerator[None]:
    """Set up SFTP Backup Location integration."""
    with (
        patch("homeassistant.components.backup.is_hassio", return_value=False),
        patch("homeassistant.components.backup.store.STORE_DELAY_SAVE", 0),
    ):
        async_initialize_backup(hass)
        assert await async_setup_component(hass, DOMAIN, {})
        await setup_integration(hass, config_entry)

        await hass.async_block_till_done()
        yield
