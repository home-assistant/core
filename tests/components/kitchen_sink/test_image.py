"""The tests for the kitchen_sink image platform."""
from http import HTTPStatus
from pathlib import Path
from unittest.mock import patch

import pytest

from homeassistant.components.kitchen_sink import DOMAIN, image
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.typing import ClientSessionGenerator


@pytest.fixture
async def image_only() -> None:
    """Enable only the image platform."""
    with patch(
        "homeassistant.components.kitchen_sink.COMPONENTS_WITH_DEMO_PLATFORM",
        [Platform.IMAGE],
    ):
        yield


@pytest.fixture(autouse=True)
async def setup_comp(hass: HomeAssistant, image_only):
    """Set up demo component."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()


async def test_states(hass: HomeAssistant) -> None:
    """Test the expected image entities are added."""
    states = hass.states.async_all()
    assert len(states) == 1
    state = states[0]

    access_token = state.attributes["access_token"]
    assert state.entity_id == "image.qr_code"
    assert state.attributes == {
        "access_token": access_token,
        "entity_picture": f"/api/image_proxy/image.qr_code?token={access_token}",
        "friendly_name": "QR Code",
    }


async def test_fetch_image(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test fetching an image with an authenticated client."""
    client = await hass_client()

    image_path = Path(image.__file__).parent / "qr_code.png"
    expected_data = await hass.async_add_executor_job(image_path.read_bytes)

    resp = await client.get("/api/image_proxy/image.qr_code")
    assert resp.status == HTTPStatus.OK
    body = await resp.read()
    assert body == expected_data
