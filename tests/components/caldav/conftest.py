"""Test fixtures for caldav."""

from typing import Any
from unittest.mock import Mock, patch

import pytest

from homeassistant.components.caldav.const import DOMAIN
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    Platform,
)

from tests.common import MockConfigEntry

TEST_URL = "https://example.com/url-1"
TEST_USERNAME = "username-1"
TEST_PASSWORD = "password-1"

CONF_LEGACY_ENTITY_NAMES = "legacy_entity_names"
CONF_READ_ONLY = "read_only"


@pytest.fixture(name="platforms")
def mock_platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return []


@pytest.fixture(autouse=True)
async def mock_patch_platforms(platforms: list[str]) -> Any:
    """Fixture to set up the integration."""
    with patch(f"homeassistant.components.{DOMAIN}.PLATFORMS", platforms):
        yield


@pytest.fixture(name="calendars")
def mock_calendars() -> list[Mock]:
    """Fixture to provide calendars returned by CalDAV client."""
    return []


@pytest.fixture(name="dav_client", autouse=True)
def mock_dav_client(calendars: list[Mock]) -> Mock:  # pyright: ignore[reportInvalidTypeForm]
    """Fixture to mock the DAVClient."""
    with patch(
        "homeassistant.components.caldav.calendar.caldav.DAVClient"
    ) as mock_client:
        mock_client.return_value.principal.return_value.calendars.return_value = (
            calendars
        )
        yield mock_client


@pytest.fixture(name="config_entry")
def mock_config_entry() -> MockConfigEntry:
    """Fixture for a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_URL: TEST_URL,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_VERIFY_SSL: True,
            CONF_LEGACY_ENTITY_NAMES: True,
            CONF_READ_ONLY: False,
        },
    )
