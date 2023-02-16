"""Test OTBR Websocket API."""
from unittest.mock import patch

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

from . import BASE_URL

from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import WebSocketGenerator


@pytest.fixture
async def websocket_client(hass, hass_ws_client):
    """Create a websocket client."""
    return await hass_ws_client(hass)


async def test_get_info(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    otbr_config_entry,
    websocket_client,
) -> None:
    """Test async_get_info."""

    mock_response = (
        "0E080000000000010000000300001035060004001FFFE00208F642646DA209B1C00708FDF57B5A"
        "0FE2AAF60510DE98B5BA1A528FEE049D4B4B01835375030D4F70656E5468726561642048410102"
        "25A40410F5DD18371BFD29E1A601EF6FFAD94C030C0402A0F7F8"
    )

    aioclient_mock.get(f"{BASE_URL}/node/dataset/active", text=mock_response)

    await websocket_client.send_json(
        {
            "id": 5,
            "type": "otbr/info",
        }
    )

    msg = await websocket_client.receive_json()
    assert msg["id"] == 5
    assert msg["success"]
    assert msg["result"] == {
        "url": BASE_URL,
        "active_dataset_tlvs": mock_response.lower(),
    }


async def test_get_info_no_entry(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test async_get_info."""
    await async_setup_component(hass, "otbr", {})
    websocket_client = await hass_ws_client(hass)
    await websocket_client.send_json(
        {
            "id": 5,
            "type": "otbr/info",
        }
    )

    msg = await websocket_client.receive_json()
    assert msg["id"] == 5
    assert not msg["success"]
    assert msg["error"]["code"] == "not_loaded"


async def test_get_info_fetch_fails(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    otbr_config_entry,
    websocket_client,
) -> None:
    """Test async_get_info."""
    await async_setup_component(hass, "otbr", {})

    with patch(
        "homeassistant.components.otbr.OTBRData.get_active_dataset_tlvs",
        side_effect=HomeAssistantError,
    ):
        await websocket_client.send_json(
            {
                "id": 5,
                "type": "otbr/info",
            }
        )
        msg = await websocket_client.receive_json()

    assert msg["id"] == 5
    assert not msg["success"]
    assert msg["error"]["code"] == "get_dataset_failed"
