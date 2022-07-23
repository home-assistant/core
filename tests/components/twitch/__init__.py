"""Tests for the Twitch integration."""

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"

TWITCH_USER = {
    "id": "123",
    "login": "test",
    "display_name": "Test",
    "type": "user",
    "broadcaster_type": "",
    "description": "",
    "profile_image_url": "",
    "offline_image_url": "",
    "view_count": 0,
    "created_at": "",
}

TWITCH_FOLLOWER = {
    "from_id": "123",
    "from_login": "test",
    "from_name": "Test",
    "to_id": "456",
    "to_login": "test2",
    "to_name": "Test 2",
    "followed_at": "2022-01-01T00:00:00Z",
}

CHANNELS = ["123", "456"]


def create_response(data: list) -> dict:
    """Create a response."""
    return {
        "data": data,
        "total": len(data),
    }
