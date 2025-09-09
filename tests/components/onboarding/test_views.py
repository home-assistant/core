"""Test the onboarding views."""

import asyncio
from collections.abc import AsyncGenerator
from http import HTTPStatus
import os
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components import onboarding
from homeassistant.components.onboarding import const, views
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar
from homeassistant.setup import async_set_domains_to_be_loaded, async_setup_component

from . import mock_storage

from tests.common import (
    CLIENT_ID,
    CLIENT_REDIRECT_URI,
    MockModule,
    MockUser,
    mock_integration,
    mock_platform,
    register_auth_provider,
)
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator


@pytest.fixture(autouse=True)
async def auth_active(hass: HomeAssistant) -> None:
    """Ensure auth is always active."""
    await register_auth_provider(hass, {"type": "homeassistant"})


@pytest.fixture(name="rpi")
async def rpi_fixture(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, mock_supervisor
) -> None:
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
async def no_rpi_fixture(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, mock_supervisor
) -> None:
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
async def mock_supervisor_fixture(
    aioclient_mock: AiohttpClientMocker,
    store_info: AsyncMock,
    supervisor_is_connected: AsyncMock,
    resolution_info: AsyncMock,
) -> AsyncGenerator[None]:
    """Mock supervisor."""
    aioclient_mock.post("http://127.0.0.1/homeassistant/options", json={"result": "ok"})
    aioclient_mock.post("http://127.0.0.1/supervisor/options", json={"result": "ok"})
    aioclient_mock.get(
        "http://127.0.0.1/network/info",
        json={
            "result": "ok",
            "data": {
                "host_internet": True,
                "supervisor_internet": True,
            },
        },
    )
    with (
        patch.dict(os.environ, {"SUPERVISOR": "127.0.0.1"}),
        patch(
            "homeassistant.components.hassio.HassIO.get_info",
            return_value={},
        ),
        patch(
            "homeassistant.components.hassio.HassIO.get_host_info",
            return_value={},
        ),
        patch(
            "homeassistant.components.hassio.HassIO.get_supervisor_info",
            return_value={"diagnostics": True},
        ),
        patch(
            "homeassistant.components.hassio.HassIO.get_os_info",
            return_value={},
        ),
        patch(
            "homeassistant.components.hassio.HassIO.get_ingress_panels",
            return_value={"panels": {}},
        ),
        patch.dict(
            os.environ,
            {"SUPERVISOR_TOKEN": "123456"},
        ),
    ):
        yield


@pytest.fixture
def mock_default_integrations():
    """Mock the default integrations set up during onboarding."""
    with (
        patch("homeassistant.components.rpi_power.config_flow.new_under_voltage"),
        patch("homeassistant.components.rpi_power.binary_sensor.new_under_voltage"),
        patch("homeassistant.components.met.async_setup_entry", return_value=True),
        patch(
            "homeassistant.components.radio_browser.async_setup_entry",
            return_value=True,
        ),
        patch(
            "homeassistant.components.shopping_list.async_setup_entry",
            return_value=True,
        ),
    ):
        yield


