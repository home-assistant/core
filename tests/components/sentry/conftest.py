"""Configuration for Sentry tests."""

from typing import Any

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.sentry.const import DOMAIN


@pytest.fixture(name="config_entry")
def config_entry_fixture() -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(domain=DOMAIN, title="Sentry")


@pytest.fixture(name="config")
def config_fixture() -> dict[str, Any]:
    """Create hass config fixture."""
    return {DOMAIN: {"dsn": "http://public@sentry.local/1"}}
