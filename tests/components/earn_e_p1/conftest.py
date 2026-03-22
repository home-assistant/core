"""Shared fixtures for EARN-E P1 Meter tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.const import CONF_HOST
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.earn_e_p1.const import DOMAIN

MOCK_HOST = "192.168.1.100"
MOCK_SERIAL = "E0012345678901234"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Enable custom integrations in all tests."""


@pytest.fixture(autouse=True)
def mock_listener():
    """Mock EarnEP1Listener to avoid real UDP sockets."""
    with patch("custom_components.earn_e_p1.EarnEP1Listener") as mock_cls:
        instance = MagicMock()
        instance.start = AsyncMock()
        instance.stop = AsyncMock()
        instance.register = MagicMock()
        instance.unregister = MagicMock()
        mock_cls.return_value = instance
        yield instance


@pytest.fixture
def mock_config_entry(hass):
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
    """Patch async_setup_entry to avoid real setup in config flow tests."""
    with patch(
        "custom_components.earn_e_p1.async_setup_entry", return_value=True
    ) as mock:
        yield mock
