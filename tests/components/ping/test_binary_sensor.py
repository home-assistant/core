"""The test for the ping binary_sensor platform."""
from unittest.mock import patch

import pytest

from homeassistant import config as hass_config, setup
from homeassistant.components.ping import DOMAIN
from homeassistant.const import SERVICE_RELOAD
from homeassistant.core import HomeAssistant

from tests.common import get_fixture_path


@pytest.fixture
def mock_ping() -> None:
    """Mock icmplib.ping."""
    with patch("homeassistant.components.ping.icmp_ping"):
        yield


async def test_reload(hass: HomeAssistant, mock_ping: None) -> None:
    """Verify we can reload trend sensors."""

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

    yaml_path = get_fixture_path("configuration.yaml", "ping")
    with patch.object(hass_config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1

    assert hass.states.get("binary_sensor.test") is None
    assert hass.states.get("binary_sensor.test2")
