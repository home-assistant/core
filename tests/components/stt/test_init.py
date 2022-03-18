"""Test STT component setup."""
from http import HTTPStatus

from homeassistant.components import stt
from homeassistant.setup import async_setup_component


async def test_setup_comp(hass):
    """Set up demo component."""
    assert await async_setup_component(hass, stt.DOMAIN, {"stt": {}})


async def test_demo_settings_not_exists(hass, hass_client):
    """Test retrieve settings from demo provider."""
    assert await async_setup_component(hass, stt.DOMAIN, {"stt": {}})
    client = await hass_client()

    response = await client.get("/api/stt/beer")

    assert response.status == HTTPStatus.NOT_FOUND


async def test_demo_speech_not_exists(hass, hass_client):
    """Test retrieve settings from demo provider."""
    assert await async_setup_component(hass, stt.DOMAIN, {"stt": {}})
    client = await hass_client()

    response = await client.post("/api/stt/beer", data=b"test")

    assert response.status == HTTPStatus.NOT_FOUND
