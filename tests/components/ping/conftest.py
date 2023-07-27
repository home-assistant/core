"""Fixtures for ping."""
import os
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant import setup
from homeassistant.components.device_tracker import legacy
from homeassistant.components.ping.const import DOMAIN
from homeassistant.core import HomeAssistant


@pytest.fixture(name="mock_ping")
def mock_icmplib_ping() -> None:
    """Mock icmplib.ping."""
    with patch("homeassistant.components.ping.icmp_ping"), patch(
        "homeassistant.components.ping.binary_sensor.async_ping"
    ), patch("homeassistant.components.ping.device_tracker.async_multiping"):
        yield


@pytest.fixture(name="yaml_devices")
def mock_yaml_devices(hass: HomeAssistant):
    """Get a path for storing yaml devices."""
    yaml_devices = hass.config.path(legacy.YAML_DEVICES)
    if os.path.isfile(yaml_devices):
        os.remove(yaml_devices)
    yield yaml_devices
    if os.path.isfile(yaml_devices):
        os.remove(yaml_devices)


@pytest.fixture(name="get_config")
async def get_config_to_integration_load() -> dict[str, Any]:
    """Return default configuration.

    To override the config, tests can be marked with:
    @pytest.mark.parametrize("get_config", [{...}])
    """

    return {
        "ping": [
            {
                "host": "127.0.0.1",
                "binary_sensor": {
                    "name": "Test binary sensor",
                },
                "device_tracker": {
                    "name": "Test device tracker",
                },
            }
        ]
    }


@pytest.fixture(name="load_yaml_integration")
async def load_int(
    hass: HomeAssistant, get_config: dict[str, Any], mock_ping: None, yaml_devices: None
) -> None:
    """Set up the ping integration in Home Assistant."""
    await setup.async_setup_component(
        hass,
        DOMAIN,
        get_config,
    )
    await hass.async_block_till_done()
