"""Tests for mobile_app component."""
from http import HTTPStatus
from typing import Any

from aiohttp.test_utils import TestClient

# pylint: disable=unused-import
import pytest

from homeassistant.components.mobile_app.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .const import REGISTER, REGISTER_CLEARTEXT

from tests.typing import ClientSessionGenerator


@pytest.fixture
async def create_registrations(
    hass: HomeAssistant, authed_api_client: TestClient
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return two new registrations."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    enc_reg = await authed_api_client.post(
        "/api/mobile_app/registrations", json=REGISTER
    )

    assert enc_reg.status == HTTPStatus.CREATED
    enc_reg_json: dict[str, Any] = await enc_reg.json()

    clear_reg = await authed_api_client.post(
        "/api/mobile_app/registrations", json=REGISTER_CLEARTEXT
    )

    assert clear_reg.status == HTTPStatus.CREATED
    clear_reg_json: dict[str, Any] = await clear_reg.json()

    await hass.async_block_till_done()

    return (enc_reg_json, clear_reg_json)


@pytest.fixture
async def push_registration(
    hass: HomeAssistant, authed_api_client: TestClient
) -> dict[str, Any]:
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
async def webhook_client(
    hass: HomeAssistant,
    authed_api_client: TestClient,
    aiohttp_client: ClientSessionGenerator,
) -> TestClient:
    """mobile_app mock client."""
    # We pass in the authed_api_client server instance because
    # it is used inside create_registrations and just passing in
    # the app instance would cause the server to start twice,
    # which caused deprecation warnings to be printed.
    return await aiohttp_client(authed_api_client.server)


@pytest.fixture
async def authed_api_client(
    hass: HomeAssistant, setup_ws: None, hass_client: ClientSessionGenerator
) -> TestClient:
    """Provide an authenticated client for mobile_app to use."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()
    return await hass_client()


@pytest.fixture
async def setup_ws(hass: HomeAssistant) -> None:
    """Configure the websocket_api component."""
    assert await async_setup_component(hass, "repairs", {})
    assert await async_setup_component(hass, "websocket_api", {})
    await hass.async_block_till_done()
