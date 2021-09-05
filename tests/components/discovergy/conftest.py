"""Fixtures for Ambee integration tests."""
import pytest

from homeassistant.components.discovergy.const import (
    CONF_ACCESS_TOKEN,
    CONF_ACCESS_TOKEN_SECRET,
    CONF_CONSUMER_KEY,
    CONF_CONSUMER_SECRET,
    DOMAIN,
)
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="test@example.com",
        domain=DOMAIN,
        data={
            CONF_EMAIL: "test@example.com",
            CONF_PASSWORD: "test-password",
            CONF_ACCESS_TOKEN: "rq-test-token",
            CONF_ACCESS_TOKEN_SECRET: "rq-test-token-secret",
            CONF_CONSUMER_KEY: "test-key",
            CONF_CONSUMER_SECRET: "test-secret",
        },
        unique_id="unique_thingy",
    )
