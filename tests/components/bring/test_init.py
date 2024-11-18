"""Unit tests for the bring integration."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.bring import (
    BringAuthException,
    BringParseException,
    BringRequestException,
    async_setup_entry,
)
from homeassistant.components.bring.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from tests.common import MockConfigEntry


async def setup_integration(
    hass: HomeAssistant,
    bring_config_entry: MockConfigEntry,
) -> None:
    """Mock setup of the bring integration."""
    bring_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(bring_config_entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_bring_client")
async def test_load_unload(
    hass: HomeAssistant,
    bring_config_entry: MockConfigEntry,
) -> None:
    """Test loading and unloading of the config entry."""
    await setup_integration(hass, bring_config_entry)

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    assert bring_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(bring_config_entry.entry_id)
    assert bring_config_entry.state is ConfigEntryState.NOT_LOADED


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
    bring_config_entry: MockConfigEntry,
) -> None:
    """Test an initialization error on integration load."""
    mock_bring_client.login.side_effect = exception
    await setup_integration(hass, bring_config_entry)
    assert bring_config_entry.state == status


@pytest.mark.parametrize(
    ("exception", "expected"),
    [
        (BringRequestException, ConfigEntryNotReady),
        (BringAuthException, ConfigEntryAuthFailed),
        (BringParseException, ConfigEntryNotReady),
    ],
)
async def test_init_exceptions(
    hass: HomeAssistant,
    mock_bring_client: AsyncMock,
    exception: Exception,
    expected: Exception,
    bring_config_entry: MockConfigEntry,
) -> None:
    """Test an initialization error on integration load."""
    bring_config_entry.add_to_hass(hass)
    mock_bring_client.login.side_effect = exception

    with pytest.raises(expected):
        await async_setup_entry(hass, bring_config_entry)


@pytest.mark.parametrize("exception", [BringRequestException, BringParseException])
@pytest.mark.parametrize(
    "bring_method",
    [
        "load_lists",
        "get_list",
        "get_all_user_settings",
    ],
)
async def test_config_entry_not_ready(
    hass: HomeAssistant,
    bring_config_entry: MockConfigEntry,
    mock_bring_client: AsyncMock,
    exception: Exception,
    bring_method: str,
) -> None:
    """Test config entry not ready."""
    getattr(mock_bring_client, bring_method).side_effect = exception
    bring_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(bring_config_entry.entry_id)
    await hass.async_block_till_done()

    assert bring_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    "exception", [None, BringAuthException, BringRequestException, BringParseException]
)
async def test_config_entry_not_ready_auth_error(
    hass: HomeAssistant,
    bring_config_entry: MockConfigEntry,
    mock_bring_client: AsyncMock,
    exception: Exception | None,
) -> None:
    """Test config entry not ready from authentication error."""

    mock_bring_client.load_lists.side_effect = BringAuthException
    mock_bring_client.retrieve_new_access_token.side_effect = exception

    bring_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(bring_config_entry.entry_id)
    await hass.async_block_till_done()

    assert bring_config_entry.state is ConfigEntryState.SETUP_RETRY
