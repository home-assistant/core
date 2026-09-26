"""Shared values for Remote Now Playing tests."""

SERVER_ID = "home"
ENTITY_ID = "media_player.speaker"
# Apple's identifier for the session. Core treats it as opaque and never parses it: this happens
# to be what the app builds today ("{utf8 byte count of serverId}:{serverId}{entityId}"), and the
# tests use a realistic value precisely to prove that nothing here depends on its shape.
SESSION_ID = "4:homemedia_player.speaker"
GENERATION = "11111111-2222-3333-4444-555555555555"
LATER_GENERATION = "99999999-8888-7777-6666-555555555555"
SEQUENCE = 10
LATER_SEQUENCE = 11
# 80 bytes, the length observed on the platform this was measured on.
PUSH_TOKEN = "40" + "ab" * 79
LATER_PUSH_TOKEN = "41" + "cd" * 79

PUSH_URL = "http://localhost/mock-push"


def registration_payload(**overrides):
    """Return a remote_media_session_token payload.

    The exact keys the iOS `RemoteMediaSessionRegistration.CodingKeys` produce. Asserted literally
    in `test_webhook.py` against `RemoteMediaRegistrationRequestTests` on the app side.
    """
    payload = {
        "session_id": SESSION_ID,
        "server_id": SERVER_ID,
        "entity_id": ENTITY_ID,
        "generation": GENERATION,
        "generation_sequence": SEQUENCE,
        "push_token": PUSH_TOKEN,
        "schema_version": 1,
    }
    payload.update(overrides)
    return payload


def dismissal_payload(**overrides):
    """Return a remote_media_session_dismissed payload."""
    payload = {
        "session_id": SESSION_ID,
        "generation": GENERATION,
        "generation_sequence": SEQUENCE,
    }
    payload.update(overrides)
    return payload


PLAYING_ATTRIBUTES = {
    "friendly_name": "Speaker",
    "media_content_id": "track-1",
    "media_title": "First",
    "media_artist": "Artist",
    "media_album_name": "Album",
    "media_duration": 240,
    "media_position": 10,
    "media_position_updated_at": "2026-09-07T00:00:00+00:00",
    "volume_level": 0.4,
    "is_volume_muted": False,
    "supported_features": 84037,
    "entity_picture": "/api/media_player_proxy/media_player.speaker?token=secret",
}
