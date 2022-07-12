"""Test the onboarding views."""
import asyncio
from http import HTTPStatus
import os
from unittest.mock import patch

import pytest

from homeassistant.components import onboarding
from homeassistant.components.onboarding import const, views
from homeassistant.helpers import area_registry as ar
from homeassistant.setup import async_setup_component

from . import mock_storage

from tests.common import CLIENT_ID, CLIENT_REDIRECT_URI, register_auth_provider


@pytest.fixture(autouse=True)
def auth_active(hass):
    """Ensure auth is always active."""
    hass.loop.run_until_complete(
        register_auth_provider(hass, {"type": "homeassistant"})
    )


@pytest.fixture(name="rpi")
async def rpi_fixture(hass, aioclient_mock, mock_supervisor):
    """Mock core info with rpi."""
    aioclient_mock.get(
        "http://127.0.0.1/core/info",
        json={
            "result": "ok",
            "data": {"version_latest": "1.0.0", "machine": "raspberrypi3"},
        },
    )
    assert await async_setup_component(hass, "hassio", {})
    await hass.async_block_till_done()


@pytest.fixture(name="no_rpi")
async def no_rpi_fixture(hass, aioclient_mock, mock_supervisor):
    """Mock core info with rpi."""
    aioclient_mock.get(
        "http://127.0.0.1/core/info",
        json={
            "result": "ok",
            "data": {"version_latest": "1.0.0", "machine": "odroid-n2"},
        },
    )
    assert await async_setup_component(hass, "hassio", {})
    await hass.async_block_till_done()


@pytest.fixture(name="mock_supervisor")
async def mock_supervisor_fixture(hass, aioclient_mock):
    """Mock supervisor."""
    aioclient_mock.post("http://127.0.0.1/homeassistant/options", json={"result": "ok"})
    aioclient_mock.post("http://127.0.0.1/supervisor/options", json={"result": "ok"})
    with patch.dict(os.environ, {"SUPERVISOR": "127.0.0.1"}), patch(
        "homeassistant.components.hassio.HassIO.is_connected",
        return_value=True,
    ), patch(
        "homeassistant.components.hassio.HassIO.get_info",
        return_value={},
    ), patch(
        "homeassistant.components.hassio.HassIO.get_host_info",
        return_value={},
    ), patch(
        "homeassistant.components.hassio.HassIO.get_store",
        return_value={},
    ), patch(
        "homeassistant.components.hassio.HassIO.get_supervisor_info",
        return_value={"diagnostics": True},
    ), patch(
        "homeassistant.components.hassio.HassIO.get_os_info",
        return_value={},
    ), patch(
        "homeassistant.components.hassio.HassIO.get_ingress_panels",
        return_value={"panels": {}},
    ), patch.dict(
        os.environ, {"SUPERVISOR_TOKEN": "123456"}
    ):
        yield


@pytest.fixture
def mock_default_integrations():
    """Mock the default integrations set up during onboarding."""
    with patch(
        "homeassistant.components.rpi_power.config_flow.new_under_voltage"
    ), patch(
        "homeassistant.components.rpi_power.binary_sensor.new_under_voltage"
    ), patch(
        "homeassistant.components.met.async_setup_entry", return_value=True
    ), patch(
        "homeassistant.components.radio_browser.async_setup_entry", return_value=True
    ):
        yield


async def test_onboarding_progress(hass, hass_storage, hass_client_no_auth):
    """Test fetching progress."""
    mock_storage(hass_storage, {"done": ["hello"]})

    assert await async_setup_component(hass, "onboarding", {})
    await hass.async_block_till_done()

    client = await hass_client_no_auth()

    with patch.object(views, "STEPS", ["hello", "world"]):
        resp = await client.get("/api/onboarding")

    assert resp.status == 200
    data = await resp.json()
    assert len(data) == 2
    assert data[0] == {"step": "hello", "done": True}
    assert data[1] == {"step": "world", "done": False}


async def test_onboarding_user_already_done(hass, hass_storage, hass_client_no_auth):
    """Test creating a new user when user step already done."""
    mock_storage(hass_storage, {"done": [views.STEP_USER]})

    with patch.object(onboarding, "STEPS", ["hello", "world"]):
        assert await async_setup_component(hass, "onboarding", {})
        await hass.async_block_till_done()

    client = await hass_client_no_auth()

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

    assert resp.status == HTTPStatus.FORBIDDEN


