"""Tests for SpaceXAI setup."""

from http import HTTPStatus
from unittest.mock import MagicMock, patch

import pytest
from spacexai_subscription_client import (
    AuthenticationError,
    PermissionDeniedError,
    SpaceXAISubscriptionError,
)
from spacexai_subscription_client.const import GROK_CLI_OAUTH_CLIENT_ID, TOKEN_URL

from homeassistant.components.spacexai.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.httpx_client import get_async_client

from . import setup_integration

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_setup_and_unload(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_spacexai_subscription_client: MagicMock,
) -> None:
    """Set up and unload the Conversation platform."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get("conversation.grok") is not None
    mock_spacexai_subscription_client.async_list_models.assert_awaited_once_with(
        "access-token"
    )
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "conversation-subentry"), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.manufacturer == "SpaceXAI"
    assert device.model == "grok-4.6"
    assert device.entry_type is dr.DeviceEntryType.SERVICE

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("error", "state"),
    [
        pytest.param(
            PermissionDeniedError,
            ConfigEntryState.SETUP_ERROR,
            id="permission_denied",
        ),
        pytest.param(
            AuthenticationError,
            ConfigEntryState.SETUP_ERROR,
            id="authentication",
        ),
        pytest.param(
            SpaceXAISubscriptionError,
            ConfigEntryState.SETUP_RETRY,
            id="connection",
        ),
    ],
)
async def test_setup_error(
    hass: HomeAssistant,
    error: type[SpaceXAISubscriptionError],
    mock_config_entry: MockConfigEntry,
    mock_spacexai_subscription_client: MagicMock,
    state: ConfigEntryState,
) -> None:
    """Translate client failures during setup."""
    mock_spacexai_subscription_client.async_list_models.side_effect = error
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is state


async def test_setup_without_models(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_spacexai_subscription_client: MagicMock,
) -> None:
    """Retry setup when the account has no available models."""
    mock_spacexai_subscription_client.async_list_models.return_value = ()
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_uses_shared_sessions(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_spacexai_subscription_client: MagicMock,
) -> None:
    """Inject Home Assistant's shared HTTP sessions into the client."""
    with patch(
        "homeassistant.components.spacexai.SpaceXAISubscriptionClient",
        return_value=mock_spacexai_subscription_client,
    ) as client_class:
        await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    client_class.assert_called_once_with(
        async_get_clientsession(hass),
        get_async_client(hass),
    )


async def test_setup_refreshes_expired_token_and_persists_rotation(
    aioclient_mock: AiohttpClientMocker,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_spacexai_subscription_client: MagicMock,
) -> None:
    """Refresh an expired token during setup and persist token rotation."""
    mock_config_entry.data["token"]["expires_at"] = 0
    aioclient_mock.post(
        TOKEN_URL,
        json={
            "access_token": "new-access-token",
            "refresh_token": "new-refresh-token",
            "expires_in": 3600,
            "token_type": "Bearer",
        },
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.data["token"]["access_token"] == "new-access-token"
    assert mock_config_entry.data["token"]["refresh_token"] == "new-refresh-token"
    assert aioclient_mock.mock_calls[0][2] == {
        "client_id": GROK_CLI_OAUTH_CLIENT_ID,
        "grant_type": "refresh_token",
        "refresh_token": "refresh-token",
    }
    mock_spacexai_subscription_client.async_list_models.assert_awaited_once_with(
        "new-access-token"
    )

    mock_spacexai_subscription_client.async_list_models.reset_mock()
    assert await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.data["token"]["refresh_token"] == "new-refresh-token"
    mock_spacexai_subscription_client.async_list_models.assert_awaited_once_with(
        "new-access-token"
    )
    assert aioclient_mock.call_count == 1


@pytest.mark.parametrize(
    ("status", "expected_state"),
    [
        pytest.param(
            HTTPStatus.BAD_REQUEST,
            ConfigEntryState.SETUP_ERROR,
            id="invalid_refresh_grant",
        ),
        pytest.param(
            HTTPStatus.UNAUTHORIZED,
            ConfigEntryState.SETUP_ERROR,
            id="revoked_refresh_token",
        ),
        pytest.param(
            HTTPStatus.TOO_MANY_REQUESTS,
            ConfigEntryState.SETUP_RETRY,
            id="rate_limited",
        ),
        pytest.param(
            HTTPStatus.INTERNAL_SERVER_ERROR,
            ConfigEntryState.SETUP_RETRY,
            id="provider_failure",
        ),
    ],
)
async def test_setup_expired_token_refresh_error(
    aioclient_mock: AiohttpClientMocker,
    expected_state: ConfigEntryState,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    status: HTTPStatus,
) -> None:
    """Classify permanent and transient failures refreshing an expired token."""
    mock_config_entry.data["token"]["expires_at"] = 0
    aioclient_mock.post(TOKEN_URL, status=status)
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is expected_state


async def test_setup_token_refresh_timeout_and_retry(
    aioclient_mock: AiohttpClientMocker,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_spacexai_subscription_client: MagicMock,
) -> None:
    """Keep credentials and retry setup after a token endpoint timeout."""
    mock_config_entry.data["token"]["expires_at"] = 0
    original_token = dict(mock_config_entry.data["token"])
    aioclient_mock.post(TOKEN_URL, exc=TimeoutError)
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_config_entry.data["token"] == original_token
    mock_spacexai_subscription_client.async_list_models.assert_not_awaited()

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        TOKEN_URL,
        json={
            "access_token": "new-access-token",
            "refresh_token": "new-refresh-token",
            "expires_in": 3600,
            "token_type": "Bearer",
        },
    )

    assert await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.data["token"]["refresh_token"] == "new-refresh-token"
    mock_spacexai_subscription_client.async_list_models.assert_awaited_once_with(
        "new-access-token"
    )
