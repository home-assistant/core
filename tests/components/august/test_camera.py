"""The camera tests for the august platform."""

from http import HTTPStatus
from unittest.mock import patch

from yalexs.const import Brand
from yalexs.doorbell import ContentTokenExpired

from homeassistant.const import STATE_IDLE
from homeassistant.core import HomeAssistant

from .mocks import _create_august_with_devices, _mock_doorbell_from_fixture

from tests.typing import ClientSessionGenerator


async def test_create_doorbell(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> None:
    """Test creation of a doorbell."""
    doorbell_one = await _mock_doorbell_from_fixture(hass, "get_doorbell.json")

    with patch.object(
        doorbell_one, "async_get_doorbell_image", create=False, return_value="image"
    ):
        await _create_august_with_devices(hass, [doorbell_one], brand=Brand.AUGUST)

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


async def test_doorbell_refresh_content_token_recover(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> None:
    """Test camera image content token expired."""
    doorbell_two = await _mock_doorbell_from_fixture(hass, "get_doorbell.json")
    with patch.object(
        doorbell_two,
        "async_get_doorbell_image",
        create=False,
        side_effect=[ContentTokenExpired, "image"],
    ):
        await _create_august_with_devices(
            hass,
            [doorbell_two],
            brand=Brand.YALE_HOME,
        )
        url = hass.states.get("camera.k98gidt45gul_name_camera").attributes[
            "entity_picture"
        ]

        client = await hass_client_no_auth()
        resp = await client.get(url)
        assert resp.status == HTTPStatus.OK
        body = await resp.text()
        assert body == "image"


async def test_doorbell_refresh_content_token_fail(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> None:
    """Test camera image content token expired."""
    doorbell_two = await _mock_doorbell_from_fixture(hass, "get_doorbell.json")
    with patch.object(
        doorbell_two,
        "async_get_doorbell_image",
        create=False,
        side_effect=ContentTokenExpired,
    ):
        await _create_august_with_devices(
            hass,
            [doorbell_two],
            brand=Brand.YALE_HOME,
        )
        url = hass.states.get("camera.k98gidt45gul_name_camera").attributes[
            "entity_picture"
        ]

        client = await hass_client_no_auth()
        resp = await client.get(url)
        assert resp.status == HTTPStatus.INTERNAL_SERVER_ERROR