async def test_onboarding_user(hass, hass_storage, hass_client_no_auth):
    """Test creating a new user."""
    area_registry = ar.async_get(hass)

    # Create an existing area to mimic an integration creating an area
    # before onboarding is done.
    area_registry.async_create("Living Room")

    assert await async_setup_component(hass, "person", {})
    assert await async_setup_component(hass, "onboarding", {})
    await hass.async_block_till_done()

    cur_users = len(await hass.auth.async_get_users())
    client = await hass_client_no_auth()

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
    assert len(await hass.auth.async_get_users()) == cur_users + 1
    user = next((user for user in users if user.name == "Test Name"), None)
    assert user is not None
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
    assert len(area_registry.areas) == 3
    assert sorted(area.name for area in area_registry.async_list_areas()) == [
        "Bedroom",
        "Kitchen",
        "Living Room",
    ]


async def test_onboarding_user_invalid_name(hass, hass_storage, hass_client_no_auth):
    """Test not providing name."""
    mock_storage(hass_storage, {"done": []})

    assert await async_setup_component(hass, "onboarding", {})
    await hass.async_block_till_done()

    client = await hass_client_no_auth()

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


async def test_onboarding_user_race(hass, hass_storage, hass_client_no_auth):
    """Test race condition on creating new user."""
    mock_storage(hass_storage, {"done": ["hello"]})

    assert await async_setup_component(hass, "onboarding", {})
    await hass.async_block_till_done()

    client = await hass_client_no_auth()

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

    assert sorted([res1.status, res2.status]) == [HTTPStatus.OK, HTTPStatus.FORBIDDEN]


