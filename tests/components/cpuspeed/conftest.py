"""Fixtures for CPU Speed integration tests."""
from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.cpuspeed.const import DOMAIN

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="CPU Speed",
        domain=DOMAIN,
        data={},
        unique_id=DOMAIN,
    )


@pytest.fixture
def mock_cpuinfo_config_flow() -> Generator[MagicMock, None, None]:
    """Return a mocked get_cpu_info.

    It is only used to check thruthy or falsy values, so it is mocked
    to return True.
    """
    with patch(
        "homeassistant.components.cpuspeed.config_flow.cpuinfo.get_cpu_info",
        return_value=True,
    ) as cpuinfo_mock:
        yield cpuinfo_mock


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.cpuspeed.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup
