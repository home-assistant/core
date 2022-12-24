import pytest

from homeassistant.components.mastodon import DOMAIN


@pytest.fixture
def mastodon_config():
    return {
        "name": "test_mastodon",
        "platform": DOMAIN,
        "access_token": "0ABC",
        "client_id": "0XYZ-UVW",
        "client_secret": "0KLM",
    }
