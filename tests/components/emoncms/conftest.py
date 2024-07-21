"""Fixtures for emoncms integration tests."""

from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.emoncms.const import (
    CONF_EXCLUDE_FEEDID,
    CONF_ONLY_INCLUDE_FEEDID,
    DOMAIN,
)
from homeassistant.const import CONF_API_KEY, CONF_UNIT_OF_MEASUREMENT, CONF_URL

from tests.common import MockConfigEntry

UNITS = ["kWh", "Wh", "W", "V", "A", "VA", "°C", "°F", "K", "Hz", "hPa", ""]


def get_feed(
    number: int, unit: str = "W", value: int = 18.04, timestamp: int = 1665509570
):
    """Generate feed details."""
    return {
        "id": str(number + 1),
        "userid": "1",
        "name": f"parameter {number + 1}",
        "tag": "tag",
        "size": "35809224",
        "unit": unit,
        "time": timestamp,
        "value": value,
    }


FEEDS = []
for i, unit in enumerate(UNITS):
    FEEDS.append(get_feed(i, unit=unit))


FEEDS2 = []
for i, unit in enumerate(UNITS):
    FEEDS2.append(get_feed(i, unit=unit, value=24.04, timestamp=1665509670))

FAILURE_MESSAGE = "client error"

FLOW_RESULT = {
    CONF_API_KEY: "my_api_key",
    CONF_ONLY_INCLUDE_FEEDID: [str(i + 1) for i in range(len(UNITS))],
    CONF_URL: "http://1.1.1.1",
    CONF_EXCLUDE_FEEDID: None,
    CONF_UNIT_OF_MEASUREMENT: None,
}

SENSOR_NAME = "emoncms@1.1.1.1"


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """Mock emoncms config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=SENSOR_NAME,
        data=FLOW_RESULT,
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.emoncms.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


PATH = "homeassistant.components.emoncms"
LIB = "EmoncmsClient"


@pytest.fixture
async def emoncms_client() -> AsyncGenerator[AsyncMock]:
    """Mock pyemoncms success response."""
    with (
        patch(f"{PATH}.{LIB}", autospec=True) as mock_client,
        patch(f"{PATH}.config_flow.{LIB}", new=mock_client),
    ):
        client = mock_client.return_value
        client.async_request.return_value = {"success": True, "message": FEEDS}
        yield client


@pytest.fixture
def emoncms_client_failure(emoncms_client):
    """Mock pyemoncms failure."""
    emoncms_client.async_request.return_value = {
        "success": False,
        "message": FAILURE_MESSAGE,
    }
    return emoncms_client


@pytest.fixture
def emoncms_client_no_feed(emoncms_client):
    """Mock pyemoncms success response with no uuid."""
    emoncms_client.async_request.return_value = {"success": True, "message": []}
    return emoncms_client
