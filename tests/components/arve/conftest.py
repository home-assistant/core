"""Common fixtures for the Arve tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.arve.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import USER_INPUT

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.arve.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry(hass: HomeAssistant, mock_arve: MagicMock) -> MockConfigEntry:
    """Return the default mocked config entry."""
    entry = MockConfigEntry(title="Arve", domain=DOMAIN, data=USER_INPUT)
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def mock_arve():
    """Return a mocked Arve client."""

    with patch(
        "homeassistant.components.arve.coordinator.Arve", autospec=True
    ) as arve_mock, patch(
        "homeassistant.components.arve.config_flow.Arve", new=arve_mock
    ):
        arve = arve_mock.return_value
        arve.device_sn = "test-serial-number"

        yield arve
