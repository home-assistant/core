"""Test the Diagnostics integration."""
from unittest.mock import AsyncMock, Mock

import pytest

from homeassistant.components.websocket_api.const import TYPE_RESULT
from homeassistant.setup import async_setup_component

from . import get_diagnostics_for_config_entry

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
                    "hello": "info",
                }
            ),
        ),
    )
    assert await async_setup_component(hass, "diagnostics", {})


async def test_websocket_info(hass, hass_ws_client):
    """Test camera_thumbnail websocket command."""
    client = await hass_ws_client(hass)
    await client.send_json({"id": 5, "type": "diagnostics/list"})

    msg = await client.receive_json()

    assert msg["id"] == 5
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    assert msg["result"] == [
        {"domain": "fake_integration", "handlers": {"config_entry": True}}
    ]


async def test_download_diagnostics(hass, hass_client):
    """Test record service."""
    assert await get_diagnostics_for_config_entry(
        hass, hass_client, "fake_integration"
    ) == {"hello": "info"}
