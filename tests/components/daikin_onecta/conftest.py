"""Shared fixtures for the Daikin Onecta integration tests."""

import time

import pytest

from homeassistant.components.daikin_onecta.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

FAKE_ACCESS_TOKEN = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ"
    ".SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
)
FAKE_REFRESH_TOKEN = "test-refresh-token"
FAKE_AUTH_IMPL = "conftest-imported-cred"


@pytest.fixture(name="config_entry")
def mock_config_entry_fixture(hass: HomeAssistant) -> MockConfigEntry:
    """Return a Daikin Onecta config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": "cloud",
            "token": {
                "refresh_token": FAKE_REFRESH_TOKEN,
                "access_token": FAKE_ACCESS_TOKEN,
                "type": "Bearer",
                "expires_at": time.time() + 86400,
            },
        },
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture(name="config_entry_v1_1")
def mock_config_entry_v1_1() -> MockConfigEntry:
    """Return a legacy Daikin Onecta config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": FAKE_AUTH_IMPL,
            "token": {
                "refresh_token": FAKE_REFRESH_TOKEN,
                "access_token": FAKE_ACCESS_TOKEN,
                "type": "Bearer",
                "expires_at": time.time() + 86400,
            },
        },
        minor_version=1,
    )
