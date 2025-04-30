"""Fixtures for Fing testing."""

import logging
from unittest.mock import MagicMock

from fing_agent_api import FingAgent
from fing_agent_api.models import DeviceResponse
import pytest

from homeassistant.components.fing.const import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_IP_ADDRESS, CONF_PORT

from tests.common import load_json_object_fixture

_LOGGER = logging.getLogger(__name__)


@pytest.fixture
def mocked_entry():
    """Fixture for mock config entry."""
    return {
        CONF_IP_ADDRESS: "192.168.1.1",  # Mocked IP
        CONF_PORT: "49090",  # Mocked PORT
        CONF_API_KEY: "test_key",  # Mocked KEY
    }


@pytest.fixture
def mocked_fing_agent_new_api():
    """Fixture for mock FingDataFetcher."""
    mockedFingAgent = MagicMock(spec=FingAgent)
    mockedFingAgent.get_devices.return_value = DeviceResponse(
        load_json_object_fixture("device_resp_new_API.json", DOMAIN)
    )
    return mockedFingAgent


@pytest.fixture
def mocked_fing_agent_old_api():
    """Fixture for mock FingDataFetcher."""
    mockedFingAgent = MagicMock(spec=FingAgent)
    mockedFingAgent.get_devices.return_value = DeviceResponse(
        load_json_object_fixture("device_resp_old_API.json", DOMAIN)
    )
    return mockedFingAgent
