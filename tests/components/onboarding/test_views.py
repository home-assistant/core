"""Test the onboarding views."""

import asyncio
from collections.abc import AsyncGenerator, Callable, Coroutine
from dataclasses import replace
from http import HTTPStatus
import os
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from aiohasupervisor import SupervisorBadRequestError
import pytest

from homeassistant import bootstrap
from homeassistant.components import hassio, onboarding
from homeassistant.components.http import KEY_HASS
from homeassistant.components.onboarding import DOMAIN, const, views
from homeassistant.const import EVENT_COMPONENT_LOADED
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import (
    EventComponentLoaded,
    async_set_domains_to_be_loaded,
    async_setup_component,
    async_wait_component,
)

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
from tests.typing import ClientSessionGenerator


@pytest.fixture(autouse=True)
async def auth_active(hass: HomeAssistant) -> None:
    """Ensure auth is always active."""
    await register_auth_provider(hass, {"type": "homeassistant"})


@pytest.fixture(name="rpi")
async def rpi_fixture(
    hass: HomeAssistant, homeassistant_info: AsyncMock, mock_supervisor: None
) -> None:
    """Mock core info with rpi."""
    homeassistant_info.return_value = replace(
        homeassistant_info.return_value, machine="raspberrypi3"
    )
    assert await async_setup_component(hass, "hassio", {})
    await hass.async_block_till_done()


@pytest.fixture(name="no_rpi")
async def no_rpi_fixture(
    hass: HomeAssistant, homeassistant_info: AsyncMock, mock_supervisor: None
) -> None:
    """Mock core info with rpi."""
    homeassistant_info.return_value = replace(
        homeassistant_info.return_value, machine="odroid-n2"
    )
    assert await async_setup_component(hass, "hassio", {})
    await hass.async_block_till_done()


@pytest.fixture(name="mock_supervisor")
async def mock_supervisor_fixture(
    store_info: AsyncMock,
    supervisor_is_connected: AsyncMock,
    resolution_info: AsyncMock,
    supervisor_root_info: AsyncMock,
    host_info: AsyncMock,
    supervisor_info: AsyncMock,
    network_info: AsyncMock,
    os_info: AsyncMock,
    ingress_panels: AsyncMock,
) -> AsyncGenerator[None]:
    """Mock supervisor."""
    supervisor_info.return_value = replace(
        supervisor_info.return_value, diagnostics=True
    )
    with (
        patch.dict(os.environ, {"SUPERVISOR": "127.0.0.1"}),
        patch.dict(os.environ, {"SUPERVISOR_TOKEN": "123456"}),
    ):
        yield


