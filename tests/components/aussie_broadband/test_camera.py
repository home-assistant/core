"""Aussie Broadband camera platform tests."""
from unittest.mock import patch

from homeassistant.components.aussie_broadband import (
    ATTR_PASSWORD,
    ATTR_USERNAME,
    DOMAIN as AUSSIE_BROADBAND_DOMAIN,
)
from homeassistant.components.aussie_broadband.const import ATTR_SERVICE_ID
from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def setup_platform(hass, platform):
    """Set up the Aussie Broadband platform."""
    mock_entry = MockConfigEntry(
        domain=AUSSIE_BROADBAND_DOMAIN,
        data={
            ATTR_USERNAME: "user@email.com",
            ATTR_PASSWORD: "password",
            ATTR_SERVICE_ID: "12345678",
        },
    )
    mock_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.aussie_broadband.PLATFORMS", [platform]
    ), patch("aussiebb.AussieBB.__init__", return_value=None):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    return mock_entry


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
