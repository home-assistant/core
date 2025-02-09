"""Test the Flick Electric config flow."""

from unittest.mock import AsyncMock, patch

from pyflick.types import APIException, AuthException
import pytest

from homeassistant.components.flick_electric.const import CONF_ACCOUNT_ID
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import CONF, setup_integration

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("exception", "config_entry_state"),
    [
        (AuthException, ConfigEntryState.SETUP_ERROR),
        (APIException, ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_init_auth_failure_triggers_auth(
    hass: HomeAssistant,
    mock_flick_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    config_entry_state: ConfigEntryState,
) -> None:
    """Test integration handles initialisation errors."""
    with patch.object(mock_flick_client, "getPricing", side_effect=exception):
        await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state == config_entry_state


async def test_init_migration_single_account(
    hass: HomeAssistant,
    mock_old_config_entry: MockConfigEntry,
    mock_flick_client: AsyncMock,
) -> None:
    """Test migration with single account."""
    await setup_integration(hass, mock_old_config_entry)

    assert len(hass.config_entries.flow.async_progress()) == 0
    assert mock_old_config_entry.state is ConfigEntryState.LOADED
    assert mock_old_config_entry.version == 2
    assert mock_old_config_entry.unique_id == CONF[CONF_ACCOUNT_ID]
    assert mock_old_config_entry.data == CONF


async def test_init_migration_multi_account_reauth(
    hass: HomeAssistant,
    mock_old_config_entry: MockConfigEntry,
    mock_flick_client_multiple: AsyncMock,
) -> None:
    """Test migration triggers reauth with multiple accounts."""
    await setup_integration(hass, mock_old_config_entry)

    assert mock_old_config_entry.state is ConfigEntryState.MIGRATION_ERROR

    # Ensure reauth flow is triggered
    await hass.async_block_till_done()
    assert len(hass.config_entries.flow.async_progress()) == 1
