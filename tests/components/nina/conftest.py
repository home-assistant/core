"""Test fixtures for NINA."""

from collections.abc import Generator
from copy import deepcopy
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.nina.const import DOMAIN
from homeassistant.core import HomeAssistant

from .common import DUMMY_CONFIG_ENTRY

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.nina.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Provide a common mock config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="NINA",
        data=deepcopy(DUMMY_CONFIG_ENTRY),
        version=1,
        minor_version=3,
    )

    config_entry.add_to_hass(hass)

    return config_entry
