"""OPNsense session fixtures."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.opnsense.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import CONFIG_DATA, setup_mock_diagnostics

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return the default mocked config entry."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_DATA,
    )
    mock_config_entry.add_to_hass(hass)
    return mock_config_entry


@pytest.fixture
def mock_diagnostics() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.opnsense.config_flow.diagnostics"
    ) as mock_diagnostics:
        setup_mock_diagnostics(mock_diagnostics)
        yield mock_diagnostics


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.opnsense.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
