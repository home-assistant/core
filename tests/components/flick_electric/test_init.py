"""Test the Flick Electric config flow."""

from unittest.mock import AsyncMock, patch

import jwt
from pyflick.types import APIException, AuthException
import pytest

from homeassistant.components.flick_electric import CONF_ID_TOKEN, HassFlickAuth
from homeassistant.components.flick_electric.const import (
    CONF_ACCOUNT_ID,
    CONF_TOKEN_EXPIRY,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import CONF, setup_integration

from tests.common import MockConfigEntry

NEW_TOKEN = jwt.encode(
    {"exp": dt_util.now().timestamp() + 86400}, "secret", algorithm="HS256"
)
EXISTING_TOKEN = jwt.encode(
    {"exp": dt_util.now().timestamp() + 3600}, "secret", algorithm="HS256"
)
EXPIRED_TOKEN = jwt.encode(
    {"exp": dt_util.now().timestamp() - 3600}, "secret", algorithm="HS256"
)


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


async def test_fetch_fresh_token(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_flick_client: AsyncMock,
) -> None:
    """Test fetching a fresh token."""
    await setup_integration(hass, mock_config_entry)

    with patch(
        "homeassistant.components.flick_electric.config_flow.SimpleFlickAuth.get_new_token",
        return_value={CONF_ID_TOKEN: NEW_TOKEN},
    ) as mock_get_new_token:
        auth = HassFlickAuth(hass, mock_config_entry)

        assert await auth.async_get_access_token() == NEW_TOKEN
        assert mock_get_new_token.call_count == 1


async def test_reuse_token(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_flick_client: AsyncMock,
) -> None:
    """Test reusing entry token."""
    await setup_integration(hass, mock_config_entry)

    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={
            **mock_config_entry.data,
            CONF_ACCESS_TOKEN: {CONF_ID_TOKEN: EXISTING_TOKEN},
            CONF_TOKEN_EXPIRY: dt_util.now().timestamp() + 3600,
        },
    )

    with patch(
        "homeassistant.components.flick_electric.config_flow.SimpleFlickAuth.get_new_token",
        return_value={CONF_ID_TOKEN: NEW_TOKEN},
    ) as mock_get_new_token:
        auth = HassFlickAuth(hass, mock_config_entry)

        assert await auth.async_get_access_token() == EXISTING_TOKEN
        assert mock_get_new_token.call_count == 0


async def test_fetch_expired_token(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_flick_client: AsyncMock,
) -> None:
    """Test fetching token when existing token is expired."""
    await setup_integration(hass, mock_config_entry)

    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={
            **mock_config_entry.data,
            CONF_ACCESS_TOKEN: {CONF_ID_TOKEN: EXPIRED_TOKEN},
            CONF_TOKEN_EXPIRY: dt_util.now().timestamp() - 3600,
        },
    )

    with patch(
        "homeassistant.components.flick_electric.config_flow.SimpleFlickAuth.get_new_token",
        return_value={CONF_ID_TOKEN: NEW_TOKEN},
    ) as mock_get_new_token:
        auth = HassFlickAuth(hass, mock_config_entry)

        assert await auth.async_get_access_token() == NEW_TOKEN
        assert mock_get_new_token.call_count == 1
