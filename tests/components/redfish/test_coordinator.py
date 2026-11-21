"""Tests for the Redfish coordinator."""

import asyncio
from collections.abc import Callable
from typing import Any
from unittest.mock import patch

from aiohttp import web
from aiohttp.test_utils import TestServer
import pytest

from homeassistant.components.redfish.api import (
    RedfishApi,
    RedfishAuthError,
    RedfishError,
)
from homeassistant.components.redfish.const import DOMAIN
from homeassistant.components.redfish.coordinator import RedfishDataUpdateCoordinator
from homeassistant.components.redfish.models import RedfishSystem
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
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
    client = RedfishApi(
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


async def test_discover_paginated_systems(
    hass: HomeAssistant,
    aiohttp_server: Callable[[], TestServer],
) -> None:
    """Test ComputerSystem discovery follows collection pagination."""
    resources: dict[str, dict[str, Any]] = {
        "/redfish/v1/": {
            "Systems": {"@odata.id": "/redfish/v1/Systems"},
        },
        "/redfish/v1/Systems": {
            "Members": [{"@odata.id": "/redfish/v1/Systems/1"}],
            "Members@odata.nextLink": "/redfish/v1/Systems?page=2",
        },
        "/redfish/v1/Systems?page=2": {
            "Members": [{"@odata.id": "/redfish/v1/Systems/2"}],
        },
        "/redfish/v1/Systems/1": {
            "@odata.id": "/redfish/v1/Systems/1",
            "Id": "1",
        },
        "/redfish/v1/Systems/2": {
            "@odata.id": "/redfish/v1/Systems/2",
            "Id": "2",
        },
    }
    app = web.Application()

    async def response(request: web.Request) -> web.Response:
        return web.json_response(resources[request.path_qs])

    app.router.add_get("/{path:.*}", response)
    server = await aiohttp_server(app)
    client = RedfishApi(
        async_get_clientsession(hass),
        str(server.make_url("")),
        "user",
        "password",
    )

    systems = await client.async_get_systems()

    assert systems.keys() == {"1", "2"}


@pytest.mark.parametrize(
    "resources",
    [
        pytest.param(
            {"/redfish/v1/": {}},
            id="missing-systems-link",
        ),
        pytest.param(
            {
                "/redfish/v1/": {"Systems": {"@odata.id": "/redfish/v1/Systems"}},
                "/redfish/v1/Systems": {"Members": {}},
            },
            id="malformed-members",
        ),
    ],
)
async def test_discover_without_usable_system_collection(
    hass: HomeAssistant,
    aiohttp_server: Callable[[], TestServer],
    resources: dict[str, dict[str, Any]],
) -> None:
    """Test malformed system collection data produces no systems."""
    app = web.Application()

    async def response(request: web.Request) -> web.Response:
        return web.json_response(resources[request.path])

    app.router.add_get("/{path:.*}", response)
    server = await aiohttp_server(app)
    client = RedfishApi(
        async_get_clientsession(hass),
        str(server.make_url("")),
        "user",
        "password",
    )

    assert await client.async_get_systems() == {}


async def test_reject_cyclic_system_collection_pagination(
    hass: HomeAssistant,
    aiohttp_server: Callable[[], TestServer],
) -> None:
    """Test cyclic system collection pagination is rejected."""
    resources: dict[str, dict[str, Any]] = {
        "/redfish/v1/": {
            "Systems": {"@odata.id": "/redfish/v1/Systems"},
        },
        "/redfish/v1/Systems": {
            "Members": [],
            "Members@odata.nextLink": "/redfish/v1/Systems",
        },
    }
    app = web.Application()

    async def response(request: web.Request) -> web.Response:
        return web.json_response(resources[request.path])

    app.router.add_get("/{path:.*}", response)
    server = await aiohttp_server(app)
    client = RedfishApi(
        async_get_clientsession(hass),
        str(server.make_url("")),
        "user",
        "password",
    )

    with pytest.raises(RedfishError):
        await client.async_get_systems()


async def test_reject_unbounded_unique_system_collection_pagination(
    hass: HomeAssistant,
) -> None:
    """Test unique pagination links cannot keep discovery running indefinitely."""
    client = RedfishApi(
        async_get_clientsession(hass),
        "https://bmc.example",
        "user",
        "password",
    )
    page = 0

    async def get_resource(path: str) -> dict[str, Any]:
        nonlocal page
        await asyncio.sleep(0)
        if path == "/redfish/v1/":
            return {"Systems": {"@odata.id": "/redfish/v1/Systems?page=0"}}
        page += 1
        return {
            "Members": [],
            "Members@odata.nextLink": f"/redfish/v1/Systems?page={page}",
        }

    with (
        patch.object(client, "_async_get", side_effect=get_resource),
        patch(
            "homeassistant.components.redfish.api.COLLECTION_TIMEOUT",
            0.01,
        ),
        pytest.raises(RedfishError),
    ):
        async with asyncio.timeout(0.1):
            await client.async_get_systems()

    assert page > 1


async def test_discover_reset_types_from_action_info(
    hass: HomeAssistant,
    aiohttp_server: Callable[[], TestServer],
) -> None:
    """Test reset types are discovered from standard ActionInfo."""
    resources: dict[str, dict[str, Any]] = {
        "/redfish/v1/": {
            "Systems": {"@odata.id": "/redfish/v1/Systems"},
        },
        "/redfish/v1/Systems": {
            "Members": [{"@odata.id": "/redfish/v1/Systems/1"}],
        },
        "/redfish/v1/Systems/1": {
            "@odata.id": "/redfish/v1/Systems/1",
            "Id": "1",
            "Actions": {
                "#ComputerSystem.Reset": {
                    "target": "/redfish/v1/Systems/1/Actions/ComputerSystem.Reset",
                    "@Redfish.ActionInfo": "/redfish/v1/Systems/1/ResetActionInfo",
                }
            },
        },
        "/redfish/v1/Systems/1/ResetActionInfo": {
            "Parameters": [
                {
                    "Name": "ResetType",
                    "AllowableValues": [
                        "On",
                        "GracefulShutdown",
                        "VendorReset",
                        1,
                    ],
                },
                {"Name": "OtherParameter", "AllowableValues": ["ForceOff"]},
            ]
        },
    }
    app = web.Application()

    async def response(request: web.Request) -> web.Response:
        return web.json_response(resources[request.path])

    app.router.add_get("/{path:.*}", response)
    server = await aiohttp_server(app)
    client = RedfishApi(
        async_get_clientsession(hass),
        str(server.make_url("")),
        "user",
        "password",
    )

    systems = await client.async_get_systems()

    assert systems["1"].reset_types == frozenset({"On", "GracefulShutdown"})


async def test_post_reset_uses_advertised_target_and_type(
    hass: HomeAssistant,
    aiohttp_server: Callable[[], TestServer],
    redfish_app: web.Application,
) -> None:
    """Test reset commands use the advertised action URL and payload."""
    server = await aiohttp_server(redfish_app)
    client = RedfishApi(
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
            None,
        )
    ]


