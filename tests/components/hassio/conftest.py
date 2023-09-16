"""Fixtures for Hass.io."""
import os
import re
from unittest.mock import Mock, patch

import pytest

from homeassistant.components.hassio.handler import HassIO, HassioAPIError
from homeassistant.core import CoreState
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.setup import async_setup_component

from . import SUPERVISOR_TOKEN

from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture(autouse=True)
def disable_security_filter():
    """Disable the security filter to ensure the integration is secure."""
    with patch(
        "homeassistant.components.http.security_filter.FILTERS",
        re.compile("not-matching-anything"),
    ):
        yield


@pytest.fixture
def hassio_env():
    """Fixture to inject hassio env."""
    with patch.dict(os.environ, {"SUPERVISOR": "127.0.0.1"}), patch(
        "homeassistant.components.hassio.HassIO.is_connected",
        return_value={"result": "ok", "data": {}},
    ), patch.dict(os.environ, {"SUPERVISOR_TOKEN": SUPERVISOR_TOKEN}), patch(
        "homeassistant.components.hassio.HassIO.get_info",
        Mock(side_effect=HassioAPIError()),
    ):
        yield


@pytest.fixture
def hassio_stubs(hassio_env, hass, hass_client, aioclient_mock):
    """Create mock hassio http client."""
    with patch(
        "homeassistant.components.hassio.HassIO.update_hass_api",
        return_value={"result": "ok"},
    ) as hass_api, patch(
        "homeassistant.components.hassio.HassIO.update_hass_timezone",
        return_value={"result": "ok"},
    ), patch(
        "homeassistant.components.hassio.HassIO.get_info",
        side_effect=HassioAPIError(),
    ), patch(
        "homeassistant.components.hassio.HassIO.get_ingress_panels",
        return_value={"panels": []},
    ), patch(
        "homeassistant.components.hassio.issues.SupervisorIssues.setup"
    ), patch(
        "homeassistant.components.hassio.HassIO.refresh_updates"
    ):
        hass.state = CoreState.starting
        hass.loop.run_until_complete(async_setup_component(hass, "hassio", {}))

    return hass_api.call_args[0][1]


@pytest.fixture
def hassio_client(hassio_stubs, hass, hass_client):
    """Return a Hass.io HTTP client."""
    return hass.loop.run_until_complete(hass_client())


@pytest.fixture
def hassio_noauth_client(hassio_stubs, hass, aiohttp_client):
    """Return a Hass.io HTTP client without auth."""
    return hass.loop.run_until_complete(aiohttp_client(hass.http.app))


@pytest.fixture
async def hassio_client_supervisor(hass, aiohttp_client, hassio_stubs):
    """Return an authenticated HTTP client."""
    access_token = hass.auth.async_create_access_token(hassio_stubs)
    return await aiohttp_client(
        hass.http.app,
        headers={"Authorization": f"Bearer {access_token}"},
    )


@pytest.fixture
async def hassio_handler(hass, aioclient_mock):
    """Create mock hassio handler."""
    with patch.dict(os.environ, {"SUPERVISOR_TOKEN": SUPERVISOR_TOKEN}):
        yield HassIO(hass.loop, async_get_clientsession(hass), "127.0.0.1")


