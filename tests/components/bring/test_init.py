"""Unit tests for the bring integration."""
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.bring import (
    BringAuthException,
    BringParseException,
    BringRequestException,
)
from homeassistant.components.bring.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def setup_integration(
    hass: HomeAssistant,
    bring_config_entry: MockConfigEntry,
) -> None:
    """Mock setup of the bring integration."""
    bring_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(bring_config_entry.entry_id)
    await hass.async_block_till_done()


async def test_load_unload(
    hass: HomeAssistant,
    mock_bring_client: AsyncMock,
    bring_config_entry: MockConfigEntry,
) -> None:
    """Test loading and unloading of the config entry."""
    await setup_integration(hass, bring_config_entry)

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    assert bring_config_entry.state == ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(bring_config_entry.entry_id)
    assert bring_config_entry.state == ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("exception", "status"),
    [
        (BringRequestException, ConfigEntryState.SETUP_RETRY),
        (BringAuthException, ConfigEntryState.SETUP_ERROR),
        (BringParseException, ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_init_failure(
    hass: HomeAssistant,
    mock_bring_client: AsyncMock,
    status: ConfigEntryState,
    exception: Exception,
    bring_config_entry: MockConfigEntry | None,
) -> None:
    """Test an initialization error on integration load."""
    mock_bring_client.loginAsync.side_effect = exception
    await setup_integration(hass, bring_config_entry)
    assert bring_config_entry.state == status
