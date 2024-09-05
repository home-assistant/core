"""Fixtures for Fing testing."""

import logging
from unittest.mock import MagicMock

from fing_agent_api import FingAgent
import pytest

from homeassistant.components.fing.const import AGENT_IP, AGENT_KEY, AGENT_PORT

from .const import mocked_dev_resp_new_API, mocked_dev_resp_old_API

_LOGGER = logging.getLogger(__name__)


@pytest.fixture
def mocked_entry():
    """Fixture for mock config entry."""
    return {
        "name": "Fing Agent",  # Mocked Name
        AGENT_IP: "192.168.1.1",  # Mocked IP
        AGENT_PORT: "49090",  # Mocked PORT
        AGENT_KEY: "test_key",  # Mocked KEY
    }


@pytest.fixture
def mocked_fing_agent_new_api():
    """Fixture for mock FingDataFetcher."""
    mockedFingAgent = MagicMock(spec=FingAgent)
    mockedFingAgent.get_devices.return_value = mocked_dev_resp_new_API()
    return mockedFingAgent


@pytest.fixture
def mocked_fing_agent_old_api():
    """Fixture for mock FingDataFetcher."""
    mockedFingAgent = MagicMock(spec=FingAgent)
    mockedFingAgent.get_devices.return_value = mocked_dev_resp_old_API()
    return mockedFingAgent
