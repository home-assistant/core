"""Fixtures for Bosch Smart Home Camera tests."""

from collections.abc import AsyncGenerator
from typing import Self
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.application_credentials import (
    DOMAIN as APPLICATION_CREDENTIALS_DOMAIN,
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.bosch_shc_camera.config_flow import (
    CLIENT_ID,
    CLIENT_SECRET,
)
from homeassistant.components.bosch_shc_camera.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


@pytest.fixture(autouse=True)
async def setup_credentials(hass: HomeAssistant) -> None:
    """Register the fixed public OSS OAuth client credential for every test."""
    await async_setup_component(hass, APPLICATION_CREDENTIALS_DOMAIN, {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET, name="Bosch SingleKey ID"),
    )


class _FakeKeycloakResponse:
    """Minimal stand-in for the aiohttp response the token endpoints read."""

    def __init__(self, status: int, payload: dict) -> None:
        self.status = status
        self._payload = payload

    async def json(self) -> dict:
        return self._payload

    async def text(self) -> str:
        return str(self._payload)

    def raise_for_status(self) -> None:
        if self.status >= 400:
            raise RuntimeError(f"HTTP {self.status}")

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None


@pytest.fixture
def mock_bosch_cloud_session() -> AsyncGenerator[MagicMock]:
    """Patch the Bosch cloud session so Keycloak token calls never hit the network.

    cloud_ssl.py builds its own pinned-TLS aiohttp.ClientSession outside of
    `async_create_clientsession`, so the standard `aioclient_mock` fixture
    can't intercept these calls — patch the session factory directly instead.
    """
    session = MagicMock()
    session.post = MagicMock(
        return_value=_FakeKeycloakResponse(
            200,
            {
                "access_token": "mock-access-token",
                "refresh_token": "mock-refresh-token",
                "type": "Bearer",
                "expires_in": 60,
            },
        )
    )
    # The config-flow's post-login camera-access verification GETs
    # /v11/video_inputs with the fresh token — default to a healthy 200 so
    # tests that aren't specifically exercising that check don't need their
    # own GET stub.
    session.get = MagicMock(return_value=_FakeKeycloakResponse(200, {}))
    with patch(
        "homeassistant.components.bosch_shc_camera.config_flow.async_get_bosch_cloud_session",
        AsyncMock(return_value=session),
    ):
        yield session


@pytest.fixture(autouse=True)
def mock_local_stream_start() -> AsyncGenerator[AsyncMock]:
    """Prevent BoschCamera.async_added_to_hass from opening a real LOCAL session.

    Every full config-entry setup spawns a background task that calls
    `local_stream.async_start_local_stream`, which opens a real aiohttp
    connection — blocked by this test suite's socket guard. Tests that
    specifically exercise LOCAL-stream behavior override this patch's
    return value or side effect themselves.
    """
    with patch(
        "homeassistant.components.bosch_shc_camera.camera.async_start_local_stream",
        AsyncMock(return_value=None),
    ) as mock_start:
        yield mock_start


@pytest.fixture
def mock_setup_entry() -> AsyncGenerator[AsyncMock]:
    """Mock setting up a config entry so the flow test doesn't run real setup."""
    with patch(
        "homeassistant.components.bosch_shc_camera.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup
