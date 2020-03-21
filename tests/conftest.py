"""Set up some common test helper things."""
import functools
import logging
from unittest.mock import patch

import pytest
import requests_mock as _requests_mock

from homeassistant import util
from homeassistant.auth.const import GROUP_ID_ADMIN, GROUP_ID_READ_ONLY
from homeassistant.auth.providers import homeassistant, legacy_api_password
from homeassistant.components.websocket_api.auth import (
    TYPE_AUTH,
    TYPE_AUTH_OK,
    TYPE_AUTH_REQUIRED,
)
from homeassistant.components.websocket_api.http import URL
from homeassistant.setup import async_setup_component
from homeassistant.util import location

pytest.register_assert_rewrite("tests.common")

from tests.common import (  # noqa: E402, isort:skip
    CLIENT_ID,
    INSTANCES,
    MockUser,
    async_test_home_assistant,
    mock_coro,
    mock_storage as mock_storage,
)
from tests.test_util.aiohttp import mock_aiohttp_client  # noqa: E402, isort:skip


logging.basicConfig(level=logging.DEBUG)
logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)


def check_real(func):
    """Force a function to require a keyword _test_real to be passed in."""

    @functools.wraps(func)
    async def guard_func(*args, **kwargs):
        real = kwargs.pop("_test_real", None)

        if not real:
            raise Exception(
                'Forgot to mock or pass "_test_real=True" to %s', func.__name__
            )

        return await func(*args, **kwargs)

    return guard_func


# Guard a few functions that would make network connections
location.async_detect_location_info = check_real(location.async_detect_location_info)
util.get_local_ip = lambda: "127.0.0.1"


@pytest.fixture(autouse=True)
def verify_cleanup():
    """Verify that the test has cleaned up resources correctly."""
    yield

    if len(INSTANCES) >= 2:
        count = len(INSTANCES)
        for inst in INSTANCES:
            inst.stop()
        pytest.exit(f"Detected non stopped instances ({count}), aborting test run")


@pytest.fixture
def hass_storage():
    """Fixture to mock storage."""
    with mock_storage() as stored_data:
        yield stored_data


@pytest.fixture
def hass(loop, hass_storage):
    """Fixture to provide a test instance of Home Assistant."""
    hass = loop.run_until_complete(async_test_home_assistant(loop))

    yield hass

    loop.run_until_complete(hass.async_stop(force=True))


@pytest.fixture
def requests_mock():
    """Fixture to provide a requests mocker."""
    with _requests_mock.mock() as m:
        yield m


@pytest.fixture
def aioclient_mock():
    """Fixture to mock aioclient calls."""
    with mock_aiohttp_client() as mock_session:
        yield mock_session


@pytest.fixture
def mock_device_tracker_conf():
    """Prevent device tracker from reading/writing data."""
    devices = []

    async def mock_update_config(path, id, entity):
        devices.append(entity)

    with patch(
        "homeassistant.components.device_tracker.legacy"
        ".DeviceTracker.async_update_config",
        side_effect=mock_update_config,
    ), patch(
        "homeassistant.components.device_tracker.legacy.async_load_config",
        side_effect=lambda *args: mock_coro(devices),
    ):
        yield devices


@pytest.fixture
def hass_access_token(hass, hass_admin_user):
    """Return an access token to access Home Assistant."""
    refresh_token = hass.loop.run_until_complete(
        hass.auth.async_create_refresh_token(hass_admin_user, CLIENT_ID)
    )
    return hass.auth.async_create_access_token(refresh_token)


@pytest.fixture
def hass_owner_user(hass, local_auth):
    """Return a Home Assistant admin user."""
    return MockUser(is_owner=True).add_to_hass(hass)


@pytest.fixture
def hass_admin_user(hass, local_auth):
    """Return a Home Assistant admin user."""
    admin_group = hass.loop.run_until_complete(
        hass.auth.async_get_group(GROUP_ID_ADMIN)
    )
    return MockUser(groups=[admin_group]).add_to_hass(hass)


@pytest.fixture
def hass_read_only_user(hass, local_auth):
    """Return a Home Assistant read only user."""
    read_only_group = hass.loop.run_until_complete(
        hass.auth.async_get_group(GROUP_ID_READ_ONLY)
    )
    return MockUser(groups=[read_only_group]).add_to_hass(hass)


@pytest.fixture
def hass_read_only_access_token(hass, hass_read_only_user):
    """Return a Home Assistant read only user."""
    refresh_token = hass.loop.run_until_complete(
        hass.auth.async_create_refresh_token(hass_read_only_user, CLIENT_ID)
    )
    return hass.auth.async_create_access_token(refresh_token)


@pytest.fixture
def legacy_auth(hass):
    """Load legacy API password provider."""
    prv = legacy_api_password.LegacyApiPasswordAuthProvider(
        hass,
        hass.auth._store,
        {"type": "legacy_api_password", "api_password": "test-password"},
    )
    hass.auth._providers[(prv.type, prv.id)] = prv
    return prv


@pytest.fixture
def local_auth(hass):
    """Load local auth provider."""
    prv = homeassistant.HassAuthProvider(
        hass, hass.auth._store, {"type": "homeassistant"}
    )
    hass.auth._providers[(prv.type, prv.id)] = prv
    return prv


@pytest.fixture
def hass_client(hass, aiohttp_client, hass_access_token):
    """Return an authenticated HTTP client."""

    async def auth_client():
        """Return an authenticated client."""
        return await aiohttp_client(
            hass.http.app, headers={"Authorization": f"Bearer {hass_access_token}"},
        )

    return auth_client


@pytest.fixture
def hass_ws_client(aiohttp_client, hass_access_token):
    """Websocket client fixture connected to websocket server."""

    async def create_client(hass, access_token=hass_access_token):
        """Create a websocket client."""
        assert await async_setup_component(hass, "websocket_api", {})

        client = await aiohttp_client(hass.http.app)

        with patch("homeassistant.components.http.auth.setup_auth"):
            websocket = await client.ws_connect(URL)
            auth_resp = await websocket.receive_json()
            assert auth_resp["type"] == TYPE_AUTH_REQUIRED

            if access_token is None:
                await websocket.send_json(
                    {"type": TYPE_AUTH, "access_token": "incorrect"}
                )
            else:
                await websocket.send_json(
                    {"type": TYPE_AUTH, "access_token": access_token}
                )

            auth_ok = await websocket.receive_json()
            assert auth_ok["type"] == TYPE_AUTH_OK

        # wrap in client
        websocket.client = client
        return websocket

    return create_client
