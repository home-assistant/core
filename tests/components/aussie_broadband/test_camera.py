"""Aussie Broadband camera platform tests."""
from unittest.mock import patch

from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.helpers import entity_registry as er

from .common import setup_platform

MOCK_SERVICE = {
    "service_id": "12345678",
    "description": "Fake Description",
    "type": "NBN",
    "nbnDetails": {"cvcGraph": "fake://fake.info/cvc.png", "poiName": "Fake Location"},
}


@patch("aussiebb.AussieBB.get_services", return_value=[MOCK_SERVICE])
async def test_fetching_graph_url(mock_get_services, hass, hass_client, requests_mock):
    """Tests that the graph image is fetched."""

    await setup_platform(hass, CAMERA_DOMAIN)
    entity_registry = er.async_get(hass)

    entity = entity_registry.async_get("camera.fake_location_poi_cvc")
    assert entity.unique_id == MOCK_SERVICE["service_id"]

    requests_mock.get("fake://fake.info/cvc.png", text="hello world")

    client = await hass_client()
    resp = await client.get("/api/camera_proxy/camera.fake_location_poi_cvc")
    assert resp.status == 200
    body = await resp.text()
    assert body == "hello world"
