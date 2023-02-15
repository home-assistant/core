"""The tests for the demo stt component."""
from http import HTTPStatus

import pytest

from homeassistant.components import stt
from homeassistant.setup import async_setup_component

from tests.typing import ClientSessionGenerator


@pytest.fixture(autouse=True)
async def setup_comp(hass):
    """Set up demo component."""
    assert await async_setup_component(hass, stt.DOMAIN, {"stt": {"platform": "demo"}})
    await hass.async_block_till_done()


async def test_demo_settings(hass_client: ClientSessionGenerator) -> None:
    """Test retrieve settings from demo provider."""
    client = await hass_client()

    response = await client.get("/api/stt/demo")
    response_data = await response.json()

    assert response.status == HTTPStatus.OK
    assert response_data == {
        "languages": ["en", "de"],
        "bit_rates": [16],
        "sample_rates": [16000, 44100],
        "formats": ["wav"],
        "codecs": ["pcm"],
        "channels": [2],
    }


async def test_demo_speech_no_metadata(hass_client: ClientSessionGenerator) -> None:
    """Test retrieve settings from demo provider."""
    client = await hass_client()

    response = await client.post("/api/stt/demo", data=b"Test")
    assert response.status == HTTPStatus.BAD_REQUEST


async def test_demo_speech_wrong_metadata(hass_client: ClientSessionGenerator) -> None:
    """Test retrieve settings from demo provider."""
    client = await hass_client()

    response = await client.post(
        "/api/stt/demo",
        headers={
            "X-Speech-Content": (
                "format=wav; codec=pcm; sample_rate=8000; bit_rate=16; channel=1;"
                " language=de"
            )
        },
        data=b"Test",
    )
    assert response.status == HTTPStatus.UNSUPPORTED_MEDIA_TYPE


async def test_demo_speech(hass_client: ClientSessionGenerator) -> None:
    """Test retrieve settings from demo provider."""
    client = await hass_client()

    response = await client.post(
        "/api/stt/demo",
        headers={
            "X-Speech-Content": (
                "format=wav; codec=pcm; sample_rate=16000; bit_rate=16; channel=2;"
                " language=de"
            )
        },
        data=b"Test",
    )
    response_data = await response.json()

    assert response.status == HTTPStatus.OK
    assert response_data == {"text": "Turn the Kitchen Lights on", "result": "success"}
