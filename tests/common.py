"""Test the helper method for writing tests."""
import asyncio
import functools as ft
import os
import sys
from unittest.mock import patch, MagicMock, Mock
from io import StringIO
import logging
import threading
from contextlib import contextmanager

from aiohttp import web

from homeassistant import core as ha, loader
from homeassistant.setup import setup_component, async_setup_component
from homeassistant.config import async_process_component_config
from homeassistant.helpers import intent, dispatcher, entity, restore_state
from homeassistant.util.unit_system import METRIC_SYSTEM
import homeassistant.util.dt as date_util
import homeassistant.util.yaml as yaml
from homeassistant.const import (
    STATE_ON, STATE_OFF, DEVICE_DEFAULT_NAME, EVENT_TIME_CHANGED,
    EVENT_STATE_CHANGED, EVENT_PLATFORM_DISCOVERED, ATTR_SERVICE,
    ATTR_DISCOVERED, SERVER_PORT, EVENT_HOMEASSISTANT_CLOSE)
from homeassistant.components import mqtt, recorder
from homeassistant.components.http.auth import auth_middleware
from homeassistant.components.http.const import (
    KEY_USE_X_FORWARDED_FOR, KEY_BANS_ENABLED, KEY_TRUSTED_NETWORKS)
from homeassistant.util.async import (
    run_callback_threadsafe, run_coroutine_threadsafe)

_TEST_INSTANCE_PORT = SERVER_PORT
_LOGGER = logging.getLogger(__name__)
INSTANCES = []


def threadsafe_callback_factory(func):
    """Create threadsafe functions out of callbacks.

    Callback needs to have `hass` as first argument.
    """
    @ft.wraps(func)
    def threadsafe(*args, **kwargs):
        """Call func threadsafe."""
        hass = args[0]
        return run_callback_threadsafe(
            hass.loop, ft.partial(func, *args, **kwargs)).result()

    return threadsafe


def threadsafe_coroutine_factory(func):
    """Create threadsafe functions out of coroutine.

    Callback needs to have `hass` as first argument.
    """
    @ft.wraps(func)
    def threadsafe(*args, **kwargs):
        """Call func threadsafe."""
        hass = args[0]
        return run_coroutine_threadsafe(
            func(*args, **kwargs), hass.loop).result()

    return threadsafe


def get_test_config_dir(*add_path):
    """Return a path to a test config dir."""
    return os.path.join(os.path.dirname(__file__), 'testing_config', *add_path)


def get_test_home_assistant():
    """Return a Home Assistant object pointing at test config directory."""
    if sys.platform == "win32":
        loop = asyncio.ProactorEventLoop()
    else:
        loop = asyncio.new_event_loop()

    hass = loop.run_until_complete(async_test_home_assistant(loop))

    stop_event = threading.Event()

    def run_loop():
        """Run event loop."""
        # pylint: disable=protected-access
        loop._thread_ident = threading.get_ident()
        loop.run_forever()
        stop_event.set()

    orig_stop = hass.stop

    def start_hass(*mocks):
        """Start hass."""
        run_coroutine_threadsafe(hass.async_start(), loop=hass.loop).result()

    def stop_hass():
        """Stop hass."""
        orig_stop()
        stop_event.wait()
        loop.close()

    hass.start = start_hass
    hass.stop = stop_hass

    threading.Thread(name="LoopThread", target=run_loop, daemon=False).start()

    return hass


