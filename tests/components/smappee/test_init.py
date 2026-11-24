"""Tests for the Smappee component init module."""

from http import HTTPStatus
import re
from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker
import requests_mock

from homeassistant.components.smappee.const import DOMAIN, TOKEN_URL
from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_USER,
    SOURCE_ZEROCONF,
    ConfigEntryState,
)
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import OAuth2TokenRequestReauthError
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
)
from homeassistant.setup import async_setup_component

MOCK_TOKEN_RESPONSE = {
    "refresh_token": "mock-refresh-token",
    "access_token": "mock-access-token",
    "type": "Bearer",
    "expires_in": 60,
}


@pytest.fixture
async def cloud_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the Smappee component and return a cloud entry with expired token."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {DOMAIN: {CONF_CLIENT_ID: "1234", CONF_CLIENT_SECRET: "5678"}},
    )
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="smappeeCloud",
        source=SOURCE_USER,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "mock-access-token",
                "refresh_token": "mock-refresh-token",
                "expires_at": 0,
                "token_type": "Bearer",
            },
        },
    )
    config_entry.add_to_hass(hass)
    return config_entry


async def test_unload_config_entry(hass: HomeAssistant) -> None:
    """Test unload config entry flow."""
    with (
        patch("pysmappee.api.SmappeeLocalApi.logon", return_value={}),
        patch(
            "pysmappee.api.SmappeeLocalApi.load_advanced_config",
            return_value=[{"key": "mdnsHostName", "value": "Smappee1006000212"}],
        ),
        patch(
            "pysmappee.api.SmappeeLocalApi.load_command_control_config", return_value=[]
        ),
        patch(
            "pysmappee.api.SmappeeLocalApi.load_instantaneous",
            return_value=[{"key": "phase0ActivePower", "value": 0}],
        ),
    ):
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            data={"host": "1.2.3.4"},
            unique_id="smappee1006000212",
            source=SOURCE_ZEROCONF,
        )
        config_entry.add_to_hass(hass)
        assert len(hass.config_entries.async_entries(DOMAIN)) == 1

        entry = hass.config_entries.async_entries(DOMAIN)[0]
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        assert not hass.data.get(DOMAIN)


async def test_oauth_implementation_not_available(hass: HomeAssistant) -> None:
    """Test that unavailable OAuth implementation raises ConfigEntryNotReady."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="smappeeCloud",
        source=SOURCE_USER,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "mock-access-token",
                "refresh_token": "mock-refresh-token",
                "expires_at": 9999999999,
                "token_type": "Bearer",
            },
        },
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.helpers.config_entry_oauth2_flow.async_get_config_entry_implementation",
        side_effect=ImplementationUnavailableError,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_token_refresh_auth_failure_on_setup(
    hass: HomeAssistant,
    cloud_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test a token refresh auth failure during setup starts a reauth flow."""
    aioclient_mock.post(TOKEN_URL["PRODUCTION"], status=HTTPStatus.UNAUTHORIZED)

    with patch("pysmappee.Smappee.load_service_locations") as mock_load:
        await hass.config_entries.async_setup(cloud_entry.entry_id)
        await hass.async_block_till_done()

    assert cloud_entry.state is ConfigEntryState.SETUP_ERROR
    mock_load.assert_not_called()
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == cloud_entry.entry_id


async def test_token_refresh_server_error_on_setup(
    hass: HomeAssistant,
    cloud_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test a token refresh server error during setup retries setup."""
    aioclient_mock.post(
        TOKEN_URL["PRODUCTION"], status=HTTPStatus.INTERNAL_SERVER_ERROR
    )

    with patch("pysmappee.Smappee.load_service_locations") as mock_load:
        await hass.config_entries.async_setup(cloud_entry.entry_id)
        await hass.async_block_till_done()

    assert cloud_entry.state is ConfigEntryState.SETUP_RETRY
    mock_load.assert_not_called()
    assert not hass.config_entries.flow.async_progress()


async def test_token_refresh_auth_failure_after_setup(
    hass: HomeAssistant,
    cloud_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    requests_mock: requests_mock.Mocker,
) -> None:
    """Test a token refresh auth failure after an API 401 starts a reauth flow."""
    aioclient_mock.post(TOKEN_URL["PRODUCTION"], json=MOCK_TOKEN_RESPONSE)
    with patch("pysmappee.Smappee.load_service_locations"):
        await hass.config_entries.async_setup(cloud_entry.entry_id)
        await hass.async_block_till_done()
    assert cloud_entry.state is ConfigEntryState.LOADED

    hass.config_entries.async_update_entry(
        cloud_entry,
        data={
            **cloud_entry.data,
            "token": {**cloud_entry.data["token"], "expires_at": 0},
        },
    )
    aioclient_mock.clear_requests()
    aioclient_mock.post(TOKEN_URL["PRODUCTION"], status=HTTPStatus.UNAUTHORIZED)
    requests_mock.get(re.compile("servicelocation"), status_code=401)

    smappee_api = cloud_entry.runtime_data.smappee.smappee_api
    with pytest.raises(OAuth2TokenRequestReauthError):
        await hass.async_add_executor_job(smappee_api.get_service_locations)
    await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == cloud_entry.entry_id