async def test_onboarding_integration(hass, hass_storage, hass_client, hass_admin_user):
    """Test finishing integration step."""
    mock_storage(hass_storage, {"done": [const.STEP_USER]})

    assert await async_setup_component(hass, "onboarding", {})
    await hass.async_block_till_done()

    client = await hass_client()

    resp = await client.post(
        "/api/onboarding/integration",
        json={"client_id": CLIENT_ID, "redirect_uri": CLIENT_REDIRECT_URI},
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

    # Onboarding refresh token and new refresh token
    user = await hass.auth.async_get_user(hass_admin_user.id)
    assert len(user.refresh_tokens) == 2, user


async def test_onboarding_integration_missing_credential(
    hass, hass_storage, hass_client, hass_access_token
):
    """Test that we fail integration step if user is missing credentials."""
    mock_storage(hass_storage, {"done": [const.STEP_USER]})

    assert await async_setup_component(hass, "onboarding", {})
    await hass.async_block_till_done()

    refresh_token = await hass.auth.async_validate_access_token(hass_access_token)
    refresh_token.credential = None

    client = await hass_client()

    resp = await client.post(
        "/api/onboarding/integration",
        json={"client_id": CLIENT_ID, "redirect_uri": CLIENT_REDIRECT_URI},
    )

    assert resp.status == 403


async def test_onboarding_integration_invalid_redirect_uri(
    hass, hass_storage, hass_client
):
    """Test finishing integration step."""
    mock_storage(hass_storage, {"done": [const.STEP_USER]})

    assert await async_setup_component(hass, "onboarding", {})
    await hass.async_block_till_done()

    client = await hass_client()

    with patch(
        "homeassistant.components.auth.indieauth.fetch_redirect_uris", return_value=[]
    ):
        resp = await client.post(
            "/api/onboarding/integration",
            json={
                "client_id": CLIENT_ID,
                "redirect_uri": "http://invalid-redirect.uri",
            },
        )

    assert resp.status == 400

    # We will still mark the last step as done because there is nothing left.
    assert const.STEP_INTEGRATION in hass_storage[const.DOMAIN]["data"]["done"]

    # Only refresh token from onboarding should be there
    for user in await hass.auth.async_get_users():
        assert len(user.refresh_tokens) == 1, user


async def test_onboarding_integration_requires_auth(
    hass, hass_storage, hass_client_no_auth
):
    """Test finishing integration step."""
    mock_storage(hass_storage, {"done": [const.STEP_USER]})

    assert await async_setup_component(hass, "onboarding", {})
    await hass.async_block_till_done()

    client = await hass_client_no_auth()

    resp = await client.post(
        "/api/onboarding/integration", json={"client_id": CLIENT_ID}
    )

    assert resp.status == 401


async def test_onboarding_core_sets_up_met(
    hass, hass_storage, hass_client, mock_default_integrations
):
    """Test finishing the core step."""
    mock_storage(hass_storage, {"done": [const.STEP_USER]})

    assert await async_setup_component(hass, "onboarding", {})
    await hass.async_block_till_done()

    client = await hass_client()
    resp = await client.post("/api/onboarding/core_config")

    assert resp.status == 200

    await hass.async_block_till_done()
    assert len(hass.config_entries.async_entries("met")) == 1


async def test_onboarding_core_sets_up_radio_browser(
    hass, hass_storage, hass_client, mock_default_integrations
):
    """Test finishing the core step set up the radio browser."""
    mock_storage(hass_storage, {"done": [const.STEP_USER]})

    assert await async_setup_component(hass, "onboarding", {})
    await hass.async_block_till_done()

    client = await hass_client()
    resp = await client.post("/api/onboarding/core_config")

    assert resp.status == 200

    await hass.async_block_till_done()
    assert len(hass.config_entries.async_entries("radio_browser")) == 1


async def test_onboarding_core_sets_up_rpi_power(
    hass, hass_storage, hass_client, aioclient_mock, rpi, mock_default_integrations
):
    """Test that the core step sets up rpi_power on RPi."""
    mock_storage(hass_storage, {"done": [const.STEP_USER]})

    assert await async_setup_component(hass, "onboarding", {})
    await hass.async_block_till_done()

    client = await hass_client()

    resp = await client.post("/api/onboarding/core_config")

    assert resp.status == 200

    await hass.async_block_till_done()

    rpi_power_state = hass.states.get("binary_sensor.rpi_power_status")
    assert rpi_power_state


async def test_onboarding_core_no_rpi_power(
    hass, hass_storage, hass_client, aioclient_mock, no_rpi, mock_default_integrations
):
    """Test that the core step do not set up rpi_power on non RPi."""
    mock_storage(hass_storage, {"done": [const.STEP_USER]})

    assert await async_setup_component(hass, "onboarding", {})
    await hass.async_block_till_done()

    client = await hass_client()

    resp = await client.post("/api/onboarding/core_config")

    assert resp.status == 200

    await hass.async_block_till_done()

    rpi_power_state = hass.states.get("binary_sensor.rpi_power_status")
    assert not rpi_power_state


async def test_onboarding_analytics(hass, hass_storage, hass_client, hass_admin_user):
    """Test finishing analytics step."""
    mock_storage(hass_storage, {"done": [const.STEP_USER]})

    assert await async_setup_component(hass, "onboarding", {})
    await hass.async_block_till_done()

    client = await hass_client()

    resp = await client.post("/api/onboarding/analytics")

    assert resp.status == 200

    assert const.STEP_ANALYTICS in hass_storage[const.DOMAIN]["data"]["done"]

    resp = await client.post("/api/onboarding/analytics")
    assert resp.status == 403


async def test_onboarding_installation_type(hass, hass_storage, hass_client):
    """Test returning installation type during onboarding."""
    mock_storage(hass_storage, {"done": []})

    assert await async_setup_component(hass, "onboarding", {})
    await hass.async_block_till_done()

    client = await hass_client()

    with patch(
        "homeassistant.components.onboarding.views.async_get_system_info",
        return_value={"installation_type": "Home Assistant Core"},
    ):
        resp = await client.get("/api/onboarding/installation_type")

        assert resp.status == 200

        resp_content = await resp.json()
        assert resp_content["installation_type"] == "Home Assistant Core"


async def test_onboarding_installation_type_after_done(hass, hass_storage, hass_client):
    """Test raising for installation type after onboarding."""
    mock_storage(hass_storage, {"done": [const.STEP_USER]})

    assert await async_setup_component(hass, "onboarding", {})
    await hass.async_block_till_done()

    client = await hass_client()

    resp = await client.get("/api/onboarding/installation_type")

    assert resp.status == 401
