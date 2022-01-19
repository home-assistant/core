"""Test the Diagnostics integration."""
from unittest.mock import AsyncMock, Mock

import pytest

from homeassistant.components.websocket_api.const import TYPE_RESULT
from homeassistant.setup import async_setup_component

from . import get_diagnostics_for_config_entry, get_diagnostics_for_device

from tests.common import mock_platform


@pytest.fixture(autouse=True)
async def mock_diagnostics_integration(hass):
    """Mock a diagnostics integration."""
    hass.config.components.add("fake_integration")
    mock_platform(
        hass,
        "fake_integration.diagnostics",
        Mock(
            async_get_config_entry_diagnostics=AsyncMock(
                return_value={
                    "config_entry": "info",
                }
            ),
            async_get_device_diagnostics=AsyncMock(
                return_value={
                    "device": "info",
                }
            ),
        ),
    )
    assert await async_setup_component(hass, "diagnostics", {})


async def test_websocket(hass, hass_ws_client):
    """Test websocket command."""
    client = await hass_ws_client(hass)
    await client.send_json({"id": 5, "type": "diagnostics/list"})

    msg = await client.receive_json()

    assert msg["id"] == 5
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    assert msg["result"] == [
        {
            "domain": "fake_integration",
            "handlers": {"config_entry": True, "device": True},
        }
    ]

    await client.send_json(
        {"id": 6, "type": "diagnostics/get", "domain": "fake_integration"}
    )

    msg = await client.receive_json()

    assert msg["id"] == 6
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    assert msg["result"] == {
        "domain": "fake_integration",
        "handlers": {"config_entry": True, "device": True},
    }


async def test_download_diagnostics(hass, hass_client):
    """Test download diagnostics."""
    assert await get_diagnostics_for_config_entry(
        hass, hass_client, "fake_integration"
    ) == {"config_entry": "info"}

    assert await get_diagnostics_for_device(hass, hass_client, "fake_integration") == {
        "device": "info"
    }
