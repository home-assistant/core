"""Set up some common test helper things."""
import asyncio
import datetime
import functools
import logging
import ssl
import threading

from aiohttp.test_utils import make_mocked_request
import multidict
import pytest
import requests_mock as _requests_mock

from homeassistant import core as ha, loader, runner, util
from homeassistant.auth.const import GROUP_ID_ADMIN, GROUP_ID_READ_ONLY
from homeassistant.auth.providers import homeassistant, legacy_api_password
from homeassistant.components import mqtt
from homeassistant.components.websocket_api.auth import (
    TYPE_AUTH,
    TYPE_AUTH_OK,
    TYPE_AUTH_REQUIRED,
)
from homeassistant.components.websocket_api.http import URL
from homeassistant.const import ATTR_NOW, EVENT_TIME_CHANGED
from homeassistant.exceptions import ServiceNotFound
from homeassistant.helpers import config_entry_oauth2_flow, event
from homeassistant.setup import async_setup_component
from homeassistant.util import location

from tests.async_mock import MagicMock, patch
from tests.ignore_uncaught_exceptions import IGNORE_UNCAUGHT_EXCEPTIONS

pytest.register_assert_rewrite("tests.common")

from tests.common import (  # noqa: E402, isort:skip
    CLIENT_ID,
    INSTANCES,
    MockUser,
    async_fire_mqtt_message,
    async_test_home_assistant,
    mock_storage as mock_storage,
)
from tests.test_util.aiohttp import mock_aiohttp_client  # noqa: E402, isort:skip


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


@pytest.fixture
def hass_storage():
    """Fixture to mock storage."""
    with mock_storage() as stored_data:
        yield stored_data


@pytest.fixture
def hass(loop, hass_storage, request):
    """Fixture to provide a test instance of Home Assistant."""

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
    hass = loop.run_until_complete(async_test_home_assistant(loop))
    orig_exception_handler = loop.get_exception_handler()
    loop.set_exception_handler(exc_handle)

    yield hass

    loop.run_until_complete(hass.async_stop(force=True))
    for ex in exceptions:
        if (
            request.module.__name__,
            request.function.__name__,
        ) in IGNORE_UNCAUGHT_EXCEPTIONS:
            continue
        if isinstance(ex, ServiceNotFound):
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
            hass.http.app, headers={"Authorization": f"Bearer {hass_access_token}"}
        )

    return auth_client


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
def hass_ws_client(aiohttp_client, hass_access_token, hass):
    """Websocket client fixture connected to websocket server."""

    async def create_client(hass=hass, access_token=hass_access_token):
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

    result = await async_setup_component(hass, mqtt.DOMAIN, {mqtt.DOMAIN: mqtt_config})
    assert result
    await hass.async_block_till_done()

    # Workaround: asynctest==0.13 fails on @functools.lru_cache
    spec = dir(hass.data["mqtt"])
    spec.remove("_matching_subscriptions")

    mqtt_component_mock = MagicMock(
        return_value=hass.data["mqtt"],
        spec_set=spec,
        wraps=hass.data["mqtt"],
    )
    mqtt_component_mock._mqttc = mqtt_client_mock

    hass.data["mqtt"] = mqtt_component_mock
    component = hass.data["mqtt"]
    component.reset_mock()
    return component


@pytest.fixture
def mock_zeroconf():
    """Mock zeroconf."""
    with patch("homeassistant.components.zeroconf.HaZeroconf") as mock_zc:
        yield mock_zc.return_value


@pytest.fixture
def legacy_patchable_time():
    """Allow time to be patchable by using event listeners instead of asyncio loop."""

    @ha.callback
    @loader.bind_hass
    def async_track_point_in_utc_time(hass, action, point_in_time):
        """Add a listener that fires once after a specific point in UTC time."""
        # Ensure point_in_time is UTC
        point_in_time = event.dt_util.as_utc(point_in_time)

        # Since this is called once, we accept a HassJob so we can avoid
        # having to figure out how to call the action every time its called.
        job = action if isinstance(action, ha.HassJob) else ha.HassJob(action)

        @ha.callback
        def point_in_time_listener(event):
            """Listen for matching time_changed events."""
            now = event.data[ATTR_NOW]

            if now < point_in_time or hasattr(point_in_time_listener, "run"):
                return

            # Set variable so that we will never run twice.
            # Because the event bus might have to wait till a thread comes
            # available to execute this listener it might occur that the
            # listener gets lined up twice to be executed. This will make
            # sure the second time it does nothing.
            setattr(point_in_time_listener, "run", True)
            async_unsub()

            hass.async_run_hass_job(job, now)

        async_unsub = hass.bus.async_listen(EVENT_TIME_CHANGED, point_in_time_listener)

        return async_unsub

    @ha.callback
    @loader.bind_hass
    def async_track_utc_time_change(
        hass, action, hour=None, minute=None, second=None, local=False
    ):
        """Add a listener that will fire if time matches a pattern."""

        job = ha.HassJob(action)
        # We do not have to wrap the function with time pattern matching logic
        # if no pattern given
        if all(val is None for val in (hour, minute, second)):

            @ha.callback
            def time_change_listener(ev) -> None:
                """Fire every time event that comes in."""
                hass.async_run_hass_job(job, ev.data[ATTR_NOW])

            return hass.bus.async_listen(EVENT_TIME_CHANGED, time_change_listener)

        matching_seconds = event.dt_util.parse_time_expression(second, 0, 59)
        matching_minutes = event.dt_util.parse_time_expression(minute, 0, 59)
        matching_hours = event.dt_util.parse_time_expression(hour, 0, 23)

        next_time = None

        def calculate_next(now) -> None:
            """Calculate and set the next time the trigger should fire."""
            nonlocal next_time

            localized_now = event.dt_util.as_local(now) if local else now
            next_time = event.dt_util.find_next_time_expression_time(
                localized_now, matching_seconds, matching_minutes, matching_hours
            )

        # Make sure rolling back the clock doesn't prevent the timer from
        # triggering.
        last_now = None

        @ha.callback
        def pattern_time_change_listener(ev) -> None:
            """Listen for matching time_changed events."""
            nonlocal next_time, last_now

            now = ev.data[ATTR_NOW]

            if last_now is None or now < last_now:
                # Time rolled back or next time not yet calculated
                calculate_next(now)

            last_now = now

            if next_time <= now:
                hass.async_run_hass_job(
                    job, event.dt_util.as_local(now) if local else now
                )
                calculate_next(now + datetime.timedelta(seconds=1))

        # We can't use async_track_point_in_utc_time here because it would
        # break in the case that the system time abruptly jumps backwards.
        # Our custom last_now logic takes care of resolving that scenario.
        return hass.bus.async_listen(EVENT_TIME_CHANGED, pattern_time_change_listener)

    with patch(
        "homeassistant.helpers.event.async_track_point_in_utc_time",
        async_track_point_in_utc_time,
    ), patch(
        "homeassistant.helpers.event.async_track_utc_time_change",
        async_track_utc_time_change,
    ):
        yield


@pytest.fixture
def enable_custom_integrations(hass):
    """Enable custom integrations defined in the test dir."""
    hass.data.pop(loader.DATA_CUSTOM_COMPONENTS)
