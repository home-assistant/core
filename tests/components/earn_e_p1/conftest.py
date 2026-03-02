"""Shared fixtures for EARN-E P1 Meter tests."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from homeassistant.components.earn_e_p1.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_HOST = "192.168.1.100"
MOCK_SERIAL = "E0012345678901234"


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create a mock config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"EARN-E P1 ({MOCK_HOST})",
        data={CONF_HOST: MOCK_HOST, "serial": MOCK_SERIAL},
        unique_id=MOCK_SERIAL,
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def mock_setup_entry():
    """Patch async_setup_entry to avoid real UDP sockets in config flow tests."""
    with patch(
        "homeassistant.components.earn_e_p1.async_setup_entry", return_value=True
    ) as mock:
        yield mock
