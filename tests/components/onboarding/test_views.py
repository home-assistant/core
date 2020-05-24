"""Test the onboarding views."""
import asyncio

import pytest

from homeassistant.components import onboarding
from homeassistant.components.onboarding import const, views
from homeassistant.const import HTTP_FORBIDDEN
from homeassistant.setup import async_setup_component

from . import mock_storage

from tests.async_mock import patch
from tests.common import CLIENT_ID, register_auth_provider
from tests.components.met.conftest import mock_weather  # noqa: F401


@pytest.fixture(autouse=True)
def always_mock_weather(mock_weather):  # noqa: F811
    """Mock the Met weather provider."""
    pass


@pytest.fixture(autouse=True)
def auth_active(hass):
    """Ensure auth is always active."""
    hass.loop.run_until_complete(
        register_auth_provider(hass, {"type": "homeassistant"})
    )


async def test_onboarding_progress(hass, hass_storage, aiohttp_client):
    """Test fetching progress."""
    mock_storage(hass_storage, {"done": ["hello"]})

    assert await async_setup_component(hass, "onboarding", {})
    client = await aiohttp_client(hass.http.app)

    with patch.object(views, "STEPS", ["hello", "world"]):
        resp = await client.get("/api/onboarding")

    assert resp.status == 200
    data = await resp.json()
    assert len(data) == 2
    assert data[0] == {"step": "hello", "done": True}
    assert data[1] == {"step": "world", "done": False}


async def test_onboarding_user_already_done(hass, hass_storage, aiohttp_client):
    """Test creating a new user when user step already done."""
    mock_storage(hass_storage, {"done": [views.STEP_USER]})

    with patch.object(onboarding, "STEPS", ["hello", "world"]):
        assert await async_setup_component(hass, "onboarding", {})

    client = await aiohttp_client(hass.http.app)

    resp = await client.post(
        "/api/onboarding/users",
        json={
            "client_id": CLIENT_ID,
            "name": "Test Name",
            "username": "test-user",
            "password": "test-pass",
            "language": "en",
        },
    )

    assert resp.status == HTTP_FORBIDDEN


async def test_onboarding_user(hass, hass_storage, aiohttp_client):
    """Test creating a new user."""
    assert await async_setup_component(hass, "person", {})
    assert await async_setup_component(hass, "onboarding", {})

    client = await aiohttp_client(hass.http.app)

    resp = await client.post(
        "/api/onboarding/users",
        json={
            "client_id": CLIENT_ID,
            "name": "Test Name",
            "username": "test-user",
            "password": "test-pass",
            "language": "en",
        },
    )

    assert resp.status == 200
    assert const.STEP_USER in hass_storage[const.DOMAIN]["data"]["done"]

    data = await resp.json()
    assert "auth_code" in data

    users = await hass.auth.async_get_users()
    assert len(users) == 1
    user = users[0]
    assert user.name == "Test Name"
    assert len(user.credentials) == 1
    assert user.credentials[0].data["username"] == "test-user"
    assert len(hass.data["person"][1].async_items()) == 1

    # Validate refresh token 1
    resp = await client.post(
        "/auth/token",
        data={
            "client_id": CLIENT_ID,
            "grant_type": "authorization_code",
            "code": data["auth_code"],
        },
    )

    assert resp.status == 200
    tokens = await resp.json()

    assert (
        await hass.auth.async_validate_access_token(tokens["access_token"]) is not None
    )

    # Validate created areas
    area_registry = await hass.helpers.area_registry.async_get_registry()
    assert len(area_registry.areas) == 3
    assert sorted([area.name for area in area_registry.async_list_areas()]) == [
        "Bedroom",
        "Kitchen",
        "Living Room",
    ]


async def test_onboarding_user_invalid_name(hass, hass_storage, aiohttp_client):
    """Test not providing name."""
    mock_storage(hass_storage, {"done": []})

    assert await async_setup_component(hass, "onboarding", {})

    client = await aiohttp_client(hass.http.app)

    resp = await client.post(
        "/api/onboarding/users",
        json={
            "client_id": CLIENT_ID,
            "username": "test-user",
            "password": "test-pass",
            "language": "en",
        },
    )

    assert resp.status == 400


async def test_onboarding_user_race(hass, hass_storage, aiohttp_client):
    """Test race condition on creating new user."""
    mock_storage(hass_storage, {"done": ["hello"]})

    assert await async_setup_component(hass, "onboarding", {})

    client = await aiohttp_client(hass.http.app)

    resp1 = client.post(
        "/api/onboarding/users",
        json={
            "client_id": CLIENT_ID,
            "name": "Test 1",
            "username": "1-user",
            "password": "1-pass",
            "language": "en",
        },
    )
    resp2 = client.post(
        "/api/onboarding/users",
        json={
            "client_id": CLIENT_ID,
            "name": "Test 2",
            "username": "2-user",
            "password": "2-pass",
            "language": "es",
        },
    )

    res1, res2 = await asyncio.gather(resp1, resp2)

    assert sorted([res1.status, res2.status]) == [200, HTTP_FORBIDDEN]


async def test_onboarding_integration(hass, hass_storage, hass_client):
    """Test finishing integration step."""
    mock_storage(hass_storage, {"done": [const.STEP_USER]})

    assert await async_setup_component(hass, "onboarding", {})

    client = await hass_client()

    resp = await client.post(
        "/api/onboarding/integration", json={"client_id": CLIENT_ID}
    )

    assert resp.status == 200
    data = await resp.json()
    assert "auth_code" in data

    # Validate refresh token
    resp = await client.post(
        "/auth/token",
        data={
            "client_id": CLIENT_ID,
            "grant_type": "authorization_code",
            "code": data["auth_code"],
        },
    )

    assert resp.status == 200
    assert const.STEP_INTEGRATION in hass_storage[const.DOMAIN]["data"]["done"]
    tokens = await resp.json()

    assert (
        await hass.auth.async_validate_access_token(tokens["access_token"]) is not None
    )


async def test_onboarding_integration_requires_auth(hass, hass_storage, aiohttp_client):
    """Test finishing integration step."""
    mock_storage(hass_storage, {"done": [const.STEP_USER]})

    assert await async_setup_component(hass, "onboarding", {})

    client = await aiohttp_client(hass.http.app)

    resp = await client.post(
        "/api/onboarding/integration", json={"client_id": CLIENT_ID}
    )

    assert resp.status == 401


async def test_onboarding_core_sets_up_met(hass, hass_storage, hass_client):
    """Test finishing the core step."""
    mock_storage(hass_storage, {"done": [const.STEP_USER]})

    assert await async_setup_component(hass, "onboarding", {})

    client = await hass_client()

    resp = await client.post("/api/onboarding/core_config")

    assert resp.status == 200

    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids("weather")) == 1
