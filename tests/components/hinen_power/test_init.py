"""Tests for the Hinen integration init module."""

import time
from unittest.mock import AsyncMock, Mock, patch

import pytest
from yarl import URL

from homeassistant.components.application_credentials import (
    AuthorizationServer,
    ClientCredential,
)
from homeassistant.components.hinen_power.auth_config import HinenImplementation
from homeassistant.components.hinen_power.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    OAuth2TokenRequestReauthError,
    OAuth2TokenRequestTransientError,
)

from . import MockHinen
from .conftest import TOKEN_URL, ComponentSetup

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_async_setup_entry_success(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test successful setup of the integration."""
    config_entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.hinen_power.HinenDataUpdateCoordinator.async_config_entry_first_refresh",
            return_value=None,
        ),
        patch(
            "homeassistant.components.hinen_power.AsyncConfigEntryAuth.check_and_refresh_token",
            return_value=None,
        ),
    ):
        result = await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert result
    assert config_entry.state is ConfigEntryState.LOADED

    assert hasattr(config_entry, "runtime_data")
    assert config_entry.runtime_data is not None


@pytest.mark.parametrize("expires_at", [time.time() - 3600], ids=["expired"])
async def test_expired_token_refresh_success(
    hass: HomeAssistant,
    setup_integration: ComponentSetup,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test expired token is refreshed."""
    aioclient_mock.clear_requests()
    aioclient_mock.get(
        TOKEN_URL,
        json={
            "data": {
                "access_token": "updated-access-token",
                "refresh_token": "updated-refresh-token",
                "expires_at": time.time() + 3600,
                "expires_in": 3600,
            }
        },
    )

    service = MockHinen(hass)
    with patch(
        "homeassistant.components.hinen_power.AsyncConfigEntryAuth.get_resource",
        return_value=service,
    ):
        await setup_integration()

        entries = hass.config_entries.async_entries(DOMAIN)
        assert len(entries) == 1
        assert entries[0].state is ConfigEntryState.LOADED
        assert entries[0].data["token"]["access_token"] == "updated-access-token"
        assert entries[0].data["token"]["expires_in"] == 3600


async def test_async_unload_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test successful unload of the integration."""
    config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.hinen_power.HinenDataUpdateCoordinator.async_config_entry_first_refresh",
            return_value=None,
        ),
        patch(
            "homeassistant.components.hinen_power.AsyncConfigEntryAuth.check_and_refresh_token",
            return_value=None,
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("status", "expected_error_class"),
    [
        (400, OAuth2TokenRequestReauthError),
        (401, OAuth2TokenRequestReauthError),
        (403, OAuth2TokenRequestReauthError),
        (429, OAuth2TokenRequestTransientError),
        (500, OAuth2TokenRequestTransientError),
        (503, OAuth2TokenRequestTransientError),
    ],
)
async def test_token_request_error_mapping(
    hass: HomeAssistant,
    status: int,
    expected_error_class: type[Exception],
) -> None:
    """Test _token_request maps HTTP errors to correct OAuth2 exceptions."""
    impl = HinenImplementation(
        hass,
        domain="hinen_power",
        client_credential=ClientCredential("id", "secret"),
        authorization_server=AuthorizationServer(
            authorize_url="https://auth.url",
            token_url=TOKEN_URL,
        ),
    )

    mock_response = AsyncMock()
    mock_response.status = status
    mock_response.json.return_value = {}
    mock_response.request_info = Mock(url=URL(TOKEN_URL))
    mock_response.headers = {}
    mock_response.history = ()

    with patch(
        "homeassistant.components.hinen_power.auth_config.async_get_clientsession"
    ) as mock_session:
        mock_session.return_value.get.return_value.__aenter__ = AsyncMock(
            return_value=mock_response
        )

        with pytest.raises(expected_error_class):
            await impl._token_request({"some": "data"})