@pytest.fixture
def all_setup_requests(
    aioclient_mock: AiohttpClientMocker, request: pytest.FixtureRequest
):
    """Mock all setup requests."""
    include_addons = hasattr(request, "param") and request.param.get(
        "include_addons", False
    )

    aioclient_mock.post("http://127.0.0.1/homeassistant/options", json={"result": "ok"})
    aioclient_mock.get("http://127.0.0.1/supervisor/ping", json={"result": "ok"})
    aioclient_mock.post("http://127.0.0.1/supervisor/options", json={"result": "ok"})
    aioclient_mock.get(
        "http://127.0.0.1/info",
        json={
            "result": "ok",
            "data": {
                "supervisor": "222",
                "homeassistant": "0.110.0",
                "hassos": "1.2.3",
            },
        },
    )
    aioclient_mock.get(
        "http://127.0.0.1/store",
        json={
            "result": "ok",
            "data": {"addons": [], "repositories": []},
        },
    )
    aioclient_mock.get(
        "http://127.0.0.1/host/info",
        json={
            "result": "ok",
            "data": {
                "result": "ok",
                "data": {
                    "chassis": "vm",
                    "operating_system": "Debian GNU/Linux 10 (buster)",
                    "kernel": "4.19.0-6-amd64",
                },
            },
        },
    )
    aioclient_mock.get(
        "http://127.0.0.1/core/info",
        json={"result": "ok", "data": {"version_latest": "1.0.0", "version": "1.0.0"}},
    )
    aioclient_mock.get(
        "http://127.0.0.1/os/info",
        json={
            "result": "ok",
            "data": {
                "version_latest": "1.0.0",
                "version": "1.0.0",
                "update_available": False,
            },
        },
    )
    aioclient_mock.get(
        "http://127.0.0.1/supervisor/info",
        json={
            "result": "ok",
            "data": {
                "result": "ok",
                "version": "1.0.0",
                "version_latest": "1.0.0",
                "auto_update": True,
                "addons": [
                    {
                        "name": "test",
                        "slug": "test",
                        "update_available": False,
                        "version": "1.0.0",
                        "version_latest": "1.0.0",
                        "repository": "core",
                        "state": "started",
                        "icon": False,
                    },
                    {
                        "name": "test2",
                        "slug": "test2",
                        "update_available": False,
                        "version": "1.0.0",
                        "version_latest": "1.0.0",
                        "repository": "core",
                        "state": "started",
                        "icon": False,
                    },
                ]
                if include_addons
                else [],
            },
        },
    )
    aioclient_mock.get(
        "http://127.0.0.1/ingress/panels", json={"result": "ok", "data": {"panels": {}}}
    )
    aioclient_mock.post("http://127.0.0.1/refresh_updates", json={"result": "ok"})

    aioclient_mock.get("http://127.0.0.1/addons/test/changelog", text="")
    aioclient_mock.get(
        "http://127.0.0.1/addons/test/info",
        json={
            "result": "ok",
            "data": {
                "name": "test",
                "slug": "test",
                "update_available": False,
                "version": "1.0.0",
                "version_latest": "1.0.0",
                "repository": "core",
                "state": "started",
                "icon": False,
                "url": "https://github.com/home-assistant/addons/test",
                "auto_update": True,
            },
        },
    )
    aioclient_mock.get("http://127.0.0.1/addons/test2/changelog", text="")
    aioclient_mock.get(
        "http://127.0.0.1/addons/test2/info",
        json={
            "result": "ok",
            "data": {
                "name": "test2",
                "slug": "test2",
                "update_available": False,
                "version": "1.0.0",
                "version_latest": "1.0.0",
                "repository": "core",
                "state": "started",
                "icon": False,
                "url": "https://github.com",
                "auto_update": False,
            },
        },
    )
    aioclient_mock.get(
        "http://127.0.0.1/core/stats",
        json={
            "result": "ok",
            "data": {
                "cpu_percent": 0.99,
                "memory_usage": 182611968,
                "memory_limit": 3977146368,
                "memory_percent": 4.59,
                "network_rx": 362570232,
                "network_tx": 82374138,
                "blk_read": 46010945536,
                "blk_write": 15051526144,
            },
        },
    )
    aioclient_mock.get(
        "http://127.0.0.1/supervisor/stats",
        json={
            "result": "ok",
            "data": {
                "cpu_percent": 0.99,
                "memory_usage": 182611968,
                "memory_limit": 3977146368,
                "memory_percent": 4.59,
                "network_rx": 362570232,
                "network_tx": 82374138,
                "blk_read": 46010945536,
                "blk_write": 15051526144,
            },
        },
    )
    aioclient_mock.get(
        "http://127.0.0.1/addons/test/stats",
        json={
            "result": "ok",
            "data": {
                "cpu_percent": 0.99,
                "memory_usage": 182611968,
                "memory_limit": 3977146368,
                "memory_percent": 4.59,
                "network_rx": 362570232,
                "network_tx": 82374138,
                "blk_read": 46010945536,
                "blk_write": 15051526144,
            },
        },
    )
    aioclient_mock.get(
        "http://127.0.0.1/addons/test2/stats",
        json={
            "result": "ok",
            "data": {
                "cpu_percent": 0.8,
                "memory_usage": 51941376,
                "memory_limit": 3977146368,
                "memory_percent": 1.31,
                "network_rx": 31338284,
                "network_tx": 15692900,
                "blk_read": 740077568,
                "blk_write": 6004736,
            },
        },
    )
