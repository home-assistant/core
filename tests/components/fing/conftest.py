"""Fixtures for Fing testing."""

import logging
from unittest.mock import MagicMock, patch

from fing_agent_api.models import AgentInfoResponse, DeviceResponse
import pytest

from homeassistant.components.fing.const import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_IP_ADDRESS, CONF_PORT

from tests.common import Generator, load_fixture, load_json_object_fixture
from tests.conftest import MockConfigEntry

_LOGGER = logging.getLogger(__name__)


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_IP_ADDRESS: "192.168.1.1",
            CONF_PORT: "49090",
            CONF_API_KEY: "test_key",
        },
        unique_id="test_agent_id",
    )


@pytest.fixture
def mocked_fing_agent(api_type: str) -> Generator[MagicMock]:
    """Mock a FingAgent instance depending on api_type."""
    with (
        patch(
            "homeassistant.components.fing.coordinator.FingAgent", autospec=True
        ) as mock_agent,
        patch("homeassistant.components.fing.config_flow.FingAgent", new=mock_agent),
    ):
        instance = mock_agent.return_value
        instance.get_devices.return_value = DeviceResponse(
            load_json_object_fixture(f"device_resp_{api_type}_API.json", DOMAIN)
        )
        instance.get_agent_info.return_value = AgentInfoResponse(
            load_fixture("agent_info_response.xml", DOMAIN)
        )
        yield instance
