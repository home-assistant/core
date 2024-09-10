"""Set up some common test helper things."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Callable, Coroutine, Generator
from contextlib import AsyncExitStack, asynccontextmanager, contextmanager
import datetime
import functools
import gc
import itertools
import logging
import os
import reprlib
from shutil import rmtree
import sqlite3
import ssl
import threading
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import AsyncMock, MagicMock, Mock, _patch, patch

from aiohttp import client
from aiohttp.test_utils import (
    BaseTestServer,
    TestClient,
    TestServer,
    make_mocked_request,
)
from aiohttp.typedefs import JSONDecoder
from aiohttp.web import Application
import bcrypt
import freezegun
import multidict
import pytest
import pytest_socket
import requests_mock
import respx
from syrupy.assertion import SnapshotAssertion

from homeassistant import block_async_io
from homeassistant.exceptions import ServiceNotFound

# Setup patching of recorder functions before any other Home Assistant imports
from . import patch_recorder  # noqa: F401, isort:skip

# Setup patching of dt_util time functions before any other Home Assistant imports
from . import patch_time  # noqa: F401, isort:skip

from homeassistant import core as ha, loader, runner
from homeassistant.auth.const import GROUP_ID_ADMIN, GROUP_ID_READ_ONLY
from homeassistant.auth.models import Credentials
from homeassistant.auth.providers import homeassistant
from homeassistant.components.device_tracker.legacy import Device
from homeassistant.components.websocket_api.auth import (
    TYPE_AUTH,
    TYPE_AUTH_OK,
    TYPE_AUTH_REQUIRED,
)
from homeassistant.components.websocket_api.http import URL
from homeassistant.config import YAML_CONFIG_FILE
from homeassistant.config_entries import ConfigEntries, ConfigEntry, ConfigEntryState
from homeassistant.const import BASE_PLATFORMS, HASSIO_USER_NAME
from homeassistant.core import (
    Context,
    CoreState,
    HassJob,
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
)
from homeassistant.helpers import (
    area_registry as ar,
    category_registry as cr,
    config_entry_oauth2_flow,
    device_registry as dr,
    entity_registry as er,
    floor_registry as fr,
    issue_registry as ir,
    label_registry as lr,
    recorder as recorder_helper,
)
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.translation import _TranslationsCacheData
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util, location
from homeassistant.util.async_ import create_eager_task, get_scheduled_timer_handles
from homeassistant.util.json import json_loads

from .ignore_uncaught_exceptions import IGNORE_UNCAUGHT_EXCEPTIONS
from .syrupy import HomeAssistantSnapshotExtension
from .typing import (
    ClientSessionGenerator,
    MockHAClientWebSocket,
    MqttMockHAClient,
    MqttMockHAClientGenerator,
    MqttMockPahoClient,
    RecorderInstanceGenerator,
    WebSocketGenerator,
)

if TYPE_CHECKING:
    # Local import to avoid processing recorder and SQLite modules when running a
    # testcase which does not use the recorder.
    from homeassistant.components import recorder

pytest.register_assert_rewrite("tests.common")

from .common import (  # noqa: E402, isort:skip
    CLIENT_ID,
    INSTANCES,
    MockConfigEntry,
    MockUser,
    async_fire_mqtt_message,
    async_test_home_assistant,
    mock_storage,
    patch_yaml_files,
    extract_stack_to_frame,
)
from .test_util.aiohttp import (  # noqa: E402, isort:skip
    AiohttpClientMocker,
    mock_aiohttp_client,
)

_LOGGER = logging.getLogger(__name__)

logging.basicConfig(level=logging.INFO)
logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)

asyncio.set_event_loop_policy(runner.HassEventLoopPolicy(False))
# Disable fixtures overriding our beautiful policy
asyncio.set_event_loop_policy = lambda policy: None


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register custom pytest options."""
    parser.addoption("--dburl", action="store", default="sqlite://")


def pytest_configure(config: pytest.Config) -> None:
    """Register marker for tests that log exceptions."""
    config.addinivalue_line(
        "markers", "no_fail_on_log_exception: mark test to not fail on logged exception"
    )
    if config.getoption("verbose") > 0:
        logging.getLogger().setLevel(logging.DEBUG)


def pytest_runtest_setup() -> None:
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

    freezegun.api.datetime_to_fakedatetime = ha_datetime_to_fakedatetime  # type: ignore[attr-defined]
    freezegun.api.FakeDatetime = HAFakeDatetime  # type: ignore[attr-defined]

    def adapt_datetime(val):
        return val.isoformat(" ")

    # Setup HAFakeDatetime converter for sqlite3
    sqlite3.register_adapter(HAFakeDatetime, adapt_datetime)

    # Setup HAFakeDatetime converter for pymysql
    try:
        # pylint: disable-next=import-outside-toplevel
        import MySQLdb.converters as MySQLdb_converters
    except ImportError:
        pass
    else:
        MySQLdb_converters.conversions[HAFakeDatetime] = (
            MySQLdb_converters.DateTime2literal
        )


