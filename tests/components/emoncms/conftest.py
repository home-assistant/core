"""Fixtures for emoncms integration tests."""

from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.emoncms.const import (
    CONF_EXCLUDE_FEEDID,
    CONF_ONLY_INCLUDE_FEEDID,
    DOMAIN,
)
from homeassistant.const import CONF_API_KEY, CONF_URL

from tests.common import MockConfigEntry

UNITS = ["kWh", "Wh", "W", "V", "A", "VA", "°C", "°F", "K", "Hz", "hPa", ""]


def get_feed(
    number: int, unit: str = "W", value: int = 18.04, timestamp: int = 1665509570
):
    """Generate feed details."""
    return {
        "id": str(number),
        "userid": "1",
        "name": f"parameter {number}",
        "tag": "tag",
        "size": "35809224",
        "unit": unit,
        "time": timestamp,
        "value": value,
    }


FEEDS = [get_feed(i + 1, unit=unit) for i, unit in enumerate(UNITS)]


EMONCMS_FAILURE = {"success": False, "message": "failure"}

FLOW_RESULT = {
    CONF_API_KEY: "my_api_key",
    CONF_ONLY_INCLUDE_FEEDID: [str(i + 1) for i in range(len(UNITS))],
    CONF_URL: "http://1.1.1.1",
    CONF_EXCLUDE_FEEDID: None,
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


@pytest.fixture
async def emoncms_client() -> AsyncGenerator[AsyncMock]:
    """Mock pyemoncms success response."""
    with (
        patch(
            "homeassistant.components.emoncms.sensor.EmoncmsClient", autospec=True
        ) as mock_client,
        patch(
            "homeassistant.components.emoncms.coordinator.EmoncmsClient",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.async_request.return_value = {"success": True, "message": FEEDS}
        yield client
