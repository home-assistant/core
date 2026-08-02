"""Tests for the Redfish coordinator."""

from collections.abc import Callable
from typing import Any
from unittest.mock import patch

from aiohttp import web
from aiohttp.test_utils import TestServer
import pytest

from homeassistant.components.redfish.const import DOMAIN
from homeassistant.components.redfish.coordinator import (
    RedfishAuthError,
    RedfishClient,
    RedfishDataUpdateCoordinator,
    RedfishError,
)
from homeassistant.components.redfish.models import RedfishSystem
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


@pytest.fixture
def redfish_app() -> web.Application:
    """Return a representative Redfish service."""
    app = web.Application()
    app["requests"] = []

    async def response(request: web.Request) -> web.Response:
        app["requests"].append(
            (
                request.method,
                request.path,
                await request.json() if request.method == "POST" else None,
                request.headers.get("Authorization"),
            )
        )
        if request.method == "POST":
            return web.Response(status=204)
        resources: dict[str, dict[str, Any]] = {
            "/redfish/v1/": {
                "Systems": {"@odata.id": "/redfish/v1/Systems"},
            },
            "/redfish/v1/Systems": {
                "Members": [
                    {"@odata.id": "/redfish/v1/Systems/1"},
                    {},
                    {"@odata.id": 1},
                    {"@odata.id": " "},
                    "invalid",
                ]
            },
            "/redfish/v1/Systems/1": {
                "@odata.id": "/redfish/v1/Systems/1",
                "Id": "1",
                "Name": "Server",
                "UUID": "uuid-1",
                "Manufacturer": "Acme",
                "Model": "Model 1",
                "SerialNumber": "serial",
                "PowerState": "On",
                "Actions": {
                    "#ComputerSystem.Reset": {
                        "target": "/redfish/v1/Systems/1/Actions/ComputerSystem.Reset",
                        "ResetType@Redfish.AllowableValues": [
                            "On",
                            "GracefulShutdown",
                            "ForceOff",
                            "GracefulRestart",
                        ],
                    }
                },
            },
        }
        if request.path not in resources:
            return web.Response(status=404)
        return web.json_response(resources[request.path])

    app.router.add_route("*", "/{path:.*}", response)
    return app


@pytest.fixture
def aiohttp_server(
    aiohttp_server: Callable[[], TestServer], socket_enabled: None
) -> Callable[[], TestServer]:
    """Return aiohttp_server and allow opening sockets."""
    return aiohttp_server


