"""Fixtures for the Yoto integration tests."""

from collections.abc import Generator
from datetime import UTC, datetime
import time
from unittest.mock import MagicMock, patch

import jwt
import pytest
from yoto_api import YotoPlayer
from yoto_api.Card import Card

from homeassistant.components.application_credentials import (
    DOMAIN as APPLICATION_CREDENTIALS_DOMAIN,
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.yoto.const import DOMAIN, YOTO_SCOPES
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

USER_ID = "auth0|user-test"
PLAYER_ID = "player-test"
CARD_ID = "card-test"
SCOPES = " ".join(YOTO_SCOPES)
ACCESS_TOKEN = jwt.encode({"sub": USER_ID}, "test-secret-long-enough-for-hmac-sha256")


def _build_player() -> YotoPlayer:
    """Build a representative Yoto player for tests."""
    return YotoPlayer(
        id=PLAYER_ID,
        name="Nursery Yoto",
        device_type="v3",
        device_family="v3",
        generation="gen3",
        online=True,
        firmware_version="v2.17.5",
        playback_status="playing",
        volume=8,
        track_length=300,
        track_position=120,
        track_title="Introduction",
        chapter_title="Chapter 1",
        card_id=CARD_ID,
        chapter_key="01",
        track_key="01-INT",
        last_updated_at=datetime(2026, 5, 8, 12, 0, tzinfo=UTC),
    )


def _build_card() -> Card:
    """Build a representative Yoto library card."""
    return Card(
        id=CARD_ID,
        title="Outer Space",
        author="Ladybird Audio Adventures",
        cover_image_large="https://example.test/cover.jpg",
    )


@pytest.fixture
def mock_token_hex() -> Generator[MagicMock]:
    """Pin the access token used for proxy URLs to keep snapshots stable."""
    with patch("secrets.token_hex", return_value="abcdef") as token:
        yield token


@pytest.fixture
def mock_yoto_manager() -> Generator[MagicMock]:
    """Patch YotoManager used by the runtime to a configurable MagicMock."""
    with patch(
        "homeassistant.components.yoto.coordinator.YotoManager",
    ) as manager_class:
        manager = MagicMock()
        manager_class.return_value = manager

        manager.players = {PLAYER_ID: _build_player()}
        manager.library = {CARD_ID: _build_card()}
        manager.token = MagicMock(refresh_token="mock-refresh-token")
        manager.mqtt_client = MagicMock()

        yield manager


@pytest.fixture(name="expires_at")
def mock_expires_at() -> float:
    """Fixture to set the OAuth token expiration time."""
    return time.time() + 3600


@pytest.fixture
def mock_config_entry(expires_at: float) -> MockConfigEntry:
    """Return a Yoto OAuth2 config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Yoto",
        unique_id=USER_ID,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": ACCESS_TOKEN,
                "refresh_token": "mock-refresh-token",
                "expires_at": expires_at,
                "expires_in": 3600,
                "token_type": "Bearer",
                "scope": SCOPES,
            },
        },
        entry_id="01J5TX5A0FF6G5V0QJX6HBC94T",
    )


@pytest.fixture
async def setup_credentials(hass: HomeAssistant) -> None:
    """Register fake OAuth2 client credentials for the Yoto integration."""
    assert await async_setup_component(hass, APPLICATION_CREDENTIALS_DOMAIN, {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential("CLIENT_ID", "CLIENT_SECRET"),
        DOMAIN,
    )
