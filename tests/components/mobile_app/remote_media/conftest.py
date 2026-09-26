"""Fixtures for Remote Now Playing tests."""

from typing import Any

import pytest

from homeassistant.components.mobile_app.const import (
    DATA_CONFIG_ENTRIES,
    DATA_REMOTE_MEDIA_SESSIONS,
    DOMAIN,
)
from homeassistant.components.mobile_app.remote_media.model import RemoteMediaSession
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .const import (
    ENTITY_ID,
    GENERATION,
    PLAYING_ATTRIBUTES,
    PUSH_TOKEN,
    PUSH_URL,
    SEQUENCE,
    SERVER_ID,
    SESSION_ID,
)

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

WEBHOOK_ID = "remote-media-webhook-id"

# A persisted snapshot, for tests that need sticky state to already exist.
STORED_SNAPSHOT: dict[str, Any] = {
    "server_id": SERVER_ID,
    "entity_id": ENTITY_ID,
    "device_name": "Speaker",
    "state": "playing",
    "device_class": None,
    "title": "First",
    "artist": "Artist",
    "album": "Album",
    "content_id": "track-1",
    "duration": 240.0,
    "position": 10.0,
    "position_updated_at_unix": 1788739200.0,
    "volume": 0.4,
    "is_muted": False,
    "features": 84037,
    "artwork_url": None,
}


def session(**overrides: Any) -> RemoteMediaSession:
    """A stored Follow relationship."""
    values: dict[str, Any] = {
        "session_id": SESSION_ID,
        "generation": GENERATION,
        "generation_sequence": SEQUENCE,
        "entity_id": ENTITY_ID,
        "server_id": SERVER_ID,
        "push_token": PUSH_TOKEN,
        "schema_version": 1,
    }
    values.update(overrides)
    return RemoteMediaSession(**values)


def stored_session(**overrides: Any) -> dict[str, Any]:
    """The same relationship as it is persisted, with sticky state."""
    data: dict[str, Any] = {
        **session().as_storage(),
        "last_timestamp": 1788739200,
        "last_snapshot": dict(STORED_SNAPSHOT),
    }
    data.update(overrides)
    return data


def stored_sessions(hass: HomeAssistant, webhook_id: str) -> dict[str, Any]:
    """The persisted sessions for one registration."""
    # pylint: disable-next=home-assistant-use-runtime-data
    return hass.data[DOMAIN][DATA_REMOTE_MEDIA_SESSIONS].get(webhook_id, {})


@pytest.fixture
async def push_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> ConfigEntry:
    """A push-capable Apple registration.

    Built from a `MockConfigEntry` rather than the HTTP registration flow so the relay mock is in
    place before any client session exists.
    """
    entry = MockConfigEntry(
        data={
            "app_data": {"push_token": "COMPANION_TOKEN", "push_url": PUSH_URL},
            "app_id": "io.robbie.HomeAssistant",
            "app_name": "Home Assistant",
            "app_version": "2026.9.1",
            "device_id": "device-1",
            "device_name": "Test iPhone",
            "manufacturer": "Apple",
            "model": "iPhone",
            "os_name": "iOS",
            "os_version": "27.0",
            "secret": "123abc",
            "supports_encryption": False,
            "user_id": "user-1",
            "webhook_id": WEBHOOK_ID,
        },
        domain=DOMAIN,
        source="registration",
        title="Test iPhone",
        version=1,
    )
    entry.add_to_hass(hass)
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()
    # pylint: disable-next=home-assistant-use-runtime-data
    return hass.data[DOMAIN][DATA_CONFIG_ENTRIES][WEBHOOK_ID]


@pytest.fixture
async def local_only_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> ConfigEntry:
    """A registration with no cloud push configuration.

    Local push only, or a build that never asked for push. Core -> relay -> APNs cannot reach it,
    so a Follow relationship for it is stored and left alone rather than watched.
    """
    entry = MockConfigEntry(
        data={
            "app_data": {},
            "app_id": "io.robbie.HomeAssistant",
            "app_name": "Home Assistant",
            "app_version": "2026.9.1",
            "device_id": "device-2",
            "device_name": "Local iPhone",
            "manufacturer": "Apple",
            "model": "iPhone",
            "os_name": "iOS",
            "os_version": "27.0",
            "secret": "123abc",
            "supports_encryption": False,
            "user_id": "user-1",
            "webhook_id": WEBHOOK_ID,
        },
        domain=DOMAIN,
        source="registration",
        title="Local iPhone",
        version=1,
    )
    entry.add_to_hass(hass)
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()
    # pylint: disable-next=home-assistant-use-runtime-data
    return hass.data[DOMAIN][DATA_CONFIG_ENTRIES][WEBHOOK_ID]


@pytest.fixture
def playing_player(hass: HomeAssistant) -> dict[str, Any]:
    """A media player that is playing something."""
    hass.states.async_set(ENTITY_ID, "playing", PLAYING_ATTRIBUTES)
    return dict(PLAYING_ATTRIBUTES)
