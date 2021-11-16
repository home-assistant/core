"""The camera tests for the august platform."""

from http import HTTPStatus
from unittest.mock import patch

from homeassistant.const import STATE_IDLE

from tests.components.august.mocks import (
    _create_august_with_devices,
    _mock_doorbell_from_fixture,
)


async def test_create_doorbell(hass, hass_client_no_auth):
    """Test creation of a doorbell."""
    doorbell_one = await _mock_doorbell_from_fixture(hass, "get_doorbell.json")

    with patch.object(
        doorbell_one, "async_get_doorbell_image", create=False, return_value="image"
    ):
        await _create_august_with_devices(hass, [doorbell_one])

        camera_k98gidt45gul_name_camera = hass.states.get(
            "camera.k98gidt45gul_name_camera"
        )
        assert camera_k98gidt45gul_name_camera.state == STATE_IDLE

        url = hass.states.get("camera.k98gidt45gul_name_camera").attributes[
            "entity_picture"
        ]

        client = await hass_client_no_auth()
        resp = await client.get(url)
        assert resp.status == HTTPStatus.OK
        body = await resp.text()
        assert body == "image"