@pytest.fixture
def mock_default_integrations():
    """Mock the default integrations set up during onboarding."""
    with (
        patch("homeassistant.components.rpi_power.config_flow.new_under_voltage"),
        patch("homeassistant.components.rpi_power.new_under_voltage"),
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

    assert await async_setup_component(hass, DOMAIN, {})
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
        assert await async_setup_component(hass, DOMAIN, {})
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
    assert await async_setup_component(hass, DOMAIN, {})
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

    assert await async_setup_component(hass, DOMAIN, {})
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

    assert await async_setup_component(hass, DOMAIN, {})
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

    assert await async_setup_component(hass, DOMAIN, {})
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

    assert await async_setup_component(hass, DOMAIN, {})
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

    assert await async_setup_component(hass, DOMAIN, {})
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

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    client = await hass_client_no_auth()

    resp = await client.post(
        "/api/onboarding/integration", json={"client_id": CLIENT_ID}
    )

    assert resp.status == 401


async def test_onboarding_installation_type_client_disconnect(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
) -> None:
    """Test a client disconnect does not break the pending hassio setup.

    The HTTP runner is created with handler_cancellation=True, so a disconnect
    cancels the request handler. An unshielded wait would cancel the setup
    future shared with every other waiter and with hassio setup itself.
    """
    mock_storage(hass_storage, {"done": []})

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    async_set_domains_to_be_loaded(hass, {"hassio"})

    wait_entered, instrumented_wait = _instrumented_wait_component()

    view = views.InstallationTypeOnboardingView(hass.data[DOMAIN].steps)
    request = Mock()
    request.app = {KEY_HASS: hass}

    with patch(
        "homeassistant.components.onboarding.views.async_wait_component",
        instrumented_wait,
    ):
        task = hass.async_create_task(view.get(request))
        await wait_entered.wait()

        # The client goes away while the request waits for hassio
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        # Setting up hassio must still resolve the shared setup future
        assert not await async_setup_component(hass, "hassio", {})


async def test_onboarding_core_sets_up_met(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    hass_client: ClientSessionGenerator,
    mock_default_integrations,
) -> None:
    """Test finishing the core step."""
    mock_storage(hass_storage, {"done": [const.STEP_USER]})

    assert await async_setup_component(hass, DOMAIN, {})
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

    assert await async_setup_component(hass, DOMAIN, {})
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

    assert await async_setup_component(hass, DOMAIN, {})
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

    assert await async_setup_component(hass, DOMAIN, {})
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
    no_rpi,
    mock_default_integrations,
) -> None:
    """Test that the core step do not set up rpi_power on non RPi."""
    mock_storage(hass_storage, {"done": [const.STEP_USER]})

    assert await async_setup_component(hass, DOMAIN, {})
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

    assert await async_setup_component(hass, DOMAIN, {})
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

    assert await async_setup_component(hass, DOMAIN, {})
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

    assert await async_setup_component(hass, DOMAIN, {})
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


def _instrumented_wait_component() -> tuple[
    asyncio.Event, Callable[[HomeAssistant, str], Coroutine[Any, Any, bool]]
]:
    """Wrap async_wait_component with an event set when the wait is entered."""
    entered = asyncio.Event()

    async def _wait_component(hass: HomeAssistant, domain: str) -> bool:
        entered.set()
        return await async_wait_component(hass, domain)

    return entered, _wait_component


async def test_onboarding_installation_type_waits_for_hassio(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    hass_client: ClientSessionGenerator,
) -> None:
    """Test installation type waits for hassio on Supervisor installations.

    The HTTP server serves onboarding before hassio is loaded, so answering
    right away would misdetect the installation type.
    """
    mock_storage(hass_storage, {"done": []})

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    client = await hass_client()

    async_set_domains_to_be_loaded(hass, {"hassio"})

    wait_entered, instrumented_wait = _instrumented_wait_component()

    with (
        patch(
            "homeassistant.components.onboarding.views.async_wait_component",
            instrumented_wait,
        ),
        patch(
            "homeassistant.components.onboarding.views.async_get_system_info",
            return_value={"installation_type": "Home Assistant OS"},
        ),
    ):
        req_task = asyncio.create_task(client.get("/api/onboarding/installation_type"))
        await wait_entered.wait()
        # The response must not be produced while hassio is still pending
        assert not req_task.done()

        # hassio setup fails fast as the test provides no supervisor to talk
        # to, which is enough to resolve the wait
        assert not await async_setup_component(hass, "hassio", {})
        resp = await req_task

    assert resp.status == 200
    resp_content = await resp.json()
    assert resp_content["installation_type"] == "Home Assistant OS"


async def test_onboarding_installation_type_done_while_waiting(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    hass_client: ClientSessionGenerator,
) -> None:
    """Test installation type is rejected if onboarding finishes while waiting."""
    mock_storage(hass_storage, {"done": []})

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    client = await hass_client()

    async_set_domains_to_be_loaded(hass, {"hassio"})

    wait_entered, instrumented_wait = _instrumented_wait_component()

    with patch(
        "homeassistant.components.onboarding.views.async_wait_component",
        instrumented_wait,
    ):
        req_task = asyncio.create_task(client.get("/api/onboarding/installation_type"))
        await wait_entered.wait()

        # Onboarding completes while the request is waiting for hassio
        hass.data[DOMAIN].steps["done"].append(const.STEP_USER)
        assert not await async_setup_component(hass, "hassio", {})
        resp = await req_task

    assert resp.status == 401


