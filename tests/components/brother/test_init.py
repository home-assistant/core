"""Test init of Brother integration."""

from unittest.mock import AsyncMock, patch

from brother import SnmpError
import pytest

from homeassistant.components.brother.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import init_integration

from tests.common import MockConfigEntry


async def test_async_setup_entry(
    hass: HomeAssistant,
    mock_brother_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a successful setup entry."""
    await init_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_config_not_ready(
    hass: HomeAssistant,
    mock_brother_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test for setup failure if connection to broker is missing."""
    mock_brother_client.async_update.side_effect = ConnectionError

    await init_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize("exc", [(SnmpError("SNMP Error")), (ConnectionError)])
async def test_error_on_init(
    hass: HomeAssistant, exc: Exception, mock_config_entry: MockConfigEntry
) -> None:
    """Test for error on init."""
    with patch(
        "homeassistant.components.brother.Brother.create",
        new=AsyncMock(side_effect=exc),
    ):
        await init_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant,
    mock_brother_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful unload of entry."""
    await init_integration(hass, mock_config_entry)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)
