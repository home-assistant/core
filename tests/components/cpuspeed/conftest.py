"""Fixtures for CPU Speed integration tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.cpuspeed.const import DOMAIN
from homeassistant.core import HomeAssistant

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

    It is only used to check truthy or falsy values, so it is mocked
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


@pytest.fixture
def mock_cpuinfo() -> Generator[MagicMock, None, None]:
    """Return a mocked get_cpu_info."""
    info = {
        "hz_actual": (3200000001, 0),
        "arch_string_raw": "aargh",
        "brand_raw": "Intel Ryzen 7",
        "hz_advertised": (3600000001, 0),
    }

    with patch(
        "homeassistant.components.cpuspeed.cpuinfo.get_cpu_info",
        return_value=info,
    ) as cpuinfo_mock:
        yield cpuinfo_mock


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_cpuinfo: MagicMock
) -> MockConfigEntry:
    """Set up the CPU Speed integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