async def test_post_reset_accepts_same_origin_scheme_relative_target(
    hass: HomeAssistant,
    aiohttp_server: Callable[[], TestServer],
    redfish_app: web.Application,
) -> None:
    """Test a same-origin scheme-relative action target is accepted."""
    server = await aiohttp_server(redfish_app)
    client = RedfishApi(
        async_get_clientsession(hass),
        str(server.make_url("")),
        "user",
        "password",
    )

    target = server.make_url(
        "/redfish/v1/Systems/1/Actions/ComputerSystem.Reset"
    ).with_scheme("")
    await client.async_reset(str(target), "On")

    assert redfish_app["requests"] == [
        (
            "POST",
            "/redfish/v1/Systems/1/Actions/ComputerSystem.Reset",
            {"ResetType": "On"},
            None,
        )
    ]


async def test_reset_authentication_error(
    hass: HomeAssistant,
    aiohttp_server: Callable[[], TestServer],
) -> None:
    """Test reset authentication errors are preserved."""
    app = web.Application()

    async def response(_request: web.Request) -> web.Response:
        return web.Response(status=401)

    app.router.add_post("/{path:.*}", response)
    server = await aiohttp_server(app)
    client = RedfishApi(
        async_get_clientsession(hass),
        str(server.make_url("")),
        "user",
        "password",
    )

    with pytest.raises(RedfishAuthError):
        await client.async_reset("/redfish/reset", "On")


async def test_reset_rejects_malformed_target(hass: HomeAssistant) -> None:
    """Test a malformed advertised reset target is rejected."""
    client = RedfishApi(
        async_get_clientsession(hass),
        "https://bmc.example",
        "user",
        "password",
    )

    with pytest.raises(RedfishError):
        await client.async_reset("https://[", "On")


@pytest.mark.parametrize(
    "scheme",
    [
        pytest.param("http", id="absolute"),
        pytest.param("", id="scheme-relative"),
    ],
)
async def test_reject_cross_origin_advertised_target(
    hass: HomeAssistant,
    aiohttp_server: Callable[[], TestServer],
    redfish_app: web.Application,
    scheme: str,
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
    client = RedfishApi(
        async_get_clientsession(hass),
        str(server.make_url("")),
        "user",
        "password",
    )

    target = malicious_server.make_url("/redfish/reset").with_scheme(scheme)
    with pytest.raises(RedfishError):
        await client.async_reset(str(target), "On")

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
    client = RedfishApi(
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


async def test_coordinator_authentication_error_requests_reauthentication(
    init_integration: MockConfigEntry,
) -> None:
    """Test polling authentication errors request reauthentication."""
    coordinator = init_integration.runtime_data
    with (
        patch.object(
            coordinator.client, "async_discover", side_effect=RedfishAuthError
        ),
        pytest.raises(ConfigEntryAuthFailed) as exc_info,
    ):
        await coordinator._async_update_data()

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "authentication_failed"


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
    client = RedfishApi(
        async_get_clientsession(hass),
        str(server.make_url("")),
        "user",
        "password",
    )

    with pytest.raises(expected_exception):
        await client.async_get_systems()


async def test_get_rejects_malformed_json(
    hass: HomeAssistant,
    aiohttp_server: Callable[[], TestServer],
) -> None:
    """Test malformed JSON is translated to a Redfish error."""
    app = web.Application()

    async def response(_request: web.Request) -> web.Response:
        return web.Response(text="{", content_type="application/json")

    app.router.add_get("/{path:.*}", response)
    server = await aiohttp_server(app)
    client = RedfishApi(
        async_get_clientsession(hass),
        str(server.make_url("")),
        "user",
        "password",
    )

    with pytest.raises(RedfishError):
        await client.async_get_systems()
