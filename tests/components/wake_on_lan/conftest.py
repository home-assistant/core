"""Test fixtures for Wake on Lan."""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import setup
from homeassistant.components.wake_on_lan.const import DOMAIN
from homeassistant.core import HomeAssistant


@pytest.fixture
def mock_send_magic_packet() -> AsyncMock:
    """Mock magic packet."""
    with patch("wakeonlan.send_magic_packet") as mock_send:
        yield mock_send


@pytest.fixture(name="get_config")
async def get_config_to_integration_load() -> dict[str, Any]:
    """Return default configuration.

    To override the config, tests can be marked with:
    @pytest.mark.parametrize("get_config", [{...}]).
    """

    return {
        "wake_on_lan": [
            {
                "switch": {
                    "mac": "00:01:02:03:04:05",
                    "name": "Test WOL 1",
                    "host": "127.0.0.1",
                }
            },
            {
                "switch": {
                    "mac": "00:01:02:03:04:06",
                    "name": "Test WOL 2",
                }
            },
        ]
    }


@pytest.fixture(name="load_yaml_integration")
async def load_int(
    hass: HomeAssistant, get_config: dict[str, Any], mock_send_magic_packet: AsyncMock
) -> None:
    """Set up the WOL integration in Home Assistant."""
    await setup.async_setup_component(
        hass,
        DOMAIN,
        get_config,
    )
    await hass.async_block_till_done()