def ha_datetime_to_fakedatetime(datetime) -> freezegun.api.FakeDatetime:  # type: ignore[name-defined]
    """Convert datetime to FakeDatetime.

    Modified to include https://github.com/spulec/freezegun/pull/424.
    """
    return freezegun.api.FakeDatetime(  # type: ignore[attr-defined]
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


class HAFakeDatetime(freezegun.api.FakeDatetime):  # type: ignore[name-defined]
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


def check_real[**_P, _R](func: Callable[_P, Coroutine[Any, Any, _R]]):
    """Force a function to require a keyword _test_real to be passed in."""

    @functools.wraps(func)
    async def guard_func(*args: _P.args, **kwargs: _P.kwargs) -> _R:
        real = kwargs.pop("_test_real", None)

        if not real:
            raise RuntimeError(
                f'Forgot to mock or pass "_test_real=True" to {func.__name__}'
            )

        return await func(*args, **kwargs)

    return guard_func


# Guard a few functions that would make network connections
location.async_detect_location_info = check_real(location.async_detect_location_info)


@pytest.fixture(name="caplog")
def caplog_fixture(caplog: pytest.LogCaptureFixture) -> pytest.LogCaptureFixture:
    """Set log level to debug for tests using the caplog fixture."""
    caplog.set_level(logging.DEBUG)
    return caplog


@pytest.fixture(autouse=True, scope="module")
def garbage_collection() -> None:
    """Run garbage collection at known locations.

    This is to mimic the behavior of pytest-aiohttp, and is
    required to avoid warnings during garbage collection from
    spilling over into next test case. We run it per module which
    handles the most common cases and let each module override
    to run per test case if needed.
    """
    gc.collect()


@pytest.fixture(autouse=True)
def expected_lingering_tasks() -> bool:
    """Temporary ability to bypass test failures.

    Parametrize to True to bypass the pytest failure.
    @pytest.mark.parametrize("expected_lingering_tasks", [True])

    This should be removed when all lingering tasks have been cleaned up.
    """
    return False


@pytest.fixture(autouse=True)
def expected_lingering_timers() -> bool:
    """Temporary ability to bypass test failures.

    Parametrize to True to bypass the pytest failure.
    @pytest.mark.parametrize("expected_lingering_timers", [True])

    This should be removed when all lingering timers have been cleaned up.
    """
    current_test = os.getenv("PYTEST_CURRENT_TEST")
    if (
        current_test
        and current_test.startswith("tests/components/")
        and current_test.split("/")[2] not in BASE_PLATFORMS
    ):
        # As a starting point, we ignore non-platform components
        return True
    return False


@pytest.fixture
def wait_for_stop_scripts_after_shutdown() -> bool:
    """Add ability to bypass _schedule_stop_scripts_after_shutdown.

    _schedule_stop_scripts_after_shutdown leaves a lingering timer.

    Parametrize to True to bypass the pytest failure.
    @pytest.mark.parametrize("wait_for_stop_scripts_at_shutdown", [True])
    """
    return False


@pytest.fixture(autouse=True)
def skip_stop_scripts(
    wait_for_stop_scripts_after_shutdown: bool,
) -> Generator[None]:
    """Add ability to bypass _schedule_stop_scripts_after_shutdown."""
    if wait_for_stop_scripts_after_shutdown:
        yield
        return
    with patch(
        "homeassistant.helpers.script._schedule_stop_scripts_after_shutdown",
        Mock(),
    ):
        yield


@contextmanager
def long_repr_strings() -> Generator[None]:
    """Increase reprlib maxstring and maxother to 300."""
    arepr = reprlib.aRepr
    original_maxstring = arepr.maxstring
    original_maxother = arepr.maxother
    arepr.maxstring = 300
    arepr.maxother = 300
    try:
        yield
    finally:
        arepr.maxstring = original_maxstring
        arepr.maxother = original_maxother


@pytest.fixture(autouse=True)
def enable_event_loop_debug(event_loop: asyncio.AbstractEventLoop) -> None:
    """Enable event loop debug mode."""
    event_loop.set_debug(True)


@pytest.fixture(autouse=True)
def verify_cleanup(
    event_loop: asyncio.AbstractEventLoop,
    expected_lingering_tasks: bool,
    expected_lingering_timers: bool,
) -> Generator[None]:
    """Verify that the test has cleaned up resources correctly."""
    threads_before = frozenset(threading.enumerate())
    tasks_before = asyncio.all_tasks(event_loop)
    yield

    event_loop.run_until_complete(event_loop.shutdown_default_executor())

    if len(INSTANCES) >= 2:
        count = len(INSTANCES)
        for inst in INSTANCES:
            inst.stop()
        pytest.exit(f"Detected non stopped instances ({count}), aborting test run")

    # Warn and clean-up lingering tasks and timers
    # before moving on to the next test.
    tasks = asyncio.all_tasks(event_loop) - tasks_before
    for task in tasks:
        if expected_lingering_tasks:
            _LOGGER.warning("Lingering task after test %r", task)
        else:
            pytest.fail(f"Lingering task after test {task!r}")
        task.cancel()
    if tasks:
        event_loop.run_until_complete(asyncio.wait(tasks))

    for handle in get_scheduled_timer_handles(event_loop):
        if not handle.cancelled():
            with long_repr_strings():
                if expected_lingering_timers:
                    _LOGGER.warning("Lingering timer after test %r", handle)
                elif handle._args and isinstance(job := handle._args[-1], HassJob):
                    if job.cancel_on_shutdown:
                        continue
                    pytest.fail(f"Lingering timer after job {job!r}")
                else:
                    pytest.fail(f"Lingering timer after test {handle!r}")
                handle.cancel()

    # Verify no threads where left behind.
    threads = frozenset(threading.enumerate()) - threads_before
    for thread in threads:
        assert isinstance(thread, threading._DummyThread) or thread.name.startswith(
            "waitpid-"
        )

    try:
        # Verify the default time zone has been restored
        assert dt_util.DEFAULT_TIME_ZONE is datetime.UTC
    finally:
        # Restore the default time zone to not break subsequent tests
        dt_util.DEFAULT_TIME_ZONE = datetime.UTC

    try:
        # Verify respx.mock has been cleaned up
        assert not respx.mock.routes, "respx.mock routes not cleaned up, maybe the test needs to be decorated with @respx.mock"
    finally:
        # Clear mock routes not break subsequent tests
        respx.mock.clear()


@pytest.fixture(autouse=True)
def reset_hass_threading_local_object() -> Generator[None]:
    """Reset the _Hass threading.local object for every test case."""
    yield
    ha._hass.__dict__.clear()


@pytest.fixture(scope="session", autouse=True)
def bcrypt_cost() -> Generator[None]:
    """Run with reduced rounds during tests, to speed up uses."""
    gensalt_orig = bcrypt.gensalt

    def gensalt_mock(rounds=12, prefix=b"2b"):
        return gensalt_orig(4, prefix)

    bcrypt.gensalt = gensalt_mock
    yield
    bcrypt.gensalt = gensalt_orig


@pytest.fixture
def hass_storage() -> Generator[dict[str, Any]]:
    """Fixture to mock storage."""
    with mock_storage() as stored_data:
        yield stored_data


@pytest.fixture
def load_registries() -> bool:
    """Fixture to control the loading of registries when setting up the hass fixture.

    To avoid loading the registries, tests can be marked with:
    @pytest.mark.parametrize("load_registries", [False])
    """
    return True


class CoalescingResponse(client.ClientWebSocketResponse):
    """ClientWebSocketResponse client that mimics the websocket js code."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Init the ClientWebSocketResponse."""
        super().__init__(*args, **kwargs)
        self._recv_buffer: list[Any] = []

    async def receive_json(
        self,
        *,
        loads: JSONDecoder = json_loads,
        timeout: float | None = None,
    ) -> Any:
        """receive_json or from buffer."""
        if self._recv_buffer:
            return self._recv_buffer.pop(0)
        data = await self.receive_str(timeout=timeout)
        decoded = loads(data)
        if isinstance(decoded, list):
            self._recv_buffer = decoded
            return self._recv_buffer.pop(0)
        return decoded


class CoalescingClient(TestClient):
    """Client that mimics the websocket js code."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Init TestClient."""
        super().__init__(*args, ws_response_class=CoalescingResponse, **kwargs)


@pytest.fixture
def aiohttp_client_cls() -> type[CoalescingClient]:
    """Override the test class for aiohttp."""
    return CoalescingClient


@pytest.fixture
def aiohttp_client(
    event_loop: asyncio.AbstractEventLoop,
) -> Generator[ClientSessionGenerator]:
    """Override the default aiohttp_client since 3.x does not support aiohttp_client_cls.

    Remove this when upgrading to 4.x as aiohttp_client_cls
    will do the same thing

    aiohttp_client(app, **kwargs)
    aiohttp_client(server, **kwargs)
    aiohttp_client(raw_server, **kwargs)
    """
    loop = event_loop
    clients = []

    async def go(
        __param: Application | BaseTestServer,
        *args: Any,
        server_kwargs: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> TestClient:
        if isinstance(__param, Callable) and not isinstance(  # type: ignore[arg-type]
            __param, (Application, BaseTestServer)
        ):
            __param = __param(loop, *args, **kwargs)
            kwargs = {}
        else:
            assert not args, "args should be empty"

        client: TestClient
        if isinstance(__param, Application):
            server_kwargs = server_kwargs or {}
            server = TestServer(__param, loop=loop, **server_kwargs)
            # Registering a view after starting the server should still work.
            server.app._router.freeze = lambda: None
            client = CoalescingClient(server, loop=loop, **kwargs)
        elif isinstance(__param, BaseTestServer):
            client = TestClient(__param, loop=loop, **kwargs)
        else:
            raise TypeError(f"Unknown argument type: {type(__param)!r}")

        await client.start_server()
        clients.append(client)
        return client

    yield go

    async def finalize() -> None:
        while clients:
            await clients.pop().close()

    loop.run_until_complete(finalize())


@pytest.fixture
def hass_fixture_setup() -> list[bool]:
    """Fixture which is truthy if the hass fixture has been setup."""
    return []


@pytest.fixture
async def hass(
    hass_fixture_setup: list[bool],
    load_registries: bool,
    hass_storage: dict[str, Any],
    request: pytest.FixtureRequest,
    mock_recorder_before_hass: None,
) -> AsyncGenerator[HomeAssistant]:
    """Create a test instance of Home Assistant."""

    loop = asyncio.get_running_loop()
    hass_fixture_setup.append(True)

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
                    "Received exception handler without exception, "
                    f"but with message: {context["message"]}"
                )
            )
        orig_exception_handler(loop, context)

    exceptions: list[Exception] = []
    async with async_test_home_assistant(loop, load_registries) as hass:
        orig_exception_handler = loop.get_exception_handler()
        loop.set_exception_handler(exc_handle)

        yield hass

        # Config entries are not normally unloaded on HA shutdown. They are unloaded here
        # to ensure that they could, and to help track lingering tasks and timers.
        loaded_entries = [
            entry
            for entry in hass.config_entries.async_entries()
            if entry.state is ConfigEntryState.LOADED
        ]
        if loaded_entries:
            await asyncio.gather(
                *(
                    create_eager_task(
                        hass.config_entries.async_unload(config_entry.entry_id),
                        loop=hass.loop,
                    )
                    for config_entry in loaded_entries
                )
            )

        await hass.async_stop(force=True)

    for ex in exceptions:
        if (
            request.module.__name__,
            request.function.__name__,
        ) in IGNORE_UNCAUGHT_EXCEPTIONS:
            continue
        raise ex


