"""The tests for the analytics ."""
from unittest.mock import patch

import pytest

from homeassistant.components.analytics.const import ANALYTICS_ENDPOINT_URL, DOMAIN
from homeassistant.setup import async_setup_component

MOCK_HUUID = "abcdefg"


@pytest.fixture(name="mock_get_huuid", autouse=True)
def mock_get_huuid_fixture():
    """Fixture to mock get huuid."""
    with patch("homeassistant.helpers.instance_id.async_get") as mock:
        yield mock


async def test_setup(hass, mock_get_huuid):
    """Test setup of the integration."""
    mock_get_huuid.return_value = MOCK_HUUID
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()

    assert hass.data[DOMAIN].huuid == MOCK_HUUID


async def test_websocket(hass, mock_get_huuid, hass_ws_client, aioclient_mock):
    """Test websocekt commands."""
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL, status=200)
    mock_get_huuid.return_value = MOCK_HUUID
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json({"id": 1, "type": "analytics"})
    response = await ws_client.receive_json()

    assert response["success"]
    assert response["result"]["huuid"] == MOCK_HUUID

    await ws_client.send_json(
        {"id": 2, "type": "analytics/preferences", "preferences": ["base"]}
    )
    response = await ws_client.receive_json()
    assert len(aioclient_mock.mock_calls) == 1
    assert response["result"]["preferences"] == ["base"]

    await ws_client.send_json({"id": 3, "type": "analytics"})
    response = await ws_client.receive_json()
    assert response["result"]["preferences"] == ["base"]
