"""Test OTBR Websocket API."""
import pytest

from homeassistant.core import HomeAssistant

from . import BASE_URL

from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture
async def websocket_client(hass, hass_ws_client):
    """Create a websocket client."""
    return await hass_ws_client(hass)


async def test_get_active_dataset_tlvs(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    thread_config_entry,
    websocket_client,
):
    """Test async_get_active_dataset_tlvs."""

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