# pylint: disable=protected-access
@asyncio.coroutine
def async_test_home_assistant(loop):
    """Return a Home Assistant object pointing at test config dir."""
    hass = ha.HomeAssistant(loop)
    INSTANCES.append(hass)

    orig_async_add_job = hass.async_add_job

    def async_add_job(target, *args):
        """Add a magic mock."""
        if isinstance(target, Mock):
            return mock_coro(target(*args))
        return orig_async_add_job(target, *args)

    hass.async_add_job = async_add_job

    hass.config.location_name = 'test home'
    hass.config.config_dir = get_test_config_dir()
    hass.config.latitude = 32.87336
    hass.config.longitude = -117.22743
    hass.config.elevation = 0
    hass.config.time_zone = date_util.get_time_zone('US/Pacific')
    hass.config.units = METRIC_SYSTEM
    hass.config.skip_pip = True

    if 'custom_components.test' not in loader.AVAILABLE_COMPONENTS:
        yield from loop.run_in_executor(None, loader.prepare, hass)

    hass.state = ha.CoreState.running

    # Mock async_start
    orig_start = hass.async_start

    @asyncio.coroutine
    def mock_async_start():
        """Start the mocking."""
        # We only mock time during tests and we want to track tasks
        with patch('homeassistant.core._async_create_timer'), \
                patch.object(hass, 'async_stop_track_tasks'):
            yield from orig_start()

    hass.async_start = mock_async_start

    @ha.callback
    def clear_instance(event):
        """Clear global instance."""
        INSTANCES.remove(hass)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_CLOSE, clear_instance)

    return hass


def get_test_instance_port():
    """Return unused port for running test instance.

    The socket that holds the default port does not get released when we stop
    HA in a different test case. Until I have figured out what is going on,
    let's run each test on a different port.
    """
    global _TEST_INSTANCE_PORT
    _TEST_INSTANCE_PORT += 1
    return _TEST_INSTANCE_PORT


@ha.callback
def async_mock_service(hass, domain, service, schema=None):
    """Set up a fake service & return a calls log list to this service."""
    calls = []

    @asyncio.coroutine
    def mock_service_log(call):  # pylint: disable=unnecessary-lambda
        """Mock service call."""
        calls.append(call)

    hass.services.async_register(
        domain, service, mock_service_log, schema=schema)

    return calls


mock_service = threadsafe_callback_factory(async_mock_service)


@ha.callback
def async_mock_intent(hass, intent_typ):
    """Set up a fake intent handler."""
    intents = []

    class MockIntentHandler(intent.IntentHandler):
        intent_type = intent_typ

        @asyncio.coroutine
        def async_handle(self, intent):
            """Handle the intent."""
            intents.append(intent)
            return intent.create_response()

    intent.async_register(hass, MockIntentHandler())

    return intents


@ha.callback
def async_fire_mqtt_message(hass, topic, payload, qos=0):
    """Fire the MQTT message."""
    if isinstance(payload, str):
        payload = payload.encode('utf-8')
    dispatcher.async_dispatcher_send(
        hass, mqtt.SIGNAL_MQTT_MESSAGE_RECEIVED, topic,
        payload, qos)


fire_mqtt_message = threadsafe_callback_factory(async_fire_mqtt_message)


@ha.callback
def async_fire_time_changed(hass, time):
    """Fire a time changes event."""
    hass.bus.async_fire(EVENT_TIME_CHANGED, {'now': time})


fire_time_changed = threadsafe_callback_factory(async_fire_time_changed)


def fire_service_discovered(hass, service, info):
    """Fire the MQTT message."""
    hass.bus.fire(EVENT_PLATFORM_DISCOVERED, {
        ATTR_SERVICE: service,
        ATTR_DISCOVERED: info
    })


def load_fixture(filename):
    """Load a fixture."""
    path = os.path.join(os.path.dirname(__file__), 'fixtures', filename)
    with open(path) as fptr:
        return fptr.read()


def mock_state_change_event(hass, new_state, old_state=None):
    """Mock state change envent."""
    event_data = {
        'entity_id': new_state.entity_id,
        'new_state': new_state,
    }

    if old_state:
        event_data['old_state'] = old_state

    hass.bus.fire(EVENT_STATE_CHANGED, event_data)


def mock_http_component(hass, api_password=None):
    """Mock the HTTP component."""
    hass.http = MagicMock(api_password=api_password)
    mock_component(hass, 'http')
    hass.http.views = {}

    def mock_register_view(view):
        """Store registered view."""
        if isinstance(view, type):
            # Instantiate the view, if needed
            view = view()

        hass.http.views[view.name] = view

    hass.http.register_view = mock_register_view


def mock_http_component_app(hass, api_password=None):
    """Create an aiohttp.web.Application instance for testing."""
    if 'http' not in hass.config.components:
        mock_http_component(hass, api_password)
    app = web.Application(middlewares=[auth_middleware])
    app['hass'] = hass
    app[KEY_USE_X_FORWARDED_FOR] = False
    app[KEY_BANS_ENABLED] = False
    app[KEY_TRUSTED_NETWORKS] = []
    return app


