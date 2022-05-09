"""Set up some common test helper things."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
import functools
import logging
import ssl
import threading
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from aiohttp.test_utils import make_mocked_request
import freezegun
import multidict
import pytest
import pytest_socket
import requests_mock as _requests_mock

from homeassistant import core as ha, loader, runner, util
from homeassistant.auth.const import GROUP_ID_ADMIN, GROUP_ID_READ_ONLY
from homeassistant.auth.models import Credentials
from homeassistant.auth.providers import homeassistant, legacy_api_password
from homeassistant.components import mqtt, recorder
from homeassistant.components.websocket_api.auth import (
    TYPE_AUTH,
    TYPE_AUTH_OK,
    TYPE_AUTH_REQUIRED,
)
from homeassistant.components.websocket_api.http import URL
from homeassistant.const import HASSIO_USER_NAME
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util, location

from tests.ignore_uncaught_exceptions import IGNORE_UNCAUGHT_EXCEPTIONS

pytest.register_assert_rewrite("tests.common")

from tests.common import (  # noqa: E402, isort:skip
    CLIENT_ID,
    INSTANCES,
    MockConfigEntry,
    MockUser,
    SetupRecorderInstanceT,
    async_fire_mqtt_message,
    async_test_home_assistant,
    get_test_home_assistant,
    init_recorder_component,
    mock_storage as mock_storage,
)
from tests.test_util.aiohttp import mock_aiohttp_client  # noqa: E402, isort:skip
from tests.components.recorder.common import (  # noqa: E402, isort:skip
    async_recorder_block_till_done,
)

_LOGGER = logging.getLogger(__name__)

logging.basicConfig(level=logging.DEBUG)
logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)

asyncio.set_event_loop_policy(runner.HassEventLoopPolicy(False))
# Disable fixtures overriding our beautiful policy
asyncio.set_event_loop_policy = lambda policy: None


def pytest_configure(config):
    """Register marker for tests that log exceptions."""
    config.addinivalue_line(
        "markers", "no_fail_on_log_exception: mark test to not fail on logged exception"
    )


def pytest_runtest_setup():
    """Prepare pytest_socket and freezegun.

    pytest_socket:
    Throw if tests attempt to open sockets.

    allow_unix_socket is set to True because it's needed by asyncio.
    Important: socket_allow_hosts must be called before disable_socket, otherwise all
    destinations will be allowed.

    freezegun:
    Modified to include https://github.com/spulec/freezegun/pull/424
    """
    pytest_socket.socket_allow_hosts(["127.0.0.1"])
    pytest_socket.disable_socket(allow_unix_socket=True)

    freezegun.api.datetime_to_fakedatetime = ha_datetime_to_fakedatetime
    freezegun.api.FakeDatetime = HAFakeDatetime


def ha_datetime_to_fakedatetime(datetime):
    """Convert datetime to FakeDatetime.

    Modified to include https://github.com/spulec/freezegun/pull/424.
    """
    return freezegun.api.FakeDatetime(
        datetime.year,
        datetime.month,
        datetime.day,
        datetime.hour,
        datetime.minute,
        datetime.second,
        datetime.microsecond,
        datetime.tzinfo,
        fold=datetime.fold,
    )


class HAFakeDatetime(freezegun.api.FakeDatetime):
    """Modified to include https://github.com/spulec/freezegun/pull/424."""

    @classmethod
    def now(cls, tz=None):
        """Return frozen now."""
        now = cls._time_to_freeze() or freezegun.api.real_datetime.now()
        if tz:
            result = tz.fromutc(now.replace(tzinfo=tz))
        else:
            result = now

        # Add the _tz_offset only if it's non-zero to preserve fold
        if cls._tz_offset():
            result += cls._tz_offset()

        return ha_datetime_to_fakedatetime(result)


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
    threads_before = frozenset(threading.enumerate())

    yield

    if len(INSTANCES) >= 2:
        count = len(INSTANCES)
        for inst in INSTANCES:
            inst.stop()
        pytest.exit(f"Detected non stopped instances ({count}), aborting test run")

    threads = frozenset(threading.enumerate()) - threads_before
    assert not threads


