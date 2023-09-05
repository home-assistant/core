"""Tests for mobile_app component."""
from http import HTTPStatus

import pytest

from homeassistant.components.mobile_app.const import DOMAIN
from homeassistant.setup import async_setup_component

from .const import REGISTER, REGISTER_CLEARTEXT


@pytest.fixture
async def create_registrations(hass, authed_api_client):
    """Return two new registrations."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    enc_reg = await authed_api_client.post(
        "/api/mobile_app/registrations", json=REGISTER
    )

    assert enc_reg.status == HTTPStatus.CREATED
    enc_reg_json = await enc_reg.json()

    clear_reg = await authed_api_client.post(
        "/api/mobile_app/registrations", json=REGISTER_CLEARTEXT
    )

    assert clear_reg.status == HTTPStatus.CREATED
    clear_reg_json = await clear_reg.json()

    await hass.async_block_till_done()

    return (enc_reg_json, clear_reg_json)


@pytest.fixture
async def push_registration(hass, authed_api_client):
    """Return registration with push notifications enabled."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    enc_reg = await authed_api_client.post(
        "/api/mobile_app/registrations",
        json={
            **REGISTER,
            "app_data": {
                "push_url": "http://localhost/mock-push",
                "push_token": "abcd",
            },
        },
    )

    assert enc_reg.status == HTTPStatus.CREATED
    return await enc_reg.json()


@pytest.fixture
async def webhook_client(hass, authed_api_client, aiohttp_client):
    """mobile_app mock client."""
    # We pass in the authed_api_client server instance because
    # it is used inside create_registrations and just passing in
    # the app instance would cause the server to start twice,
    # which caused deprecation warnings to be printed.
    return await aiohttp_client(authed_api_client.server)


@pytest.fixture
async def authed_api_client(hass, hass_client):
    """Provide an authenticated client for mobile_app to use."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()
    return await hass_client()


@pytest.fixture(autouse=True)
async def setup_ws(hass):
    """Configure the websocket_api component."""
    assert await async_setup_component(hass, "repairs", {})
    assert await async_setup_component(hass, "websocket_api", {})
    await hass.async_block_till_done()