async def test_onboarding_progress(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
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


async def test_onboarding_user_already_done(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
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


async def test_onboarding_user(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    hass_client_no_auth: ClientSessionGenerator,
    area_registry: ar.AreaRegistry,
) -> None:
    """Test creating a new user."""
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

    assert hass.auth.async_validate_access_token(tokens["access_token"]) is not None

    # Validate created areas
    assert len(area_registry.areas) == 3
    assert sorted(area.name for area in area_registry.async_list_areas()) == [
        "Bedroom",
        "Kitchen",
        "Living Room",
    ]


async def test_onboarding_user_invalid_name(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
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


async def test_onboarding_user_race(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
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


async def test_onboarding_integration(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    hass_client: ClientSessionGenerator,
    hass_admin_user: MockUser,
) -> None:
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

    assert hass.auth.async_validate_access_token(tokens["access_token"]) is not None

    # Onboarding refresh token and new refresh token
    user = await hass.auth.async_get_user(hass_admin_user.id)
    assert len(user.refresh_tokens) == 2, user


async def test_onboarding_integration_missing_credential(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    hass_client: ClientSessionGenerator,
    hass_access_token: str,
) -> None:
    """Test that we fail integration step if user is missing credentials."""
    mock_storage(hass_storage, {"done": [const.STEP_USER]})

    assert await async_setup_component(hass, "onboarding", {})
    await hass.async_block_till_done()

    refresh_token = hass.auth.async_validate_access_token(hass_access_token)
    refresh_token.credential = None

    client = await hass_client()

    resp = await client.post(
        "/api/onboarding/integration",
        json={"client_id": CLIENT_ID, "redirect_uri": CLIENT_REDIRECT_URI},
    )

    assert resp.status == 403


async def test_onboarding_integration_invalid_redirect_uri(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    hass_client: ClientSessionGenerator,
) -> None:
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
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
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
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    hass_client: ClientSessionGenerator,
    mock_default_integrations,
) -> None:
    """Test finishing the core step."""
    mock_storage(hass_storage, {"done": [const.STEP_USER]})

    assert await async_setup_component(hass, "onboarding", {})
    await hass.async_block_till_done()

    client = await hass_client()
    resp = await client.post("/api/onboarding/core_config")

    assert resp.status == 200

    await hass.async_block_till_done()
    assert len(hass.config_entries.async_entries("met")) == 1


async def test_onboarding_core_sets_up_shopping_list(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    hass_client: ClientSessionGenerator,
    mock_default_integrations,
) -> None:
    """Test finishing the core step set up the shopping list."""
    mock_storage(hass_storage, {"done": [const.STEP_USER]})

    assert await async_setup_component(hass, "onboarding", {})
    await hass.async_block_till_done()

    client = await hass_client()
    resp = await client.post("/api/onboarding/core_config")

    assert resp.status == 200

    await hass.async_block_till_done()
    assert len(hass.config_entries.async_entries("shopping_list")) == 1


async def test_onboarding_core_sets_up_google_translate(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    hass_client: ClientSessionGenerator,
    mock_default_integrations,
) -> None:
    """Test finishing the core step sets up google translate."""
    mock_storage(hass_storage, {"done": [const.STEP_USER]})

    assert await async_setup_component(hass, "onboarding", {})
    await hass.async_block_till_done()

    client = await hass_client()
    resp = await client.post("/api/onboarding/core_config")

    assert resp.status == 200

    await hass.async_block_till_done()
    assert len(hass.config_entries.async_entries("google_translate")) == 1


async def test_onboarding_core_sets_up_radio_browser(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    hass_client: ClientSessionGenerator,
    mock_default_integrations,
) -> None:
    """Test finishing the core step set up the radio browser."""
    mock_storage(hass_storage, {"done": [const.STEP_USER]})

    assert await async_setup_component(hass, "onboarding", {})
    await hass.async_block_till_done()

    client = await hass_client()
    resp = await client.post("/api/onboarding/core_config")

    assert resp.status == 200

    await hass.async_block_till_done()
    assert len(hass.config_entries.async_entries("radio_browser")) == 1


async def test_onboarding_core_no_rpi_power(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    hass_client: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    no_rpi,
    mock_default_integrations,
) -> None:
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


async def test_onboarding_core_ensures_analytics_loaded(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    hass_client: ClientSessionGenerator,
    mock_default_integrations,
) -> None:
    """Test finishing the core step ensures analytics is ready."""
    mock_storage(hass_storage, {"done": [const.STEP_USER]})
    assert "analytics" not in hass.config.components

    assert await async_setup_component(hass, "onboarding", {})
    await hass.async_block_till_done()

    client = await hass_client()
    resp = await client.post("/api/onboarding/core_config")

    assert resp.status == 200

    await hass.async_block_till_done()
    assert "analytics" in hass.config.components


async def test_onboarding_analytics(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    hass_client: ClientSessionGenerator,
    hass_admin_user: MockUser,
) -> None:
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


async def test_onboarding_installation_type(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    hass_client: ClientSessionGenerator,
) -> None:
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


@pytest.mark.parametrize(
    ("method", "view", "kwargs"),
    [
        ("get", "installation_type", {}),
    ],
)
async def test_onboarding_view_after_done(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    hass_client: ClientSessionGenerator,
    method: str,
    view: str,
    kwargs: dict[str, Any],
) -> None:
    """Test raising after onboarding."""
    mock_storage(hass_storage, {"done": [const.STEP_USER]})

    assert await async_setup_component(hass, "onboarding", {})
    await hass.async_block_till_done()

    client = await hass_client()

    resp = await client.request(method, f"/api/onboarding/{view}", **kwargs)

    assert resp.status == 401


async def test_complete_onboarding(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test completing onboarding calls listeners."""
    listener_1 = Mock()
    onboarding.async_add_listener(hass, listener_1)
    listener_1.assert_not_called()

    assert await async_setup_component(hass, "onboarding", {})
    await hass.async_block_till_done()

    listener_2 = Mock()
    onboarding.async_add_listener(hass, listener_2)
    listener_2.assert_not_called()

    client = await hass_client()

    assert not onboarding.async_is_onboarded(hass)

    # Complete the user step
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
    assert not onboarding.async_is_onboarded(hass)
    listener_2.assert_not_called()

    # Complete the core config step
    resp = await client.post("/api/onboarding/core_config")
    assert resp.status == 200
    assert not onboarding.async_is_onboarded(hass)
    listener_2.assert_not_called()

    # Complete the integration step
    resp = await client.post(
        "/api/onboarding/integration",
        json={"client_id": CLIENT_ID, "redirect_uri": CLIENT_REDIRECT_URI},
    )
    assert resp.status == 200
    assert not onboarding.async_is_onboarded(hass)
    listener_2.assert_not_called()

    # Complete the analytics step
    resp = await client.post("/api/onboarding/analytics")
    assert resp.status == 200
    assert onboarding.async_is_onboarded(hass)
    listener_1.assert_not_called()  # Registered before the integration was setup
    listener_2.assert_called_once_with()

    listener_3 = Mock()
    onboarding.async_add_listener(hass, listener_3)
    listener_3.assert_called_once_with()


@pytest.mark.parametrize(
    ("domain", "expected_result"),
    [
        ("onboarding", {"integration_loaded": True}),
        ("non_existing_domain", {"integration_loaded": False}),
    ],
)
async def test_wait_integration(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    hass_client: ClientSessionGenerator,
    domain: str,
    expected_result: dict[str, Any],
) -> None:
    """Test we can get wait for an integration to load."""
    mock_storage(hass_storage, {"done": []})

    assert await async_setup_component(hass, "onboarding", {})
    await hass.async_block_till_done()

    client = await hass_client()
    req = await client.post("/api/onboarding/integration/wait", json={"domain": domain})

    assert req.status == HTTPStatus.OK
    data = await req.json()
    assert data == expected_result


async def test_wait_integration_startup(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    hass_client: ClientSessionGenerator,
) -> None:
    """Test we can get wait for an integration to load during startup."""
    mock_storage(hass_storage, {"done": []})

    assert await async_setup_component(hass, "onboarding", {})
    await hass.async_block_till_done()
    client = await hass_client()

    setup_stall = asyncio.Event()
    setup_started = asyncio.Event()

    async def mock_setup(hass: HomeAssistant, _) -> bool:
        setup_started.set()
        await setup_stall.wait()
        return True

    mock_integration(hass, MockModule("test", async_setup=mock_setup))

    # The integration is not loaded, and is also not scheduled to load
    req = await client.post("/api/onboarding/integration/wait", json={"domain": "test"})
    assert req.status == HTTPStatus.OK
    data = await req.json()
    assert data == {"integration_loaded": False}

    # Mark the component as scheduled to be loaded
    async_set_domains_to_be_loaded(hass, {"test"})

    # Start loading the component, including its config entries
    hass.async_create_task(async_setup_component(hass, "test", {}))
    await setup_started.wait()

    # The component is not yet loaded
    assert "test" not in hass.config.components

    # Allow setup to proceed
    setup_stall.set()

    # The component is scheduled to load, this will block until the config entry is loaded
    req = await client.post("/api/onboarding/integration/wait", json={"domain": "test"})
    assert req.status == HTTPStatus.OK
    data = await req.json()
    assert data == {"integration_loaded": True}

    # The component has been loaded
    assert "test" in hass.config.components


async def test_not_setup_platform_if_onboarded(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test if onboarding is done, we don't setup platforms."""
    mock_storage(hass_storage, {"done": onboarding.STEPS})

    platform_mock = Mock(async_setup_views=AsyncMock(), spec=["async_setup_views"])
    mock_platform(hass, "test.onboarding", platform_mock)
    assert await async_setup_component(hass, "test", {})
    await hass.async_block_till_done()

    assert await async_setup_component(hass, "onboarding", {})
    await hass.async_block_till_done()

    assert len(platform_mock.async_setup_views.mock_calls) == 0


async def test_setup_platform_if_not_onboarded(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test if onboarding is not done, we setup platforms."""
    platform_mock = Mock(async_setup_views=AsyncMock(), spec=["async_setup_views"])
    mock_platform(hass, "test.onboarding", platform_mock)
    assert await async_setup_component(hass, "test", {})
    await hass.async_block_till_done()

    assert await async_setup_component(hass, "onboarding", {})
    await hass.async_block_till_done()

    platform_mock.async_setup_views.assert_awaited_once_with(hass, {"done": []})


@pytest.mark.parametrize(
    "platform_mock",
    [
        Mock(some_method=AsyncMock(), spec=["some_method"]),
        Mock(spec=[]),
    ],
)
async def test_bad_platform(
    hass: HomeAssistant,
    platform_mock: Mock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test loading onboarding platform which doesn't have the expected methods."""
    mock_platform(hass, "test.onboarding", platform_mock)
    assert await async_setup_component(hass, "test", {})
    await hass.async_block_till_done()

    assert await async_setup_component(hass, "onboarding", {})
    await hass.async_block_till_done()

    assert platform_mock.mock_calls == []
    assert "'test.onboarding' is not a valid onboarding platform" in caplog.text
