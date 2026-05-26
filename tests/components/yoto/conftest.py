"""Fixtures for the Yoto integration tests."""

from collections.abc import Generator
from datetime import UTC, datetime
import time
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
from yoto_api import (
    Card,
    Device,
    PlaybackEvent,
    PlaybackStatus,
    PlayerInfo,
    PlayerStatus,
    YotoPlayer,
)

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


def _build_card() -> Card:
    """Build a representative Yoto library card."""
    return Card(
        id=CARD_ID,
        title="Outer Space",
        author="Ladybird Audio Adventures",
        cover_image_large="https://example.test/cover.jpg",
    )


def _build_player() -> YotoPlayer:
    """Build a representative Yoto player for tests."""
    now = datetime(2026, 5, 8, 12, 0, tzinfo=UTC)
    player = YotoPlayer(
        device=Device(
            device_id=PLAYER_ID,
            name="Nursery Yoto",
            device_type="v3",
            device_family="v3",
            generation="gen3",
        ),
        devices_refreshed_at=now,
        info_refreshed_at=now,
        last_event_received_at=now,
    )
    player.info = PlayerInfo(
        device_id=PLAYER_ID,
        firmware_version="v2.17.5",
        mac="aa:bb:cc:dd:ee:ff",
    )
    player.status = PlayerStatus(device_id=PLAYER_ID, is_online=True)
    player.last_event = PlaybackEvent(
        player_id=PLAYER_ID,
        playback_status=PlaybackStatus.PLAYING,
        volume=8,
        volume_max=16,
        track_length=300,
        position=120,
        card_id=CARD_ID,
        chapter_key="01",
        chapter_title="Chapter 1",
        track_key="01-INT",
        track_title="Introduction",
    )
    return player


@pytest.fixture
def mock_token_hex() -> Generator[MagicMock]:
    """Pin the access token used for proxy URLs to keep snapshots stable."""
    with patch("secrets.token_hex", return_value="abcdef") as token:
        yield token


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Bypass the integration setup so the config flow can be tested in isolation."""
    with patch(
        "homeassistant.components.yoto.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_yoto_client() -> Generator[MagicMock]:
    """Patch YotoClient used by the runtime to a configurable mock."""
    with patch(
        "homeassistant.components.yoto.coordinator.YotoClient", autospec=True
    ) as client_class:
        client = client_class.return_value
        client.players = {PLAYER_ID: _build_player()}
        client.library = {CARD_ID: _build_card()}
        client.token = MagicMock(refresh_token="mock-refresh-token")
        yield client


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