def test_coordinator_uses_configured_tls_verification(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the coordinator uses the configured TLS verification setting."""
    with patch(
        "homeassistant.components.redfish.coordinator.async_get_clientsession"
    ) as get_clientsession:
        RedfishDataUpdateCoordinator(hass, mock_config_entry)

    get_clientsession.assert_called_once_with(hass, verify_ssl=False)


async def test_discover_systems(
    hass: HomeAssistant,
    aiohttp_server: Callable[[], TestServer],
    redfish_app: web.Application,
) -> None:
    """Test standard service-root ComputerSystem discovery."""
    server = await aiohttp_server(redfish_app)
    client = RedfishClient(
        async_get_clientsession(hass),
        str(server.make_url("")),
        "user",
        "password",
    )

    data = await client.async_discover()

    assert data.systems == {
        "1": RedfishSystem(
            odata_id="/redfish/v1/Systems/1",
            system_id="1",
            name="Server",
            uuid="uuid-1",
            manufacturer="Acme",
            model="Model 1",
            serial_number="serial",
            power_state="On",
            reset_target="/redfish/v1/Systems/1/Actions/ComputerSystem.Reset",
            reset_types=frozenset(
                {"On", "GracefulShutdown", "ForceOff", "GracefulRestart"}
            ),
        )
    }


async def test_post_reset_uses_advertised_target_and_type(
    hass: HomeAssistant,
    aiohttp_server: Callable[[], TestServer],
    redfish_app: web.Application,
) -> None:
    """Test reset commands use the advertised action URL and payload."""
    server = await aiohttp_server(redfish_app)
    client = RedfishClient(
        async_get_clientsession(hass),
        str(server.make_url("")),
        "user",
        "password",
    )

    target = str(server.make_url("/redfish/v1/Systems/1/Actions/ComputerSystem.Reset"))
    await client.async_reset(target, "On")

    assert redfish_app["requests"] == [
        (
            "POST",
            "/redfish/v1/Systems/1/Actions/ComputerSystem.Reset",
            {"ResetType": "On"},
            "Basic dXNlcjpwYXNzd29yZA==",
        )
    ]


async def test_reject_cross_origin_advertised_target(
    hass: HomeAssistant,
    aiohttp_server: Callable[[], TestServer],
    redfish_app: web.Application,
) -> None:
    """Test credentials are never sent to a cross-origin advertised target."""
    server = await aiohttp_server(redfish_app)
    malicious_app = web.Application()
    malicious_requests: list[str] = []

    async def capture_request(request: web.Request) -> web.Response:
        malicious_requests.append(request.headers.get("Authorization", ""))
        return web.Response(status=204)

    malicious_app.router.add_post("/{path:.*}", capture_request)
    malicious_server = await aiohttp_server(malicious_app)
    client = RedfishClient(
        async_get_clientsession(hass),
        str(server.make_url("")),
        "user",
        "password",
    )

    with pytest.raises(RedfishError):
        await client.async_reset(str(malicious_server.make_url("/redfish/reset")), "On")

    assert malicious_requests == []


async def test_reject_cross_origin_redirect(
    hass: HomeAssistant,
    aiohttp_server: Callable[[], TestServer],
) -> None:
    """Test a Redfish response cannot redirect requests to another origin."""
    malicious_app = web.Application()
    malicious_requests: list[str] = []

    async def capture_request(request: web.Request) -> web.Response:
        malicious_requests.append(request.headers.get("Authorization", ""))
        return web.json_response({})

    malicious_app.router.add_get("/{path:.*}", capture_request)
    malicious_server = await aiohttp_server(malicious_app)

    redirect_app = web.Application()

    async def redirect_request(_request: web.Request) -> web.Response:
        raise web.HTTPFound(str(malicious_server.make_url("/redfish/v1/")))

    redirect_app.router.add_get("/{path:.*}", redirect_request)
    redirect_server = await aiohttp_server(redirect_app)
    client = RedfishClient(
        async_get_clientsession(hass),
        str(redirect_server.make_url("")),
        "user",
        "password",
    )

    with pytest.raises(RedfishError):
        await client.async_get_systems()

    assert malicious_requests == []


async def test_coordinator_update_error_is_translated(
    init_integration: MockConfigEntry,
) -> None:
    """Test polling errors expose a translated Home Assistant message."""
    coordinator = init_integration.runtime_data
    with (
        patch.object(coordinator.client, "async_discover", side_effect=RedfishError),
        pytest.raises(UpdateFailed) as exc_info,
    ):
        await coordinator._async_update_data()

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "update_failed"


@pytest.mark.parametrize(
    ("status", "payload", "expected_exception"),
    [
        pytest.param(401, {}, RedfishAuthError, id="unauthorized"),
        pytest.param(403, {}, RedfishAuthError, id="forbidden"),
        pytest.param(500, {}, RedfishError, id="server-error"),
        pytest.param(200, [], RedfishError, id="non-object-json"),
    ],
)
async def test_get_response_errors(
    hass: HomeAssistant,
    aiohttp_server: Callable[[], TestServer],
    status: int,
    payload: dict[str, Any] | list[Any],
    expected_exception: type[RedfishError],
) -> None:
    """Test authentication, HTTP, and malformed response errors."""
    app = web.Application()

    async def response(_request: web.Request) -> web.Response:
        return web.json_response(payload, status=status)

    app.router.add_get("/{path:.*}", response)
    server = await aiohttp_server(app)
    client = RedfishClient(
        async_get_clientsession(hass),
        str(server.make_url("")),
        "user",
        "password",
    )

    with pytest.raises(expected_exception):
        await client.async_get_systems()