@pytest.fixture(autouse=True)
def bcrypt_cost():
    """Run with reduced rounds during tests, to speed up uses."""
    import bcrypt

    gensalt_orig = bcrypt.gensalt

    def gensalt_mock(rounds=12, prefix=b"2b"):
        return gensalt_orig(4, prefix)

    bcrypt.gensalt = gensalt_mock
    yield
    bcrypt.gensalt = gensalt_orig


@pytest.fixture
def hass_storage():
    """Fixture to mock storage."""
    with mock_storage() as stored_data:
        yield stored_data


@pytest.fixture
def load_registries():
    """Fixture to control the loading of registries when setting up the hass fixture.

    To avoid loading the registries, tests can be marked with:
    @pytest.mark.parametrize("load_registries", [False])
    """
    return True


@pytest.fixture
def hass(loop, load_registries, hass_storage, request):
    """Fixture to provide a test instance of Home Assistant."""

    orig_tz = dt_util.DEFAULT_TIME_ZONE

    def exc_handle(loop, context):
        """Handle exceptions by rethrowing them, which will fail the test."""
        # Most of these contexts will contain an exception, but not all.
        # The docs note the key as "optional"
        # See https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.call_exception_handler
        if "exception" in context:
            exceptions.append(context["exception"])
        else:
            exceptions.append(
                Exception(
                    "Received exception handler without exception, but with message: %s"
                    % context["message"]
                )
            )
        orig_exception_handler(loop, context)

    exceptions = []
    hass = loop.run_until_complete(async_test_home_assistant(loop, load_registries))
    orig_exception_handler = loop.get_exception_handler()
    loop.set_exception_handler(exc_handle)

    yield hass

    loop.run_until_complete(hass.async_stop(force=True))

    # Restore timezone, it is set when creating the hass object
    dt_util.DEFAULT_TIME_ZONE = orig_tz

    for ex in exceptions:
        if (
            request.module.__name__,
            request.function.__name__,
        ) in IGNORE_UNCAUGHT_EXCEPTIONS:
            continue
        raise ex


@pytest.fixture
async def stop_hass():
    """Make sure all hass are stopped."""
    orig_hass = ha.HomeAssistant

    created = []

    def mock_hass():
        hass_inst = orig_hass()
        created.append(hass_inst)
        return hass_inst

    with patch("homeassistant.core.HomeAssistant", mock_hass):
        yield

    for hass_inst in created:
        if hass_inst.state == ha.CoreState.stopped:
            continue

        with patch.object(hass_inst.loop, "stop"):
            await hass_inst.async_block_till_done()
            await hass_inst.async_stop(force=True)


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
        side_effect=lambda *args: devices,
    ):
        yield devices


@pytest.fixture
async def hass_admin_credential(hass, local_auth):
    """Provide credentials for admin user."""
    return Credentials(
        id="mock-credential-id",
        auth_provider_type="homeassistant",
        auth_provider_id=None,
        data={"username": "admin"},
        is_new=False,
    )


