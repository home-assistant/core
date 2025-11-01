"""Test configuration for dreo integration."""

from __future__ import annotations

import pytest

from homeassistant.components.dreo.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry

MOCK_DEVICE_ID1 = "test-device-id"
MOCK_DEVICE_ID2 = "test-device-id-2"


@pytest.fixture
def mock_config_entry():
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Test Dreo",
        data={
            CONF_USERNAME: "test@example.com",
            CONF_PASSWORD: "password",
        },
        source=SOURCE_USER,
        entry_id="test",
        unique_id="test@example.com",
    )