@asyncio.coroutine
def async_mock_mqtt_component(hass):
    """Mock the MQTT component."""
    with patch('homeassistant.components.mqtt.MQTT') as mock_mqtt:
        mock_mqtt().async_connect.return_value = mock_coro(True)
        yield from async_setup_component(hass, mqtt.DOMAIN, {
            mqtt.DOMAIN: {
                mqtt.CONF_BROKER: 'mock-broker',
            }
        })
        return mock_mqtt


mock_mqtt_component = threadsafe_coroutine_factory(async_mock_mqtt_component)


@ha.callback
def mock_component(hass, component):
    """Mock a component is setup."""
    if component in hass.config.components:
        AssertionError("Component {} is already setup".format(component))

    hass.config.components.add(component)


class MockModule(object):
    """Representation of a fake module."""

    # pylint: disable=invalid-name
    def __init__(self, domain=None, dependencies=None, setup=None,
                 requirements=None, config_schema=None, platform_schema=None,
                 async_setup=None):
        """Initialize the mock module."""
        self.DOMAIN = domain
        self.DEPENDENCIES = dependencies or []
        self.REQUIREMENTS = requirements or []
        self._setup = setup

        if config_schema is not None:
            self.CONFIG_SCHEMA = config_schema

        if platform_schema is not None:
            self.PLATFORM_SCHEMA = platform_schema

        if async_setup is not None:
            self.async_setup = async_setup

    def setup(self, hass, config):
        """Set up the component.

        We always define this mock because MagicMock setups will be seen by the
        executor as a coroutine, raising an exception.
        """
        if self._setup is not None:
            return self._setup(hass, config)
        return True


class MockPlatform(object):
    """Provide a fake platform."""

    # pylint: disable=invalid-name
    def __init__(self, setup_platform=None, dependencies=None,
                 platform_schema=None, async_setup_platform=None):
        """Initialize the platform."""
        self.DEPENDENCIES = dependencies or []
        self._setup_platform = setup_platform

        if platform_schema is not None:
            self.PLATFORM_SCHEMA = platform_schema

        if async_setup_platform is not None:
            self.async_setup_platform = async_setup_platform

    def setup_platform(self, hass, config, add_devices, discovery_info=None):
        """Set up the platform."""
        if self._setup_platform is not None:
            self._setup_platform(hass, config, add_devices, discovery_info)


class MockToggleDevice(entity.ToggleEntity):
    """Provide a mock toggle device."""

    def __init__(self, name, state):
        """Initialize the mock device."""
        self._name = name or DEVICE_DEFAULT_NAME
        self._state = state
        self.calls = []

    @property
    def name(self):
        """Return the name of the device if any."""
        self.calls.append(('name', {}))
        return self._name

    @property
    def state(self):
        """Return the name of the device if any."""
        self.calls.append(('state', {}))
        return self._state

    @property
    def is_on(self):
        """Return true if device is on."""
        self.calls.append(('is_on', {}))
        return self._state == STATE_ON

    def turn_on(self, **kwargs):
        """Turn the device on."""
        self.calls.append(('turn_on', kwargs))
        self._state = STATE_ON

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self.calls.append(('turn_off', kwargs))
        self._state = STATE_OFF

    def last_call(self, method=None):
        """Return the last call."""
        if not self.calls:
            return None
        elif method is None:
            return self.calls[-1]
        else:
            try:
                return next(call for call in reversed(self.calls)
                            if call[0] == method)
            except StopIteration:
                return None


