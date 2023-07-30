"""The test for the ping binary_sensor platform."""
from unittest.mock import patch

import pytest

from homeassistant import setup
from homeassistant.core import HomeAssistant


@pytest.fixture
def mock_ping() -> None:
    """Mock icmplib.ping."""
    with patch("homeassistant.components.ping.icmp_ping"):
        yield


async def test_setup(hass: HomeAssistant, mock_ping: None) -> None:
    """Verify we can set up the ping sensor."""

    await setup.async_setup_component(
        hass,
        "binary_sensor",
        {
            "binary_sensor": {
                "platform": "ping",
                "name": "test",
                "host": "127.0.0.1",
                "count": 1,
            }
        },
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1

    assert hass.states.get("binary_sensor.test")
