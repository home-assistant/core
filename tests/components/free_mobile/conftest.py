"""Fixtures for the Free Mobile integration tests."""

from collections.abc import Generator
from http import HTTPStatus
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.free_mobile.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import MOCK_CONFIG

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_send_sms() -> Generator[MagicMock]:
    """Mock the Free Mobile SMS client's send_sms call."""
    with patch("freesms.FreeClient.send_sms") as mock:
        mock.return_value = MagicMock(status_code=HTTPStatus.OK)
        yield mock


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create a Free Mobile config entry."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    entry.add_to_hass(hass)
    return entry
