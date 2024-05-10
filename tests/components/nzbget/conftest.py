"""Define fixtures available for all tests."""

from unittest.mock import MagicMock, patch

import pytest

from . import MOCK_HISTORY, MOCK_STATUS, MOCK_VERSION


@pytest.fixture
def nzbget_api(hass):
    """Mock NZBGetApi for easier testing."""
    with patch("homeassistant.components.nzbget.coordinator.NZBGetAPI") as mock_api:
        instance = mock_api.return_value

        instance.history = MagicMock(return_value=list(MOCK_HISTORY))
        instance.pausedownload = MagicMock(return_value=True)
        instance.resumedownload = MagicMock(return_value=True)
        instance.status = MagicMock(return_value=MOCK_STATUS.copy())
        instance.version = MagicMock(return_value=MOCK_VERSION)

        yield mock_api
