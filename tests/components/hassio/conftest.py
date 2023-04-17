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