def patch_yaml_files(files_dict, endswith=True):
    """Patch load_yaml with a dictionary of yaml files."""
    # match using endswith, start search with longest string
    matchlist = sorted(list(files_dict.keys()), key=len) if endswith else []

    def mock_open_f(fname, **_):
        """Mock open() in the yaml module, used by load_yaml."""
        # Return the mocked file on full match
        if fname in files_dict:
            _LOGGER.debug("patch_yaml_files match %s", fname)
            res = StringIO(files_dict[fname])
            setattr(res, 'name', fname)
            return res

        # Match using endswith
        for ends in matchlist:
            if fname.endswith(ends):
                _LOGGER.debug("patch_yaml_files end match %s: %s", ends, fname)
                res = StringIO(files_dict[ends])
                setattr(res, 'name', fname)
                return res

        # Fallback for hass.components (i.e. services.yaml)
        if 'homeassistant/components' in fname:
            _LOGGER.debug("patch_yaml_files using real file: %s", fname)
            return open(fname, encoding='utf-8')

        # Not found
        raise FileNotFoundError("File not found: {}".format(fname))

    return patch.object(yaml, 'open', mock_open_f, create=True)


def mock_coro(return_value=None):
    """Return a coro that returns a value."""
    return mock_coro_func(return_value)()


def mock_coro_func(return_value=None):
    """Return a method to create a coro function that returns a value."""
    @asyncio.coroutine
    def coro(*args, **kwargs):
        """Fake coroutine."""
        return return_value

    return coro


@contextmanager
def assert_setup_component(count, domain=None):
    """Collect valid configuration from setup_component.

    - count: The amount of valid platforms that should be setup
    - domain: The domain to count is optional. It can be automatically
              determined most of the time

    Use as a context manager around setup.setup_component
        with assert_setup_component(0) as result_config:
            setup_component(hass, domain, start_config)
            # using result_config is optional
    """
    config = {}

    @ha.callback
    def mock_psc(hass, config_input, domain):
        """Mock the prepare_setup_component to capture config."""
        res = async_process_component_config(
            hass, config_input, domain)
        config[domain] = None if res is None else res.get(domain)
        _LOGGER.debug("Configuration for %s, Validated: %s, Original %s",
                      domain, config[domain], config_input.get(domain))
        return res

    assert isinstance(config, dict)
    with patch('homeassistant.config.async_process_component_config',
               mock_psc):
        yield config

    if domain is None:
        assert len(config) == 1, ('assert_setup_component requires DOMAIN: {}'
                                  .format(list(config.keys())))
        domain = list(config.keys())[0]

    res = config.get(domain)
    res_len = 0 if res is None else len(res)
    assert res_len == count, 'setup_component failed, expected {} got {}: {}' \
        .format(count, res_len, res)


def init_recorder_component(hass, add_config=None):
    """Initialize the recorder."""
    config = dict(add_config) if add_config else {}
    config[recorder.CONF_DB_URL] = 'sqlite://'  # In memory DB

    with patch('homeassistant.components.recorder.migration.migrate_schema'):
        assert setup_component(hass, recorder.DOMAIN,
                               {recorder.DOMAIN: config})
        assert recorder.DOMAIN in hass.config.components
    _LOGGER.info("In-memory recorder successfully started")


def mock_restore_cache(hass, states):
    """Mock the DATA_RESTORE_CACHE."""
    key = restore_state.DATA_RESTORE_CACHE
    hass.data[key] = {
        state.entity_id: state for state in states}
    _LOGGER.debug('Restore cache: %s', hass.data[key])
    assert len(hass.data[key]) == len(states), \
        "Duplicate entity_id? {}".format(states)
    hass.state = ha.CoreState.starting
    mock_component(hass, recorder.DOMAIN)


class MockDependency:
    """Decorator to mock install a dependency."""

    def __init__(self, root, *args):
        """Initialize decorator."""
        self.root = root
        self.submodules = args

    def __enter__(self):
        """Start mocking."""
        def resolve(mock, path):
            """Resolve a mock."""
            if not path:
                return mock

            return resolve(getattr(mock, path[0]), path[1:])

        base = MagicMock()
        to_mock = {
            "{}.{}".format(self.root, tom): resolve(base, tom.split('.'))
            for tom in self.submodules
        }
        to_mock[self.root] = base

        self.patcher = patch.dict('sys.modules', to_mock)
        self.patcher.start()
        return base

    def __exit__(self, *exc):
        """Stop mocking."""
        self.patcher.stop()
        return False

    def __call__(self, func):
        """Apply decorator."""
        def run_mocked(*args, **kwargs):
            """Run with mocked dependencies."""
            with self as base:
                args = list(args) + [base]
                func(*args, **kwargs)

        return run_mocked
