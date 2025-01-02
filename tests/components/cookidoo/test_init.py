"""Unit tests for the cookidoo integration."""

from unittest.mock import AsyncMock

from cookidoo_api import CookidooAuthException, CookidooRequestException
import pytest

from homeassistant.components.cookidoo.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_cookidoo_client")
async def test_load_unload(
    hass: HomeAssistant,
    cookidoo_config_entry: MockConfigEntry,
) -> None:
    """Test loading and unloading of the config entry."""
    await setup_integration(hass, cookidoo_config_entry)

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    assert cookidoo_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(cookidoo_config_entry.entry_id)
    assert cookidoo_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("exception", "status"),
    [
        (CookidooRequestException, ConfigEntryState.SETUP_RETRY),
        (CookidooAuthException, ConfigEntryState.SETUP_ERROR),
    ],
)
async def test_init_failure(
    hass: HomeAssistant,
    mock_cookidoo_client: AsyncMock,
    status: ConfigEntryState,
    exception: Exception,
    cookidoo_config_entry: MockConfigEntry,
) -> None:
    """Test an initialization error on integration load."""
    mock_cookidoo_client.login.side_effect = exception
    await setup_integration(hass, cookidoo_config_entry)
    assert cookidoo_config_entry.state == status


@pytest.mark.parametrize(
    "cookidoo_method",
    [
        "get_ingredient_items",
        "get_additional_items",
    ],
)
async def test_config_entry_not_ready(
    hass: HomeAssistant,
    cookidoo_config_entry: MockConfigEntry,
    mock_cookidoo_client: AsyncMock,
    cookidoo_method: str,
) -> None:
    """Test config entry not ready."""
    getattr(
        mock_cookidoo_client, cookidoo_method
    ).side_effect = CookidooRequestException()
    cookidoo_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(cookidoo_config_entry.entry_id)
    await hass.async_block_till_done()

    assert cookidoo_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    ("exception", "status"),
    [
        (None, ConfigEntryState.LOADED),
        (CookidooRequestException, ConfigEntryState.SETUP_RETRY),
        (CookidooAuthException, ConfigEntryState.SETUP_ERROR),
    ],
)
async def test_config_entry_not_ready_auth_error(
    hass: HomeAssistant,
    cookidoo_config_entry: MockConfigEntry,
    mock_cookidoo_client: AsyncMock,
    exception: Exception | None,
    status: ConfigEntryState,
) -> None:
    """Test config entry not ready from authentication error."""

    mock_cookidoo_client.get_ingredient_items.side_effect = CookidooAuthException
    mock_cookidoo_client.refresh_token.side_effect = exception

    cookidoo_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(cookidoo_config_entry.entry_id)
    await hass.async_block_till_done()

    assert cookidoo_config_entry.state is status
