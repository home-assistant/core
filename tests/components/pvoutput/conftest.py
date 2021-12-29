"""Fixtures for PVOutput integration tests."""
from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.pvoutput.const import CONF_SYSTEM_ID, DOMAIN
from homeassistant.const import CONF_API_KEY

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="12345",
        domain=DOMAIN,
        data={CONF_API_KEY: "tskey-MOCK", CONF_SYSTEM_ID: 12345},
        unique_id="12345",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.pvoutput.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_pvoutput_config_flow() -> Generator[None, MagicMock, None]:
    """Return a mocked PVOutput client."""
    with patch(
        "homeassistant.components.pvoutput.config_flow.PVOutput", autospec=True
    ) as pvoutput_mock:
        yield pvoutput_mock.return_value
