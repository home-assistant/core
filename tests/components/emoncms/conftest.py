"""Fixtures for emoncms integration tests."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest

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