@pytest.fixture
async def stop_hass() -> AsyncGenerator[None]:
    """Make sure all hass are stopped."""
    orig_hass = ha.HomeAssistant

    event_loop = asyncio.get_running_loop()
    created = []

    def mock_hass(*args):
        hass_inst = orig_hass(*args)
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
            await event_loop.shutdown_default_executor()


@pytest.fixture(name="requests_mock")
def requests_mock_fixture() -> Generator[requests_mock.Mocker]:
    """Fixture to provide a requests mocker."""
    with requests_mock.mock() as m:
        yield m


@pytest.fixture
def aioclient_mock() -> Generator[AiohttpClientMocker]:
    """Fixture to mock aioclient calls."""
    with mock_aiohttp_client() as mock_session:
        yield mock_session


@pytest.fixture
def mock_device_tracker_conf() -> Generator[list[Device]]:
    """Prevent device tracker from reading/writing data."""
    devices: list[Device] = []

    async def mock_update_config(path: str, dev_id: str, entity: Device) -> None:
        devices.append(entity)

    with (
        patch(
            (
                "homeassistant.components.device_tracker.legacy"
                ".DeviceTracker.async_update_config"
            ),
            side_effect=mock_update_config,
        ),
        patch(
            "homeassistant.components.device_tracker.legacy.async_load_config",
            side_effect=lambda *args: devices,
        ),
    ):
        yield devices


@pytest.fixture
async def hass_admin_credential(
    hass: HomeAssistant, local_auth: homeassistant.HassAuthProvider
) -> Credentials:
    """Provide credentials for admin user."""
    return Credentials(
        id="mock-credential-id",
        auth_provider_type="homeassistant",
        auth_provider_id=None,
        data={"username": "admin"},
        is_new=False,
    )


@pytest.fixture
async def hass_access_token(
    hass: HomeAssistant, hass_admin_user: MockUser, hass_admin_credential: Credentials
) -> str:
    """Return an access token to access Home Assistant."""
    await hass.auth.async_link_user(hass_admin_user, hass_admin_credential)

    refresh_token = await hass.auth.async_create_refresh_token(
        hass_admin_user, CLIENT_ID, credential=hass_admin_credential
    )
    return hass.auth.async_create_access_token(refresh_token)


@pytest.fixture
def hass_owner_user(
    hass: HomeAssistant, local_auth: homeassistant.HassAuthProvider
) -> MockUser:
    """Return a Home Assistant admin user."""
    return MockUser(is_owner=True).add_to_hass(hass)


@pytest.fixture
async def hass_admin_user(
    hass: HomeAssistant, local_auth: homeassistant.HassAuthProvider
) -> MockUser:
    """Return a Home Assistant admin user."""
    admin_group = await hass.auth.async_get_group(GROUP_ID_ADMIN)
    return MockUser(groups=[admin_group]).add_to_hass(hass)


@pytest.fixture
async def hass_read_only_user(
    hass: HomeAssistant, local_auth: homeassistant.HassAuthProvider
) -> MockUser:
    """Return a Home Assistant read only user."""
    read_only_group = await hass.auth.async_get_group(GROUP_ID_READ_ONLY)
    return MockUser(groups=[read_only_group]).add_to_hass(hass)


@pytest.fixture
async def hass_read_only_access_token(
    hass: HomeAssistant,
    hass_read_only_user: MockUser,
    local_auth: homeassistant.HassAuthProvider,
) -> str:
    """Return a Home Assistant read only user."""
    credential = Credentials(
        id="mock-readonly-credential-id",
        auth_provider_type="homeassistant",
        auth_provider_id=None,
        data={"username": "readonly"},
        is_new=False,
    )
    hass_read_only_user.credentials.append(credential)

    refresh_token = await hass.auth.async_create_refresh_token(
        hass_read_only_user, CLIENT_ID, credential=credential
    )
    return hass.auth.async_create_access_token(refresh_token)


@pytest.fixture
async def hass_supervisor_user(
    hass: HomeAssistant, local_auth: homeassistant.HassAuthProvider
) -> MockUser:
    """Return the Home Assistant Supervisor user."""
    admin_group = await hass.auth.async_get_group(GROUP_ID_ADMIN)
    return MockUser(
        name=HASSIO_USER_NAME, groups=[admin_group], system_generated=True
    ).add_to_hass(hass)


