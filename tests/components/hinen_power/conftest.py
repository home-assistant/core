"""Configure tests for the Hinen integration."""

from collections.abc import Awaitable, Callable, Coroutine
import time
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.hinen_power.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import MockHinen

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

type ComponentSetup = Callable[[], Awaitable[MockHinen]]

CLIENT_ID = "6liMmES7"
CLIENT_SECRET = "test_client_secret"
PAGE_LANGUAGE = "en_US"
AUTH_URL = "https://global.knowledge.celinksmart.com/#/auth"
TOKEN_URL = (
    "https://global.iot-api.celinksmart.com/iot-global/open-platforms/auth/token"
)
REDIRECTION_URL = "https://example.com/auth/hinen/callback"
REGION_CODE = "region_code"
HOST = "https://dev-iot-api.celinksmart.cn"
TITLE = "Test Hinen Device"
TOKEN = "homeassistant.components.hinen_power.api.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid"


@pytest.fixture(autouse=True)
async def setup_credentials(hass: HomeAssistant) -> None:
    """Fixture to setup credentials."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET),
        DOMAIN,
    )


@pytest.fixture(name="expires_at")
def mock_expires_at() -> float:
    """Fixture to set the oauth token expiration time."""
    return time.time() + 3600


@pytest.fixture(name="config_entry")
def mock_config_entry(expires_at: int) -> MockConfigEntry:
    """Create Hinen entry in Home Assistant."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=TITLE,
        unique_id="device_12345",
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "account_id": 12345678,
                "access_token": "mock-access-token",
                "refresh_token": "mock-refresh-token",
                "expires_in": 6000,
                "expires_at": expires_at,
                "access_token_expiration": 12345678,
                "host": "https://dev-iot-api.celinksmart.cn",
                "client_secret": "test_client_secret",
                "region_code": "CN",
            },
        },
        options={"devices": ["device_12345"]},
    )


@pytest.fixture(autouse=True)
def mock_connection(aioclient_mock: AiohttpClientMocker) -> None:
    """Mock Hinen connection."""
    aioclient_mock.get(
        TOKEN_URL,
        json={
            "data": {
                "account_id": 12345678,
                "access_token": "mock-access-token",
                "refresh_token": "mock-refresh-token",
                "expires_in": 6000,
                "access_token_expiration": 12345678,
                "host": "https://dev-iot-api.celinksmart.cn",
                "client_secret": "test_client_secret",
                "region_code": "CN",
            }
        },
    )

    # Mock country list API
    aioclient_mock.get(
        "https://global.knowledge.celinksmart.com/prod-api/iot-global/app-api/countries",
        json={
            "data": [
                {"code": "CN", "name": "中国"},
                {"code": "US", "name": "United States"},
                {"code": "JP", "name": "日本"},
                {"code": "GB", "name": "United Kingdom"},
            ]
        },
    )


@pytest.fixture(name="setup_integration")
async def mock_setup_integration(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> Callable[[], Coroutine[Any, Any, MockHinen]]:
    """Fixture for setting up the component."""
    config_entry.add_to_hass(hass)

    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET),
        DOMAIN,
    )

    async def func() -> MockHinen:
        mock = MockHinen(hass)
        with (
            patch(
                "homeassistant.components.hinen_power.AsyncConfigEntryAuth.get_resource",
                return_value=mock,
            ),
            patch(
                "homeassistant.components.hinen_power.AsyncConfigEntryAuth.hinen_open",
                new=mock,
            ),
        ):
            assert await async_setup_component(hass, DOMAIN, {})
            await hass.async_block_till_done()
        return mock

    return func
