"""Fixtures for tests."""
from collections.abc import Awaitable, Callable, Coroutine
import time
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.withings.const import DOMAIN
from homeassistant.config import async_process_ha_core_config
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import MockWithings
from .common import ComponentFactory

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

ComponentSetup = Callable[[], Awaitable[MockWithings]]

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"
SCOPES = [
    "user.info",
    "user.metrics",
    "user.activity",
    "user.sleepevents",
]
TITLE = "henk"
USER_ID = 12345
WEBHOOK_ID = "55a7335ea8dee830eed4ef8f84cda8f6d80b83af0847dc74032e86120bffed5e"


@pytest.fixture
def component_factory(
    hass: HomeAssistant,
    hass_client_no_auth,
    aioclient_mock: AiohttpClientMocker,
    current_request_with_host: None,
):
    """Return a factory for initializing the withings component."""
    with patch(
        "homeassistant.components.withings.common.ConfigEntryWithingsApi"
    ) as api_class_mock:
        yield ComponentFactory(
            hass, api_class_mock, hass_client_no_auth, aioclient_mock
        )


@pytest.fixture(name="scopes")
def mock_scopes() -> list[str]:
    """Fixture to set the scopes present in the OAuth token."""
    return SCOPES


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
def mock_expires_at() -> int:
    """Fixture to set the oauth token expiration time."""
    return time.time() + 3600


@pytest.fixture(name="config_entry")
def mock_config_entry(expires_at: int, scopes: list[str]) -> MockConfigEntry:
    """Create Withings entry in Home Assistant."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=TITLE,
        unique_id=str(USER_ID),
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "status": 0,
                "userid": str(USER_ID),
                "access_token": "mock-access-token",
                "refresh_token": "mock-refresh-token",
                "expires_at": expires_at,
                "scope": ",".join(scopes),
            },
            "profile": TITLE,
            "use_webhook": True,
            "webhook_id": WEBHOOK_ID,
        },
    )


@pytest.fixture(name="setup_integration")
async def mock_setup_integration(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> Callable[[], Coroutine[Any, Any, MockWithings]]:
    """Fixture for setting up the component."""
    config_entry.add_to_hass(hass)

    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET),
        DOMAIN,
    )
    await async_process_ha_core_config(
        hass,
        {"internal_url": "http://example.local:8123"},
    )

    async def func() -> MockWithings:
        mock = MockWithings()
        with patch(
            "homeassistant.components.withings.common.ConfigEntryWithingsApi",
            return_value=mock,
        ):
            assert await async_setup_component(hass, DOMAIN, {})
            await hass.async_block_till_done()
        return mock

    return func
