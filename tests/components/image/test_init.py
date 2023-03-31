"""The tests for the image component."""
from http import HTTPStatus

import pytest

from homeassistant.core import HomeAssistant

from tests.typing import ClientSessionGenerator


@pytest.mark.freeze_time("2023-04-01 00:00:00+00:00")
async def test_state(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, mock_image
) -> None:
    """Test image state."""
    state = hass.states.get("image.test")
    assert state.state == "2023-04-01T00:00:00"
    access_token = state.attributes["access_token"]
    assert state.attributes == {
        "access_token": access_token,
        "entity_picture": f"/api/image_proxy/image.test?token={access_token}",
        "friendly_name": "Test",
    }


async def test_fetch_image_authenticated(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, mock_image
) -> None:
    """Test fetching an image with an authenticated client."""
    client = await hass_client()

    resp = await client.get("/api/image_proxy/image.test")
    assert resp.status == HTTPStatus.OK
    body = await resp.read()
    assert body == b"Test"

    resp = await client.get("/api/image_proxy/image.unknown")
    assert resp.status == HTTPStatus.NOT_FOUND


async def test_fetch_image_unauthenticated(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator, mock_image
) -> None:
    """Test fetching an image with an unauthenticated client."""
    client = await hass_client_no_auth()

    resp = await client.get("/api/image_proxy/image.test")
    assert resp.status == HTTPStatus.FORBIDDEN

    resp = await client.get("/api/image_proxy/image.test")
    assert resp.status == HTTPStatus.FORBIDDEN

    state = hass.states.get("image.test")
    resp = await client.get(state.attributes["entity_picture"])
    assert resp.status == HTTPStatus.OK
    body = await resp.read()
    assert body == b"Test"

    resp = await client.get("/api/image_proxy/image.unknown")
    assert resp.status == HTTPStatus.NOT_FOUND