@pytest.fixture
async def hass_access_token(hass, hass_admin_user, hass_admin_credential):
    """Return an access token to access Home Assistant."""
    await hass.auth.async_link_user(hass_admin_user, hass_admin_credential)

    refresh_token = await hass.auth.async_create_refresh_token(
        hass_admin_user, CLIENT_ID, credential=hass_admin_credential
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
def hass_read_only_access_token(hass, hass_read_only_user, local_auth):
    """Return a Home Assistant read only user."""
    credential = Credentials(
        id="mock-readonly-credential-id",
        auth_provider_type="homeassistant",
        auth_provider_id=None,
        data={"username": "readonly"},
        is_new=False,
    )
    hass_read_only_user.credentials.append(credential)

    refresh_token = hass.loop.run_until_complete(
        hass.auth.async_create_refresh_token(
            hass_read_only_user, CLIENT_ID, credential=credential
        )
    )
    return hass.auth.async_create_access_token(refresh_token)


@pytest.fixture
def hass_supervisor_user(hass, local_auth):
    """Return the Home Assistant Supervisor user."""
    admin_group = hass.loop.run_until_complete(
        hass.auth.async_get_group(GROUP_ID_ADMIN)
    )
    return MockUser(
        name=HASSIO_USER_NAME, groups=[admin_group], system_generated=True
    ).add_to_hass(hass)


@pytest.fixture
def hass_supervisor_access_token(hass, hass_supervisor_user, local_auth):
    """Return a Home Assistant Supervisor access token."""
    refresh_token = hass.loop.run_until_complete(
        hass.auth.async_create_refresh_token(hass_supervisor_user)
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
    hass.loop.run_until_complete(prv.async_initialize())
    hass.auth._providers[(prv.type, prv.id)] = prv
    return prv


@pytest.fixture
def hass_client(hass, aiohttp_client, hass_access_token, socket_enabled):
    """Return an authenticated HTTP client."""

    async def auth_client():
        """Return an authenticated client."""
        return await aiohttp_client(
            hass.http.app, headers={"Authorization": f"Bearer {hass_access_token}"}
        )

    return auth_client


@pytest.fixture
def hass_client_no_auth(hass, aiohttp_client, socket_enabled):
    """Return an unauthenticated HTTP client."""

    async def client():
        """Return an authenticated client."""
        return await aiohttp_client(hass.http.app)

    return client


@pytest.fixture
def current_request():
    """Mock current request."""
    with patch("homeassistant.components.http.current_request") as mock_request_context:
        mocked_request = make_mocked_request(
            "GET",
            "/some/request",
            headers={"Host": "example.com"},
            sslcontext=ssl.SSLContext(ssl.PROTOCOL_TLS),
        )
        mock_request_context.get.return_value = mocked_request
        yield mock_request_context


@pytest.fixture
def current_request_with_host(current_request):
    """Mock current request with a host header."""
    new_headers = multidict.CIMultiDict(current_request.get.return_value.headers)
    new_headers[config_entry_oauth2_flow.HEADER_FRONTEND_BASE] = "https://example.com"
    current_request.get.return_value = current_request.get.return_value.clone(
        headers=new_headers
    )


@pytest.fixture
def hass_ws_client(aiohttp_client, hass_access_token, hass, socket_enabled):
    """Websocket client fixture connected to websocket server."""

    async def create_client(hass=hass, access_token=hass_access_token):
        """Create a websocket client."""
        assert await async_setup_component(hass, "websocket_api", {})
        client = await aiohttp_client(hass.http.app)
        websocket = await client.ws_connect(URL)
        auth_resp = await websocket.receive_json()
        assert auth_resp["type"] == TYPE_AUTH_REQUIRED

        if access_token is None:
            await websocket.send_json({"type": TYPE_AUTH, "access_token": "incorrect"})
        else:
            await websocket.send_json({"type": TYPE_AUTH, "access_token": access_token})

        auth_ok = await websocket.receive_json()
        assert auth_ok["type"] == TYPE_AUTH_OK

        # wrap in client
        websocket.client = client
        return websocket

    return create_client


@pytest.fixture(autouse=True)
def fail_on_log_exception(request, monkeypatch):
    """Fixture to fail if a callback wrapped by catch_log_exception or coroutine wrapped by async_create_catching_coro throws."""
    if "no_fail_on_log_exception" in request.keywords:
        return

    def log_exception(format_err, *args):
        raise

    monkeypatch.setattr("homeassistant.util.logging.log_exception", log_exception)


@pytest.fixture
def mqtt_config():
    """Fixture to allow overriding MQTT config."""
    return None


@pytest.fixture
def mqtt_client_mock(hass):
    """Fixture to mock MQTT client."""

    mid = 0

    def get_mid():
        nonlocal mid
        mid += 1
        return mid

    class FakeInfo:
        def __init__(self, mid):
            self.mid = mid
            self.rc = 0

    with patch("paho.mqtt.client.Client") as mock_client:

        @ha.callback
        def _async_fire_mqtt_message(topic, payload, qos, retain):
            async_fire_mqtt_message(hass, topic, payload, qos, retain)
            mid = get_mid()
            mock_client.on_publish(0, 0, mid)
            return FakeInfo(mid)

        def _subscribe(topic, qos=0):
            mid = get_mid()
            mock_client.on_subscribe(0, 0, mid)
            return (0, mid)

        def _unsubscribe(topic):
            mid = get_mid()
            mock_client.on_unsubscribe(0, 0, mid)
            return (0, mid)

        mock_client = mock_client.return_value
        mock_client.connect.return_value = 0
        mock_client.subscribe.side_effect = _subscribe
        mock_client.unsubscribe.side_effect = _unsubscribe
        mock_client.publish.side_effect = _async_fire_mqtt_message
        yield mock_client


@pytest.fixture
async def mqtt_mock(hass, mqtt_client_mock, mqtt_config):
    """Fixture to mock MQTT component."""
    if mqtt_config is None:
        mqtt_config = {mqtt.CONF_BROKER: "mock-broker", mqtt.CONF_BIRTH_MESSAGE: {}}

    await hass.async_block_till_done()

    entry = MockConfigEntry(
        data=mqtt_config,
        domain=mqtt.DOMAIN,
        title="Tasmota",
    )

    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    mqtt_component_mock = MagicMock(
        return_value=hass.data["mqtt"],
        spec_set=hass.data["mqtt"],
        wraps=hass.data["mqtt"],
    )
    mqtt_component_mock.conf = hass.data["mqtt"].conf  # For diagnostics
    mqtt_component_mock._mqttc = mqtt_client_mock
    # connected set to True to get a more realistics behavior when subscribing
    hass.data["mqtt"].connected = True

    hass.data["mqtt"] = mqtt_component_mock
    component = hass.data["mqtt"]
    component.reset_mock()
    return component


@pytest.fixture(autouse=True)
def mock_get_source_ip():
    """Mock network util's async_get_source_ip."""
    with patch(
        "homeassistant.components.network.util.async_get_source_ip",
        return_value="10.10.10.10",
    ):
        yield


@pytest.fixture
def mock_zeroconf():
    """Mock zeroconf."""
    with patch("homeassistant.components.zeroconf.HaZeroconf", autospec=True), patch(
        "homeassistant.components.zeroconf.HaAsyncServiceBrowser", autospec=True
    ):
        yield


@pytest.fixture
def mock_async_zeroconf(mock_zeroconf):
    """Mock AsyncZeroconf."""
    with patch("homeassistant.components.zeroconf.HaAsyncZeroconf") as mock_aiozc:
        zc = mock_aiozc.return_value
        zc.async_unregister_service = AsyncMock()
        zc.async_register_service = AsyncMock()
        zc.async_update_service = AsyncMock()
        zc.zeroconf.async_wait_for_start = AsyncMock()
        zc.zeroconf.done = False
        zc.async_close = AsyncMock()
        zc.ha_async_close = AsyncMock()
        yield zc


@pytest.fixture
def enable_custom_integrations(hass):
    """Enable custom integrations defined in the test dir."""
    hass.data.pop(loader.DATA_CUSTOM_COMPONENTS)


@pytest.fixture
def enable_statistics():
    """Fixture to control enabling of recorder's statistics compilation.

    To enable statistics, tests can be marked with:
    @pytest.mark.parametrize("enable_statistics", [True])
    """
    return False


@pytest.fixture
def enable_nightly_purge():
    """Fixture to control enabling of recorder's nightly purge job.

    To enable nightly purging, tests can be marked with:
    @pytest.mark.parametrize("enable_nightly_purge", [True])
    """
    return False


@pytest.fixture
def recorder_config():
    """Fixture to override recorder config.

    To override the config, tests can be marked with:
    @pytest.mark.parametrize("recorder_config", [{...}])
    """
    return None


@pytest.fixture
def hass_recorder(enable_nightly_purge, enable_statistics, hass_storage):
    """Home Assistant fixture with in-memory recorder."""
    original_tz = dt_util.DEFAULT_TIME_ZONE

    hass = get_test_home_assistant()
    nightly = recorder.Recorder.async_nightly_tasks if enable_nightly_purge else None
    stats = recorder.Recorder.async_periodic_statistics if enable_statistics else None
    with patch(
        "homeassistant.components.recorder.Recorder.async_nightly_tasks",
        side_effect=nightly,
        autospec=True,
    ), patch(
        "homeassistant.components.recorder.Recorder.async_periodic_statistics",
        side_effect=stats,
        autospec=True,
    ):

        def setup_recorder(config=None):
            """Set up with params."""
            init_recorder_component(hass, config)
            hass.start()
            hass.block_till_done()
            hass.data[recorder.DATA_INSTANCE].block_till_done()
            return hass

        yield setup_recorder
        hass.stop()

    # Restore timezone, it is set when creating the hass object
    dt_util.DEFAULT_TIME_ZONE = original_tz


async def _async_init_recorder_component(hass, add_config=None):
    """Initialize the recorder asynchronously."""
    config = dict(add_config) if add_config else {}
    if recorder.CONF_DB_URL not in config:
        config[recorder.CONF_DB_URL] = "sqlite://"  # In memory DB
        if recorder.CONF_COMMIT_INTERVAL not in config:
            config[recorder.CONF_COMMIT_INTERVAL] = 0

    with patch("homeassistant.components.recorder.ALLOW_IN_MEMORY_DB", True), patch(
        "homeassistant.components.recorder.migration.migrate_schema"
    ):
        assert await async_setup_component(
            hass, recorder.DOMAIN, {recorder.DOMAIN: config}
        )
        assert recorder.DOMAIN in hass.config.components
    _LOGGER.info(
        "Test recorder successfully started, database location: %s",
        config[recorder.CONF_DB_URL],
    )


@pytest.fixture
async def async_setup_recorder_instance(
    enable_nightly_purge, enable_statistics
) -> AsyncGenerator[SetupRecorderInstanceT, None]:
    """Yield callable to setup recorder instance."""

    async def async_setup_recorder(
        hass: HomeAssistant, config: ConfigType | None = None
    ) -> recorder.Recorder:
        """Setup and return recorder instance."""  # noqa: D401
        nightly = (
            recorder.Recorder.async_nightly_tasks if enable_nightly_purge else None
        )
        stats = (
            recorder.Recorder.async_periodic_statistics if enable_statistics else None
        )
        with patch(
            "homeassistant.components.recorder.Recorder.async_nightly_tasks",
            side_effect=nightly,
            autospec=True,
        ), patch(
            "homeassistant.components.recorder.Recorder.async_periodic_statistics",
            side_effect=stats,
            autospec=True,
        ):
            await _async_init_recorder_component(hass, config)
            await hass.async_block_till_done()
            instance = hass.data[recorder.DATA_INSTANCE]
            # The recorder's worker is not started until Home Assistant is running
            if hass.state == CoreState.running:
                await async_recorder_block_till_done(hass)
            return instance

    return async_setup_recorder


@pytest.fixture
async def recorder_mock(recorder_config, async_setup_recorder_instance, hass):
    """Fixture with in-memory recorder."""
    await async_setup_recorder_instance(hass, recorder_config)


@pytest.fixture
def mock_integration_frame():
    """Mock as if we're calling code from inside an integration."""
    correct_frame = Mock(
        filename="/home/paulus/homeassistant/components/hue/light.py",
        lineno="23",
        line="self.light.is_on",
    )
    with patch(
        "homeassistant.helpers.frame.extract_stack",
        return_value=[
            Mock(
                filename="/home/paulus/homeassistant/core.py",
                lineno="23",
                line="do_something()",
            ),
            correct_frame,
            Mock(
                filename="/home/paulus/aiohue/lights.py",
                lineno="2",
                line="something()",
            ),
        ],
    ):
        yield correct_frame