@pytest.fixture
async def hass_supervisor_access_token(
    hass: HomeAssistant,
    hass_supervisor_user: MockUser,
    local_auth: homeassistant.HassAuthProvider,
) -> str:
    """Return a Home Assistant Supervisor access token."""
    refresh_token = await hass.auth.async_create_refresh_token(hass_supervisor_user)
    return hass.auth.async_create_access_token(refresh_token)


@pytest.fixture
async def local_auth(hass: HomeAssistant) -> homeassistant.HassAuthProvider:
    """Load local auth provider."""
    prv = homeassistant.HassAuthProvider(
        hass, hass.auth._store, {"type": "homeassistant"}
    )
    await prv.async_initialize()
    hass.auth._providers[(prv.type, prv.id)] = prv
    return prv


@pytest.fixture
def hass_client(
    hass: HomeAssistant,
    aiohttp_client: ClientSessionGenerator,
    hass_access_token: str,
    socket_enabled: None,
) -> ClientSessionGenerator:
    """Return an authenticated HTTP client."""

    async def auth_client(access_token: str | None = hass_access_token) -> TestClient:
        """Return an authenticated client."""
        return await aiohttp_client(
            hass.http.app, headers={"Authorization": f"Bearer {access_token}"}
        )

    return auth_client


@pytest.fixture
def hass_client_no_auth(
    hass: HomeAssistant,
    aiohttp_client: ClientSessionGenerator,
    socket_enabled: None,
) -> ClientSessionGenerator:
    """Return an unauthenticated HTTP client."""

    async def client() -> TestClient:
        """Return an authenticated client."""
        return await aiohttp_client(hass.http.app)

    return client


@pytest.fixture
def current_request() -> Generator[MagicMock]:
    """Mock current request."""
    with patch("homeassistant.components.http.current_request") as mock_request_context:
        mocked_request = make_mocked_request(
            "GET",
            "/some/request",
            headers={"Host": "example.com"},
            sslcontext=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT),
        )
        mock_request_context.get.return_value = mocked_request
        yield mock_request_context


@pytest.fixture
def current_request_with_host(current_request: MagicMock) -> None:
    """Mock current request with a host header."""
    new_headers = multidict.CIMultiDict(current_request.get.return_value.headers)
    new_headers[config_entry_oauth2_flow.HEADER_FRONTEND_BASE] = "https://example.com"
    current_request.get.return_value = current_request.get.return_value.clone(
        headers=new_headers
    )


@pytest.fixture
def hass_ws_client(
    aiohttp_client: ClientSessionGenerator,
    hass_access_token: str,
    hass: HomeAssistant,
    socket_enabled: None,
) -> WebSocketGenerator:
    """Websocket client fixture connected to websocket server."""

    async def create_client(
        hass: HomeAssistant = hass, access_token: str | None = hass_access_token
    ) -> MockHAClientWebSocket:
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

        def _get_next_id() -> Generator[int]:
            i = 0
            while True:
                yield (i := i + 1)

        id_generator = _get_next_id()

        def _send_json_auto_id(data: dict[str, Any]) -> Coroutine[Any, Any, None]:
            data["id"] = next(id_generator)
            return websocket.send_json(data)

        async def _remove_device(device_id: str, config_entry_id: str) -> Any:
            await _send_json_auto_id(
                {
                    "type": "config/device_registry/remove_config_entry",
                    "config_entry_id": config_entry_id,
                    "device_id": device_id,
                }
            )
            return await websocket.receive_json()

        # wrap in client
        wrapped_websocket = cast(MockHAClientWebSocket, websocket)
        wrapped_websocket.client = client
        wrapped_websocket.send_json_auto_id = _send_json_auto_id
        wrapped_websocket.remove_device = _remove_device
        return wrapped_websocket

    return create_client


