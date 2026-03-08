"""Test the onboarding views."""

from http import HTTPStatus
from typing import Any
from unittest.mock import MagicMock

import pytest

from homeassistant.components import onboarding
from homeassistant.components.cloud import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import register_auth_provider
from tests.typing import ClientSessionGenerator


def mock_onboarding_storage(hass_storage, data):
    """Mock the onboarding storage."""
    hass_storage[onboarding.STORAGE_KEY] = {
        "version": onboarding.STORAGE_VERSION,
        "data": data,
    }


@pytest.fixture(autouse=True)
async def auth_active(hass: HomeAssistant) -> None:
    """Ensure auth is always active."""
    await register_auth_provider(hass, {"type": "homeassistant"})


@pytest.fixture(name="setup_cloud", autouse=True)
async def setup_cloud_fixture(hass: HomeAssistant, cloud: MagicMock) -> None:
    """Fixture that sets up cloud."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("method", "view", "kwargs"),
    [
        (
            "post",
            "cloud/forgot_password",
            {"json": {"email": "hello@bla.com"}},
        ),
        (
            "post",
            "cloud/login",
            {"json": {"email": "my_username", "password": "my_password"}},
        ),
        ("post", "cloud/logout", {}),
        ("get", "cloud/status", {}),
    ],
)
async def test_onboarding_view_after_done(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    hass_client: ClientSessionGenerator,
    cloud: MagicMock,
    method: str,
    view: str,
    kwargs: dict[str, Any],
) -> None:
    """Test raising after onboarding."""
    mock_onboarding_storage(hass_storage, {"done": [onboarding.const.STEP_USER]})

    assert await async_setup_component(hass, "onboarding", {})
    await hass.async_block_till_done()

    client = await hass_client()

    resp = await client.request(method, f"/api/onboarding/{view}", **kwargs)

    assert resp.status == 401


async def test_onboarding_cloud_forgot_password(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    hass_client: ClientSessionGenerator,
    cloud: MagicMock,
) -> None:
    """Test cloud forgot password."""
    mock_onboarding_storage(hass_storage, {"done": []})

    assert await async_setup_component(hass, "onboarding", {})
    await hass.async_block_till_done()

    client = await hass_client()

    mock_cognito = cloud.auth

    req = await client.post(
        "/api/onboarding/cloud/forgot_password", json={"email": "hello@bla.com"}
    )

    assert req.status == HTTPStatus.OK
    assert mock_cognito.async_forgot_password.call_count == 1


async def test_onboarding_cloud_login(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    hass_client: ClientSessionGenerator,
    cloud: MagicMock,
) -> None:
    """Test logging out from cloud."""
    mock_onboarding_storage(hass_storage, {"done": []})

    assert await async_setup_component(hass, "onboarding", {})
    await hass.async_block_till_done()

    client = await hass_client()
    req = await client.post(
        "/api/onboarding/cloud/login",
        json={"email": "my_username", "password": "my_password"},
    )

    assert req.status == HTTPStatus.OK
    data = await req.json()
    assert data == {"cloud_pipeline": None, "success": True}
    assert cloud.login.call_count == 1


async def test_onboarding_cloud_logout(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    hass_client: ClientSessionGenerator,
    cloud: MagicMock,
) -> None:
    """Test logging out from cloud."""
    mock_onboarding_storage(hass_storage, {"done": []})

    assert await async_setup_component(hass, "onboarding", {})
    await hass.async_block_till_done()

    client = await hass_client()
    req = await client.post("/api/onboarding/cloud/logout")

    assert req.status == HTTPStatus.OK
    data = await req.json()
    assert data == {"message": "ok"}
    assert cloud.logout.call_count == 1


async def test_onboarding_cloud_status(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    hass_client: ClientSessionGenerator,
    cloud: MagicMock,
) -> None:
    """Test logging out from cloud."""
    mock_onboarding_storage(hass_storage, {"done": []})

    assert await async_setup_component(hass, "onboarding", {})
    await hass.async_block_till_done()

    client = await hass_client()
    req = await client.get("/api/onboarding/cloud/status")

    assert req.status == HTTPStatus.OK
    data = await req.json()
    assert data == {"logged_in": False}
