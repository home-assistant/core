"""Tests for the flow previews."""

from datetime import timedelta
from http import HTTPStatus
from unittest.mock import patch

import pytest
from pytest_homeassistant.typing import ClientSessionGenerator

from homeassistant.components.http.auth import async_sign_path
from homeassistant.components.local_vision.const import DOMAIN
from homeassistant.components.local_vision.preview import MAX_PREVIEWS
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant

from . import REGION, USER_INPUT


async def _preview_url(hass: HomeAssistant) -> str:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], REGION)
    return result["description_placeholders"]["preview"]


@pytest.mark.usefixtures("camera")
async def test_preview_served(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """The signed preview URL from the flow serves a JPEG."""
    url = await _preview_url(hass)
    client = await hass_client_no_auth()

    response = await client.get(url)

    assert response.status == HTTPStatus.OK
    assert response.content_type == "image/jpeg"
    assert (await response.read())[:2] == b"\xff\xd8"


@pytest.mark.usefixtures("camera")
async def test_preview_unknown_or_expired(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Unknown tokens and expired previews are not found."""
    url = await _preview_url(hass)
    client = await hass_client_no_auth()
    unknown = async_sign_path(
        hass, f"/api/{DOMAIN}/preview/{'0' * 32}", timedelta(minutes=1)
    )
    assert (await client.get(unknown)).status == HTTPStatus.NOT_FOUND

    with patch(
        "homeassistant.components.local_vision.preview.monotonic",
        return_value=1e12,
    ):
        assert (await client.get(url)).status == HTTPStatus.NOT_FOUND


@pytest.mark.usefixtures("camera")
async def test_preview_count_is_bounded(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> None:
    """Old previews make room once too many are open."""
    first = await _preview_url(hass)
    for _ in range(MAX_PREVIEWS):
        last = await _preview_url(hass)
    client = await hass_client_no_auth()

    assert (await client.get(first)).status == HTTPStatus.NOT_FOUND
    assert (await client.get(last)).status == HTTPStatus.OK
