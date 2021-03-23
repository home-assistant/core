"""The tests for the analytics ."""
from homeassistant.components.analytics.const import ANALYTICS_ENDPOINT_URL, DOMAIN
from homeassistant.setup import async_setup_component


async def test_setup(hass, hass_storage):
    """Test setup of the integration."""
    uuid = await hass.helpers.instance_id.async_get()
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()

    assert hass.data[DOMAIN].huuid == uuid
    assert hass_storage["core.uuid"]["data"]["uuid"] == uuid


async def test_websocket(hass, hass_storage, hass_ws_client, aioclient_mock):
    """Test websocekt commands."""
    uuid = await hass.helpers.instance_id.async_get()
    aioclient_mock.post(ANALYTICS_ENDPOINT_URL, status=200)
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()

    ws_client = await hass_ws_client(hass)
    await ws_client.send_json({"id": 1, "type": "analytics"})
    response = await ws_client.receive_json()

    assert response["success"]
    assert response["result"]["huuid"] == uuid

    await ws_client.send_json(
        {"id": 2, "type": "analytics/preferences", "preferences": ["base"]}
    )
    response = await ws_client.receive_json()
    assert len(aioclient_mock.mock_calls) == 1
    assert response["result"]["preferences"] == ["base"]

    await ws_client.send_json({"id": 3, "type": "analytics"})
    response = await ws_client.receive_json()
    assert response["result"]["preferences"] == ["base"]
