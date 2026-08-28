"""Tests for the Discogs integration."""

from contextlib import contextmanager
from unittest.mock import patch

MOCK_TOKEN = "test_token_123"
MOCK_USERNAME = "testuser"


@contextmanager
def patch_discogs_client(mock_client):
    """Patch the discogs_client.Client constructor."""
    with patch(
        "homeassistant.components.discogs.config_flow.discogs_client.Client",
        return_value=mock_client,
    ):
        yield


@contextmanager
def patch_setup_entry():
    """Patch async_setup_entry."""
    with patch(
        "homeassistant.components.discogs.async_setup_entry", return_value=True
    ) as mock:
        yield mock