async def test_onboarding_installation_type_no_hassio(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    hass_client: ClientSessionGenerator,
) -> None:
    """Test installation type does not wait when hassio is not pending setup."""
    mock_storage(hass_storage, {"done": []})

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    client = await hass_client()

    with patch(
        "homeassistant.components.onboarding.views.async_get_system_info",
        return_value={"installation_type": "Home Assistant Container"},
    ):
        resp = await client.get("/api/onboarding/installation_type")

    assert resp.status == 200
    resp_content = await resp.json()
    assert resp_content["installation_type"] == "Home Assistant Container"


@pytest.mark.usefixtures("mock_supervisor", "homeassistant_info")
async def test_onboarding_installation_type_during_bootstrap(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    hass_client_no_auth: ClientSessionGenerator,
    supervisor_client: AsyncMock,
) -> None:
    """Test installation type detection with the real bootstrap setup order.

    Bootstrap serves onboarding as a frontend dependency in stage 0, while
    hassio, added to the domains to set up from the SUPERVISOR environment
    variable, only loads in stage 1. The installation type must not be
    reported before hassio is set up.
    """
    mock_storage(hass_storage, {"done": []})
    # No Supervisor update is available during the onboarding update check
    supervisor_client.supervisor.update.side_effect = SupervisorBadRequestError

    onboarding_loaded = asyncio.Event()

    @callback
    def _onboarding_loaded(event: Event[EventComponentLoaded]) -> None:
        onboarding_loaded.set()

    @callback
    def _filter_onboarding(event_data: EventComponentLoaded) -> bool:
        return event_data["component"] == DOMAIN

    hass.bus.async_listen(
        EVENT_COMPONENT_LOADED, _onboarding_loaded, event_filter=_filter_onboarding
    )

    hassio_setup_gate = asyncio.Event()
    real_hassio_setup = hassio.async_setup

    async def gated_hassio_setup(hass: HomeAssistant, config: ConfigType) -> bool:
        await hassio_setup_gate.wait()
        return await real_hassio_setup(hass, config)

    wait_entered, instrumented_wait = _instrumented_wait_component()

    with (
        patch("homeassistant.bootstrap.DEFAULT_INTEGRATIONS", set()),
        patch("homeassistant.components.hassio.async_setup", gated_hassio_setup),
        patch(
            "homeassistant.components.onboarding.views.async_wait_component",
            instrumented_wait,
        ),
    ):
        bootstrap_task = asyncio.create_task(
            bootstrap._async_set_up_integrations(hass, {"frontend": {}})
        )
        await onboarding_loaded.wait()
        assert "hassio" not in hass.config.components

        client = await hass_client_no_auth()
        req_task = asyncio.create_task(client.get("/api/onboarding/installation_type"))
        await wait_entered.wait()
        # The response must not be produced while hassio is still pending
        assert not req_task.done()

        hassio_setup_gate.set()
        resp = await req_task
        await bootstrap_task

    assert resp.status == 200
    resp_content = await resp.json()
    assert resp_content["installation_type"] == "Home Assistant OS"


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

    assert await async_setup_component(hass, DOMAIN, {})
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

    assert await async_setup_component(hass, DOMAIN, {})
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

    assert await async_setup_component(hass, DOMAIN, {})
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

    assert await async_setup_component(hass, DOMAIN, {})
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

    # The component is scheduled to load, this will block until
    # the config entry is loaded
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

    assert await async_setup_component(hass, DOMAIN, {})
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

    assert await async_setup_component(hass, DOMAIN, {})
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

    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    assert platform_mock.mock_calls == []
    assert "'test.onboarding' is not a valid onboarding platform" in caplog.text
