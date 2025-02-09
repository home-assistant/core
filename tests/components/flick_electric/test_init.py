"""Test the Flick Electric config flow."""

from unittest.mock import AsyncMock

from pyflick.types import APIException, AuthException
import pytest

from homeassistant.components.flick_electric.const import CONF_ACCOUNT_ID, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
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
    mock_flick_client.getPricing.side_effect = exception

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state == config_entry_state


async def test_init_migration_single_account(
    hass: HomeAssistant, mock_flick_client: AsyncMock
) -> None:
    """Test migration with single account."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: CONF[CONF_USERNAME],
            CONF_PASSWORD: CONF[CONF_PASSWORD],
        },
        title=CONF_USERNAME,
        unique_id=CONF_USERNAME,
        version=1,
    )
    await setup_integration(hass, entry)

    assert len(hass.config_entries.flow.async_progress()) == 0
    assert entry.state is ConfigEntryState.LOADED
    assert entry.version == 2
    assert entry.unique_id == CONF[CONF_ACCOUNT_ID]
    assert entry.data == CONF


async def test_init_migration_multi_account_reauth(
    hass: HomeAssistant, mock_flick_client_multiple: AsyncMock
) -> None:
    """Test migration triggers reauth with multiple accounts."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: CONF[CONF_USERNAME],
            CONF_PASSWORD: CONF[CONF_PASSWORD],
        },
        title=CONF_USERNAME,
        unique_id=CONF_USERNAME,
        version=1,
    )
    await setup_integration(hass, entry)

    assert entry.state is ConfigEntryState.MIGRATION_ERROR

    # Ensure reauth flow is triggered
    await hass.async_block_till_done()
    assert len(hass.config_entries.flow.async_progress()) == 1