@pytest.fixture(autouse=True)
def fail_on_log_exception(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fixture to fail if a callback wrapped by catch_log_exception or coroutine wrapped by async_create_catching_coro throws."""
    if "no_fail_on_log_exception" in request.keywords:
        return

    def log_exception(format_err, *args):
        raise  # noqa: PLE0704

    monkeypatch.setattr("homeassistant.util.logging.log_exception", log_exception)


@pytest.fixture
def mqtt_config_entry_data() -> dict[str, Any] | None:
    """Fixture to allow overriding MQTT config."""
    return None


@pytest.fixture
def mqtt_client_mock(hass: HomeAssistant) -> Generator[MqttMockPahoClient]:
    """Fixture to mock MQTT client."""

    mid: int = 0

    def get_mid() -> int:
        nonlocal mid
        mid += 1
        return mid

    class FakeInfo:
        """Class to fake MQTT info."""

        def __init__(self, mid: int) -> None:
            self.mid = mid
            self.rc = 0

    with patch(
        "homeassistant.components.mqtt.async_client.AsyncMQTTClient"
    ) as mock_client:
        # The below use a call_soon for the on_publish/on_subscribe/on_unsubscribe
        # callbacks to simulate the behavior of the real MQTT client which will
        # not be synchronous.

        @ha.callback
        def _async_fire_mqtt_message(topic, payload, qos, retain):
            async_fire_mqtt_message(hass, topic, payload or b"", qos, retain)
            mid = get_mid()
            hass.loop.call_soon(mock_client.on_publish, 0, 0, mid)
            return FakeInfo(mid)

        def _subscribe(topic, qos=0):
            mid = get_mid()
            hass.loop.call_soon(mock_client.on_subscribe, 0, 0, mid)
            return (0, mid)

        def _unsubscribe(topic):
            mid = get_mid()
            hass.loop.call_soon(mock_client.on_unsubscribe, 0, 0, mid)
            return (0, mid)

        def _connect(*args, **kwargs):
            # Connect always calls reconnect once, but we
            # mock it out so we call reconnect to simulate
            # the behavior.
            mock_client.reconnect()
            hass.loop.call_soon_threadsafe(
                mock_client.on_connect, mock_client, None, 0, 0, 0
            )
            mock_client.on_socket_open(
                mock_client, None, Mock(fileno=Mock(return_value=-1))
            )
            mock_client.on_socket_register_write(
                mock_client, None, Mock(fileno=Mock(return_value=-1))
            )
            return 0

        mock_client = mock_client.return_value
        mock_client.connect.side_effect = _connect
        mock_client.subscribe.side_effect = _subscribe
        mock_client.unsubscribe.side_effect = _unsubscribe
        mock_client.publish.side_effect = _async_fire_mqtt_message
        mock_client.loop_read.return_value = 0
        yield mock_client


@pytest.fixture
async def mqtt_mock(
    hass: HomeAssistant,
    mock_hass_config: None,
    mqtt_client_mock: MqttMockPahoClient,
    mqtt_config_entry_data: dict[str, Any] | None,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> AsyncGenerator[MqttMockHAClient]:
    """Fixture to mock MQTT component."""
    return await mqtt_mock_entry()


@asynccontextmanager
async def _mqtt_mock_entry(
    hass: HomeAssistant,
    mqtt_client_mock: MqttMockPahoClient,
    mqtt_config_entry_data: dict[str, Any] | None,
) -> AsyncGenerator[MqttMockHAClientGenerator]:
    """Fixture to mock a delayed setup of the MQTT config entry."""
    # Local import to avoid processing MQTT modules when running a testcase
    # which does not use MQTT.
    from homeassistant.components import mqtt  # pylint: disable=import-outside-toplevel

    if mqtt_config_entry_data is None:
        mqtt_config_entry_data = {
            mqtt.CONF_BROKER: "mock-broker",
            mqtt.CONF_BIRTH_MESSAGE: {},
        }

    await hass.async_block_till_done()

    entry = MockConfigEntry(
        data=mqtt_config_entry_data,
        domain=mqtt.DOMAIN,
        title="MQTT",
    )
    entry.add_to_hass(hass)

    real_mqtt = mqtt.MQTT
    real_mqtt_instance = None
    mock_mqtt_instance = None

    async def _setup_mqtt_entry(
        setup_entry: Callable[[HomeAssistant, ConfigEntry], Coroutine[Any, Any, bool]],
    ) -> MagicMock:
        """Set up the MQTT config entry."""
        assert await setup_entry(hass, entry)

        # Assert that MQTT is setup
        assert real_mqtt_instance is not None, "MQTT was not setup correctly"
        mock_mqtt_instance.conf = real_mqtt_instance.conf  # For diagnostics
        mock_mqtt_instance._mqttc = mqtt_client_mock

        # connected set to True to get a more realistic behavior when subscribing
        mock_mqtt_instance.connected = True
        mqtt_client_mock.on_connect(mqtt_client_mock, None, 0, 0, 0)

        async_dispatcher_send(hass, mqtt.MQTT_CONNECTION_STATE, True)
        await hass.async_block_till_done()

        return mock_mqtt_instance

    def create_mock_mqtt(*args, **kwargs) -> MqttMockHAClient:
        """Create a mock based on mqtt.MQTT."""
        nonlocal mock_mqtt_instance
        nonlocal real_mqtt_instance
        real_mqtt_instance = real_mqtt(*args, **kwargs)
        spec = [*dir(real_mqtt_instance), "_mqttc"]
        mock_mqtt_instance = MagicMock(
            return_value=real_mqtt_instance,
            spec_set=spec,
            wraps=real_mqtt_instance,
        )
        return mock_mqtt_instance

    with patch("homeassistant.components.mqtt.MQTT", side_effect=create_mock_mqtt):
        yield _setup_mqtt_entry


@pytest.fixture
def hass_config() -> ConfigType:
    """Fixture to parametrize the content of main configuration using mock_hass_config.

    To set a configuration, tests can be marked with:
    @pytest.mark.parametrize("hass_config", [{integration: {...}}])
    Add the `mock_hass_config: None` fixture to the test.
    """
    return {}


@pytest.fixture
def mock_hass_config(hass: HomeAssistant, hass_config: ConfigType) -> Generator[None]:
    """Fixture to mock the content of main configuration.

    Patches homeassistant.config.load_yaml_config_file and hass.config_entries
    with `hass_config` as parameterized.
    """
    if hass_config:
        hass.config_entries = ConfigEntries(hass, hass_config)
    with patch("homeassistant.config.load_yaml_config_file", return_value=hass_config):
        yield


@pytest.fixture
def hass_config_yaml() -> str:
    """Fixture to parametrize the content of configuration.yaml file.

    To set yaml content, tests can be marked with:
    @pytest.mark.parametrize("hass_config_yaml", ["..."])
    Add the `mock_hass_config_yaml: None` fixture to the test.
    """
    return ""


@pytest.fixture
def hass_config_yaml_files(hass_config_yaml: str) -> dict[str, str]:
    """Fixture to parametrize multiple yaml configuration files.

    To set the YAML files to patch, tests can be marked with:
    @pytest.mark.parametrize(
        "hass_config_yaml_files", [{"configuration.yaml": "..."}]
    )
    Add the `mock_hass_config_yaml: None` fixture to the test.
    """
    return {YAML_CONFIG_FILE: hass_config_yaml}


@pytest.fixture
def mock_hass_config_yaml(
    hass: HomeAssistant, hass_config_yaml_files: dict[str, str]
) -> Generator[None]:
    """Fixture to mock the content of the yaml configuration files.

    Patches yaml configuration files using the `hass_config_yaml`
    and `hass_config_yaml_files` fixtures.
    """
    with patch_yaml_files(hass_config_yaml_files):
        yield


@pytest.fixture
async def mqtt_mock_entry(
    hass: HomeAssistant,
    mqtt_client_mock: MqttMockPahoClient,
    mqtt_config_entry_data: dict[str, Any] | None,
) -> AsyncGenerator[MqttMockHAClientGenerator]:
    """Set up an MQTT config entry."""

    async def _async_setup_config_entry(
        hass: HomeAssistant, entry: ConfigEntry
    ) -> bool:
        """Help set up the config entry."""
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        return True

    async def _setup_mqtt_entry() -> MqttMockHAClient:
        """Set up the MQTT config entry."""
        return await mqtt_mock_entry(_async_setup_config_entry)

    async with _mqtt_mock_entry(
        hass, mqtt_client_mock, mqtt_config_entry_data
    ) as mqtt_mock_entry:
        yield _setup_mqtt_entry


@pytest.fixture(autouse=True, scope="session")
def mock_network() -> Generator[None]:
    """Mock network."""
    with patch(
        "homeassistant.components.network.util.ifaddr.get_adapters",
        return_value=[
            Mock(
                nice_name="eth0",
                ips=[Mock(is_IPv6=False, ip="10.10.10.10", network_prefix=24)],
                index=0,
            )
        ],
    ):
        yield


@pytest.fixture(autouse=True, scope="session")
def mock_get_source_ip() -> Generator[_patch]:
    """Mock network util's async_get_source_ip."""
    patcher = patch(
        "homeassistant.components.network.util.async_get_source_ip",
        return_value="10.10.10.10",
    )
    patcher.start()
    try:
        yield patcher
    finally:
        patcher.stop()


@pytest.fixture(autouse=True, scope="session")
def translations_once() -> Generator[_patch]:
    """Only load translations once per session."""
    cache = _TranslationsCacheData({}, {})
    patcher = patch(
        "homeassistant.helpers.translation._TranslationsCacheData",
        return_value=cache,
    )
    patcher.start()
    try:
        yield patcher
    finally:
        patcher.stop()


@pytest.fixture
def disable_translations_once(
    translations_once: _patch,
) -> Generator[None]:
    """Override loading translations once."""
    translations_once.stop()
    yield
    translations_once.start()


@pytest.fixture
def mock_zeroconf() -> Generator[MagicMock]:
    """Mock zeroconf."""
    from zeroconf import DNSCache  # pylint: disable=import-outside-toplevel

    with (
        patch("homeassistant.components.zeroconf.HaZeroconf", autospec=True) as mock_zc,
        patch("homeassistant.components.zeroconf.AsyncServiceBrowser", autospec=True),
    ):
        zc = mock_zc.return_value
        # DNSCache has strong Cython type checks, and MagicMock does not work
        # so we must mock the class directly
        zc.cache = DNSCache()
        yield mock_zc


@pytest.fixture
def mock_async_zeroconf(mock_zeroconf: MagicMock) -> Generator[MagicMock]:
    """Mock AsyncZeroconf."""
    from zeroconf import DNSCache, Zeroconf  # pylint: disable=import-outside-toplevel
    from zeroconf.asyncio import (  # pylint: disable=import-outside-toplevel
        AsyncZeroconf,
    )

    with patch(
        "homeassistant.components.zeroconf.HaAsyncZeroconf", spec=AsyncZeroconf
    ) as mock_aiozc:
        zc = mock_aiozc.return_value
        zc.async_unregister_service = AsyncMock()
        zc.async_register_service = AsyncMock()
        zc.async_update_service = AsyncMock()
        zc.zeroconf = Mock(spec=Zeroconf)
        zc.zeroconf.async_wait_for_start = AsyncMock()
        # DNSCache has strong Cython type checks, and MagicMock does not work
        # so we must mock the class directly
        zc.zeroconf.cache = DNSCache()
        zc.zeroconf.done = False
        zc.async_close = AsyncMock()
        zc.ha_async_close = AsyncMock()
        yield zc


@pytest.fixture
def enable_custom_integrations(hass: HomeAssistant) -> None:
    """Enable custom integrations defined in the test dir."""
    hass.data.pop(loader.DATA_CUSTOM_COMPONENTS)


@pytest.fixture
def enable_statistics() -> bool:
    """Fixture to control enabling of recorder's statistics compilation.

    To enable statistics, tests can be marked with:
    @pytest.mark.parametrize("enable_statistics", [True])
    """
    return False


@pytest.fixture
def enable_missing_statistics() -> bool:
    """Fixture to control enabling of recorder's statistics compilation.

    To enable statistics, tests can be marked with:
    @pytest.mark.parametrize("enable_missing_statistics", [True])
    """
    return False


@pytest.fixture
def enable_schema_validation() -> bool:
    """Fixture to control enabling of recorder's statistics table validation.

    To enable statistics table validation, tests can be marked with:
    @pytest.mark.parametrize("enable_schema_validation", [True])
    """
    return False


@pytest.fixture
def enable_nightly_purge() -> bool:
    """Fixture to control enabling of recorder's nightly purge job.

    To enable nightly purging, tests can be marked with:
    @pytest.mark.parametrize("enable_nightly_purge", [True])
    """
    return False


@pytest.fixture
def enable_migrate_event_context_ids() -> bool:
    """Fixture to control enabling of recorder's context id migration.

    To enable context id migration, tests can be marked with:
    @pytest.mark.parametrize("enable_migrate_event_context_ids", [True])
    """
    return False


@pytest.fixture
def enable_migrate_state_context_ids() -> bool:
    """Fixture to control enabling of recorder's context id migration.

    To enable context id migration, tests can be marked with:
    @pytest.mark.parametrize("enable_migrate_state_context_ids", [True])
    """
    return False


@pytest.fixture
def enable_migrate_event_type_ids() -> bool:
    """Fixture to control enabling of recorder's event type id migration.

    To enable context id migration, tests can be marked with:
    @pytest.mark.parametrize("enable_migrate_event_type_ids", [True])
    """
    return False


@pytest.fixture
def enable_migrate_entity_ids() -> bool:
    """Fixture to control enabling of recorder's entity_id migration.

    To enable context id migration, tests can be marked with:
    @pytest.mark.parametrize("enable_migrate_entity_ids", [True])
    """
    return False


@pytest.fixture
def enable_migrate_event_ids() -> bool:
    """Fixture to control enabling of recorder's event id migration.

    To enable context id migration, tests can be marked with:
    @pytest.mark.parametrize("enable_migrate_event_ids", [True])
    """
    return False


@pytest.fixture
def recorder_config() -> dict[str, Any] | None:
    """Fixture to override recorder config.

    To override the config, tests can be marked with:
    @pytest.mark.parametrize("recorder_config", [{...}])
    """
    return None


@pytest.fixture
def persistent_database() -> bool:
    """Fixture to control if database should persist when recorder is shut down in test.

    When using sqlite, this uses on disk database instead of in memory database.
    This does nothing when using mysql or postgresql.

    Note that the database is always destroyed in between tests.

    To use a persistent database, tests can be marked with:
    @pytest.mark.parametrize("persistent_database", [True])
    """
    return False


@pytest.fixture
def recorder_db_url(
    pytestconfig: pytest.Config,
    hass_fixture_setup: list[bool],
    persistent_database: str,
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[str]:
    """Prepare a default database for tests and return a connection URL."""
    assert not hass_fixture_setup

    db_url = cast(str, pytestconfig.getoption("dburl"))
    if db_url == "sqlite://" and persistent_database:
        tmp_path = tmp_path_factory.mktemp("recorder")
        db_url = "sqlite:///" + str(tmp_path / "pytest.db")
    elif db_url.startswith("mysql://"):
        # pylint: disable-next=import-outside-toplevel
        import sqlalchemy_utils

        charset = "utf8mb4' COLLATE = 'utf8mb4_unicode_ci"
        assert not sqlalchemy_utils.database_exists(db_url)
        sqlalchemy_utils.create_database(db_url, encoding=charset)
    elif db_url.startswith("postgresql://"):
        # pylint: disable-next=import-outside-toplevel
        import sqlalchemy_utils

        assert not sqlalchemy_utils.database_exists(db_url)
        sqlalchemy_utils.create_database(db_url, encoding="utf8")
    yield db_url
    if db_url == "sqlite://" and persistent_database:
        rmtree(tmp_path, ignore_errors=True)
    elif db_url.startswith("mysql://"):
        # pylint: disable-next=import-outside-toplevel
        import sqlalchemy as sa

        made_url = sa.make_url(db_url)
        db = made_url.database
        engine = sa.create_engine(db_url)
        # Check for any open connections to the database before dropping it
        # to ensure that InnoDB does not deadlock.
        with engine.begin() as connection:
            query = sa.text(
                "select id FROM information_schema.processlist WHERE db=:db and id != CONNECTION_ID()"
            )
            rows = connection.execute(query, parameters={"db": db}).fetchall()
            if rows:
                raise RuntimeError(
                    f"Unable to drop database {db} because it is in use by {rows}"
                )
        engine.dispose()
        sqlalchemy_utils.drop_database(db_url)
    elif db_url.startswith("postgresql://"):
        sqlalchemy_utils.drop_database(db_url)


async def _async_init_recorder_component(
    hass: HomeAssistant,
    add_config: dict[str, Any] | None = None,
    db_url: str | None = None,
    *,
    expected_setup_result: bool,
    wait_setup: bool,
) -> None:
    """Initialize the recorder asynchronously."""
    # pylint: disable-next=import-outside-toplevel
    from homeassistant.components import recorder

    config = dict(add_config) if add_config else {}
    if recorder.CONF_DB_URL not in config:
        config[recorder.CONF_DB_URL] = db_url
        if recorder.CONF_COMMIT_INTERVAL not in config:
            config[recorder.CONF_COMMIT_INTERVAL] = 0

    with patch("homeassistant.components.recorder.ALLOW_IN_MEMORY_DB", True):
        if recorder.DOMAIN not in hass.data:
            recorder_helper.async_initialize_recorder(hass)
        setup_task = asyncio.ensure_future(
            async_setup_component(hass, recorder.DOMAIN, {recorder.DOMAIN: config})
        )
        if wait_setup:
            # Wait for recorder integration to setup
            setup_result = await setup_task
            assert setup_result == expected_setup_result
            assert (recorder.DOMAIN in hass.config.components) == expected_setup_result
        else:
            # Wait for recorder to connect to the database
            await recorder_helper.async_wait_recorder(hass)
    _LOGGER.info(
        "Test recorder successfully started, database location: %s",
        config[recorder.CONF_DB_URL],
    )


class ThreadSession(threading.local):
    """Keep track of session per thread."""

    has_session = False


thread_session = ThreadSession()


@pytest.fixture
async def async_test_recorder(
    recorder_db_url: str,
    enable_nightly_purge: bool,
    enable_statistics: bool,
    enable_missing_statistics: bool,
    enable_schema_validation: bool,
    enable_migrate_event_context_ids: bool,
    enable_migrate_state_context_ids: bool,
    enable_migrate_event_type_ids: bool,
    enable_migrate_entity_ids: bool,
    enable_migrate_event_ids: bool,
) -> AsyncGenerator[RecorderInstanceGenerator]:
    """Yield context manager to setup recorder instance."""
    # pylint: disable-next=import-outside-toplevel
    from homeassistant.components import recorder

    # pylint: disable-next=import-outside-toplevel
    from homeassistant.components.recorder import migration

    # pylint: disable-next=import-outside-toplevel
    from .components.recorder.common import async_recorder_block_till_done

    # pylint: disable-next=import-outside-toplevel
    from .patch_recorder import real_session_scope

    if TYPE_CHECKING:
        # pylint: disable-next=import-outside-toplevel
        from sqlalchemy.orm.session import Session

    @contextmanager
    def debug_session_scope(
        *,
        hass: HomeAssistant | None = None,
        session: Session | None = None,
        exception_filter: Callable[[Exception], bool] | None = None,
        read_only: bool = False,
    ) -> Generator[Session]:
        """Wrap session_scope to bark if we create nested sessions."""
        if thread_session.has_session:
            raise RuntimeError(
                f"Thread '{threading.current_thread().name}' already has an "
                "active session"
            )
        thread_session.has_session = True
        try:
            with real_session_scope(
                hass=hass,
                session=session,
                exception_filter=exception_filter,
                read_only=read_only,
            ) as ses:
                yield ses
        finally:
            thread_session.has_session = False

    nightly = recorder.Recorder.async_nightly_tasks if enable_nightly_purge else None
    stats = recorder.Recorder.async_periodic_statistics if enable_statistics else None
    schema_validate = (
        migration._find_schema_errors
        if enable_schema_validation
        else itertools.repeat(set())
    )
    compile_missing = (
        recorder.Recorder._schedule_compile_missing_statistics
        if enable_missing_statistics
        else None
    )
    migrate_states_context_ids = (
        migration.StatesContextIDMigration.migrate_data
        if enable_migrate_state_context_ids
        else None
    )
    migrate_events_context_ids = (
        migration.EventsContextIDMigration.migrate_data
        if enable_migrate_event_context_ids
        else None
    )
    migrate_event_type_ids = (
        migration.EventTypeIDMigration.migrate_data
        if enable_migrate_event_type_ids
        else None
    )
    migrate_entity_ids = (
        migration.EntityIDMigration.migrate_data if enable_migrate_entity_ids else None
    )
    legacy_event_id_foreign_key_exists = (
        migration.EventIDPostMigration._legacy_event_id_foreign_key_exists
        if enable_migrate_event_ids
        else lambda _: None
    )
    with (
        patch(
            "homeassistant.components.recorder.Recorder.async_nightly_tasks",
            side_effect=nightly,
            autospec=True,
        ),
        patch(
            "homeassistant.components.recorder.Recorder.async_periodic_statistics",
            side_effect=stats,
            autospec=True,
        ),
        patch(
            "homeassistant.components.recorder.migration._find_schema_errors",
            side_effect=schema_validate,
            autospec=True,
        ),
        patch(
            "homeassistant.components.recorder.migration.EventsContextIDMigration.migrate_data",
            side_effect=migrate_events_context_ids,
            autospec=True,
        ),
        patch(
            "homeassistant.components.recorder.migration.StatesContextIDMigration.migrate_data",
            side_effect=migrate_states_context_ids,
            autospec=True,
        ),
        patch(
            "homeassistant.components.recorder.migration.EventTypeIDMigration.migrate_data",
            side_effect=migrate_event_type_ids,
            autospec=True,
        ),
        patch(
            "homeassistant.components.recorder.migration.EntityIDMigration.migrate_data",
            side_effect=migrate_entity_ids,
            autospec=True,
        ),
        patch(
            "homeassistant.components.recorder.migration.EventIDPostMigration._legacy_event_id_foreign_key_exists",
            side_effect=legacy_event_id_foreign_key_exists,
            autospec=True,
        ),
        patch(
            "homeassistant.components.recorder.Recorder._schedule_compile_missing_statistics",
            side_effect=compile_missing,
            autospec=True,
        ),
        patch.object(
            patch_recorder,
            "real_session_scope",
            side_effect=debug_session_scope,
            autospec=True,
        ),
    ):

        @asynccontextmanager
        async def async_test_recorder(
            hass: HomeAssistant,
            config: ConfigType | None = None,
            *,
            expected_setup_result: bool = True,
            wait_recorder: bool = True,
            wait_recorder_setup: bool = True,
        ) -> AsyncGenerator[recorder.Recorder]:
            """Setup and return recorder instance."""  # noqa: D401
            await _async_init_recorder_component(
                hass,
                config,
                recorder_db_url,
                expected_setup_result=expected_setup_result,
                wait_setup=wait_recorder_setup,
            )
            await hass.async_block_till_done()
            instance = hass.data[recorder.DATA_INSTANCE]
            # The recorder's worker is not started until Home Assistant is running
            if hass.state is CoreState.running and wait_recorder:
                await async_recorder_block_till_done(hass)
            try:
                yield instance
            finally:
                if instance.is_alive():
                    await instance._async_shutdown(None)

        yield async_test_recorder


@pytest.fixture
async def async_setup_recorder_instance(
    async_test_recorder: RecorderInstanceGenerator,
) -> AsyncGenerator[RecorderInstanceGenerator]:
    """Yield callable to setup recorder instance."""

    async with AsyncExitStack() as stack:

        async def async_setup_recorder(
            hass: HomeAssistant,
            config: ConfigType | None = None,
            *,
            expected_setup_result: bool = True,
            wait_recorder: bool = True,
            wait_recorder_setup: bool = True,
        ) -> AsyncGenerator[recorder.Recorder]:
            """Set up and return recorder instance."""

            return await stack.enter_async_context(
                async_test_recorder(
                    hass,
                    config,
                    expected_setup_result=expected_setup_result,
                    wait_recorder=wait_recorder,
                    wait_recorder_setup=wait_recorder_setup,
                )
            )

        yield async_setup_recorder


@pytest.fixture
async def recorder_mock(
    recorder_config: dict[str, Any] | None,
    async_test_recorder: RecorderInstanceGenerator,
    hass: HomeAssistant,
) -> AsyncGenerator[recorder.Recorder]:
    """Fixture with in-memory recorder."""
    async with async_test_recorder(hass, recorder_config) as instance:
        yield instance


@pytest.fixture
def mock_recorder_before_hass() -> None:
    """Mock the recorder.

    Override or parametrize this fixture with a fixture that mocks the recorder,
    in the tests that need to test the recorder.
    """


@pytest.fixture(name="enable_bluetooth")
async def mock_enable_bluetooth(
    hass: HomeAssistant,
    mock_bleak_scanner_start: MagicMock,
    mock_bluetooth_adapters: None,
) -> AsyncGenerator[None]:
    """Fixture to mock starting the bleak scanner."""
    entry = MockConfigEntry(domain="bluetooth", unique_id="00:00:00:00:00:01")
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    yield
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


@pytest.fixture(scope="session")
def mock_bluetooth_adapters() -> Generator[None]:
    """Fixture to mock bluetooth adapters."""
    with (
        patch("bluetooth_auto_recovery.recover_adapter"),
        patch("bluetooth_adapters.systems.platform.system", return_value="Linux"),
        patch("bluetooth_adapters.systems.linux.LinuxAdapters.refresh"),
        patch(
            "bluetooth_adapters.systems.linux.LinuxAdapters.adapters",
            {
                "hci0": {
                    "address": "00:00:00:00:00:01",
                    "hw_version": "usb:v1D6Bp0246d053F",
                    "passive_scan": False,
                    "sw_version": "homeassistant",
                    "manufacturer": "ACME",
                    "product": "Bluetooth Adapter 5.0",
                    "product_id": "aa01",
                    "vendor_id": "cc01",
                },
            },
        ),
    ):
        yield


@pytest.fixture
def mock_bleak_scanner_start() -> Generator[MagicMock]:
    """Fixture to mock starting the bleak scanner."""

    # Late imports to avoid loading bleak unless we need it

    # pylint: disable-next=import-outside-toplevel
    from habluetooth import scanner as bluetooth_scanner

    # We need to drop the stop method from the object since we patched
    # out start and this fixture will expire before the stop method is called
    # when EVENT_HOMEASSISTANT_STOP is fired.
    # pylint: disable-next=c-extension-no-member
    bluetooth_scanner.OriginalBleakScanner.stop = AsyncMock()  # type: ignore[assignment]
    with (
        patch.object(
            bluetooth_scanner.OriginalBleakScanner,  # pylint: disable=c-extension-no-member
            "start",
        ) as mock_bleak_scanner_start,
        patch.object(bluetooth_scanner, "HaScanner"),
    ):
        yield mock_bleak_scanner_start


@pytest.fixture
def mock_integration_frame() -> Generator[Mock]:
    """Mock as if we're calling code from inside an integration."""
    correct_frame = Mock(
        filename="/home/paulus/homeassistant/components/hue/light.py",
        lineno="23",
        line="self.light.is_on",
    )
    with (
        patch(
            "homeassistant.helpers.frame.linecache.getline",
            return_value=correct_frame.line,
        ),
        patch(
            "homeassistant.helpers.frame.get_current_frame",
            return_value=extract_stack_to_frame(
                [
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
                ]
            ),
        ),
    ):
        yield correct_frame


@pytest.fixture
def mock_bluetooth(
    mock_bleak_scanner_start: MagicMock, mock_bluetooth_adapters: None
) -> None:
    """Mock out bluetooth from starting."""


@pytest.fixture
def category_registry(hass: HomeAssistant) -> cr.CategoryRegistry:
    """Return the category registry from the current hass instance."""
    return cr.async_get(hass)


@pytest.fixture
def area_registry(hass: HomeAssistant) -> ar.AreaRegistry:
    """Return the area registry from the current hass instance."""
    return ar.async_get(hass)


@pytest.fixture
def device_registry(hass: HomeAssistant) -> dr.DeviceRegistry:
    """Return the device registry from the current hass instance."""
    return dr.async_get(hass)


@pytest.fixture
def entity_registry(hass: HomeAssistant) -> er.EntityRegistry:
    """Return the entity registry from the current hass instance."""
    return er.async_get(hass)


@pytest.fixture
def floor_registry(hass: HomeAssistant) -> fr.FloorRegistry:
    """Return the floor registry from the current hass instance."""
    return fr.async_get(hass)


@pytest.fixture
def issue_registry(hass: HomeAssistant) -> ir.IssueRegistry:
    """Return the issue registry from the current hass instance."""
    return ir.async_get(hass)


@pytest.fixture
def label_registry(hass: HomeAssistant) -> lr.LabelRegistry:
    """Return the label registry from the current hass instance."""
    return lr.async_get(hass)


@pytest.fixture
def service_calls(hass: HomeAssistant) -> Generator[list[ServiceCall]]:
    """Track all service calls."""
    calls = []

    _original_async_call = hass.services.async_call

    async def _async_call(
        self,
        domain: str,
        service: str,
        service_data: dict[str, Any] | None = None,
        blocking: bool = False,
        context: Context | None = None,
        target: dict[str, Any] | None = None,
        return_response: bool = False,
    ) -> ServiceResponse:
        calls.append(
            ServiceCall(domain, service, service_data, context, return_response)
        )
        try:
            return await _original_async_call(
                domain,
                service,
                service_data,
                blocking,
                context,
                target,
                return_response,
            )
        except ServiceNotFound:
            _LOGGER.debug("Ignoring unknown service call to %s.%s", domain, service)
        return None

    with patch("homeassistant.core.ServiceRegistry.async_call", _async_call):
        yield calls


@pytest.fixture
def snapshot(snapshot: SnapshotAssertion) -> SnapshotAssertion:
    """Return snapshot assertion fixture with the Home Assistant extension."""
    return snapshot.use_extension(HomeAssistantSnapshotExtension)


@pytest.fixture
def disable_block_async_io() -> Generator[None]:
    """Fixture to disable the loop protection from block_async_io."""
    yield
    calls = block_async_io._BLOCKED_CALLS.calls
    for blocking_call in calls:
        setattr(
            blocking_call.object, blocking_call.function, blocking_call.original_func
        )
    calls.clear()
