"""Fixtures for Whois integration tests."""
from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.whois.const import DOMAIN
from homeassistant.const import CONF_DOMAIN

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="Home Assistant",
        domain=DOMAIN,
        data={
            CONF_DOMAIN: "Home-Assistant.io",
        },
        unique_id="home-assistant.io",
    )


@pytest.fixture
def mock_whois_config_flow() -> Generator[MagicMock, None, None]:
    """Return a mocked whois."""
    with patch("homeassistant.components.whois.config_flow.whois.query") as whois_mock:
        yield whois_mock


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.whois.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup
