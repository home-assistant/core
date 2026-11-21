"""Tests for the Plex image view."""

from http import HTTPStatus
from unittest.mock import patch

import pytest
from pytest_homeassistant.typing import ClientSessionGenerator
import requests_mock

from homeassistant.components.plex.const import CONF_SERVER_IDENTIFIER
from homeassistant.core import HomeAssistant

from .const import DEFAULT_DATA

SERVER_ID = DEFAULT_DATA[CONF_SERVER_IDENTIFIER]
FETCH_IMAGE = "homeassistant.components.plex.view.async_fetch_image"


@pytest.mark.usefixtures("mock_plex_server")
async def test_image_view_cache_miss_recovery(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test a link works after the thumbnail cache was lost in a reload."""
    client = await hass_client()

    with patch(FETCH_IMAGE, return_value=(b"image", "image/jpeg")) as fetch:
        response = await client.get(f"/api/plex_image_proxy/{SERVER_ID}/1")

    assert response.status == HTTPStatus.OK
    assert await response.read() == b"image"
    assert fetch.call_args.args[2].startswith(
        "https://1.2.3.4:32400/library/metadata/1/thumb"
    )


@pytest.mark.usefixtures("mock_plex_server")
@pytest.mark.parametrize(
    ("server_id", "media_content_id"),
    [
        (SERVER_ID, "999"),
        (SERVER_ID, "not-a-key"),
        ("unknown", "1"),
    ],
)
async def test_image_view_not_found(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    requests_mock: requests_mock.Mocker,
    server_id: str,
    media_content_id: str,
) -> None:
    """Test images that cannot be found."""
    requests_mock.get(
        "https://1.2.3.4:32400/library/metadata/999", status_code=HTTPStatus.NOT_FOUND
    )
    client = await hass_client()

    with patch(FETCH_IMAGE, return_value=(b"image", "image/jpeg")):
        response = await client.get(
            f"/api/plex_image_proxy/{server_id}/{media_content_id}"
        )

    assert response.status == HTTPStatus.NOT_FOUND
