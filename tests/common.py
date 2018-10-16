"""Test the helper method for writing tests."""
import asyncio
from collections import OrderedDict
from datetime import timedelta
import functools as ft
import json
import os
import sys
from unittest.mock import patch, MagicMock, Mock
from io import StringIO
import logging
import threading
from contextlib import contextmanager

from homeassistant import auth, core as ha, config_entries
from homeassistant.auth import (
    models as auth_models, auth_store, providers as auth_providers)
from homeassistant.setup import setup_component, async_setup_component
from homeassistant.config import async_process_component_config
from homeassistant.helpers import (
    intent, entity, restore_state, entity_registry,
    entity_platform, storage, device_registry)
from homeassistant.util.unit_system import METRIC_SYSTEM
import homeassistant.util.dt as date_util
import homeassistant.util.yaml as yaml
from homeassistant.const import (
    STATE_ON, STATE_OFF, DEVICE_DEFAULT_NAME, EVENT_TIME_CHANGED,
    EVENT_STATE_CHANGED, EVENT_PLATFORM_DISCOVERED, ATTR_SERVICE,
    ATTR_DISCOVERED, SERVER_PORT, EVENT_HOMEASSISTANT_CLOSE)
from homeassistant.components import mqtt, recorder
from homeassistant.util.async_ import (
    run_callback_threadsafe, run_coroutine_threadsafe)

_TEST_INSTANCE_PORT = SERVER_PORT
_LOGGER = logging.getLogger(__name__)
INSTANCES = []
CLIENT_ID = 'https://example.com/app'
CLIENT_REDIRECT_URI = 'https://example.com/app/callback'


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
    hass.config.async_load = Mock()
    store = auth_store.AuthStore(hass)
    hass.auth = auth.AuthManager(hass, store, {}, {})
    ensure_auth_manager_loaded(hass.auth)
    INSTANCES.append(hass)

    orig_async_add_job = hass.async_add_job
    orig_async_add_executor_job = hass.async_add_executor_job
    orig_async_create_task = hass.async_create_task

    def async_add_job(target, *args):
        """Add job."""
        if isinstance(target, Mock):
            return mock_coro(target(*args))
        return orig_async_add_job(target, *args)

    def async_add_executor_job(target, *args):
        """Add executor job."""
        if isinstance(target, Mock):
            return mock_coro(target(*args))
        return orig_async_add_executor_job(target, *args)

    def async_create_task(coroutine):
        """Create task."""
        if isinstance(coroutine, Mock):
            return mock_coro()
        return orig_async_create_task(coroutine)

    hass.async_add_job = async_add_job
    hass.async_add_executor_job = async_add_executor_job
    hass.async_create_task = async_create_task

    hass.config.location_name = 'test home'
    hass.config.config_dir = get_test_config_dir()
    hass.config.latitude = 32.87336
    hass.config.longitude = -117.22743
    hass.config.elevation = 0
    hass.config.time_zone = date_util.get_time_zone('US/Pacific')
    hass.config.units = METRIC_SYSTEM
    hass.config.skip_pip = True

    hass.config_entries = config_entries.ConfigEntries(hass, {})
    hass.config_entries._entries = []
    hass.config_entries._store._async_ensure_stop_listener = lambda: None

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

    @ha.callback
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
def async_fire_mqtt_message(hass, topic, payload, qos=0, retain=False):
    """Fire the MQTT message."""
    if isinstance(payload, str):
        payload = payload.encode('utf-8')
    msg = mqtt.Message(topic, payload, qos, retain)
    hass.async_run_job(hass.data['mqtt']._mqtt_on_message, None, None, msg)


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
    with open(path, encoding='utf-8') as fptr:
        return fptr.read()


def mock_state_change_event(hass, new_state, old_state=None):
    """Mock state change envent."""
    event_data = {
        'entity_id': new_state.entity_id,
        'new_state': new_state,
    }

    if old_state:
        event_data['old_state'] = old_state

    hass.bus.fire(EVENT_STATE_CHANGED, event_data, context=new_state.context)


@asyncio.coroutine
def async_mock_mqtt_component(hass, config=None):
    """Mock the MQTT component."""
    if config is None:
        config = {mqtt.CONF_BROKER: 'mock-broker'}

    with patch('paho.mqtt.client.Client') as mock_client:
        mock_client().connect.return_value = 0
        mock_client().subscribe.return_value = (0, 0)
        mock_client().publish.return_value = (0, 0)

        result = yield from async_setup_component(hass, mqtt.DOMAIN, {
            mqtt.DOMAIN: config
        })
        assert result

        hass.data['mqtt'] = MagicMock(spec_set=hass.data['mqtt'],
                                      wraps=hass.data['mqtt'])

        return hass.data['mqtt']


mock_mqtt_component = threadsafe_coroutine_factory(async_mock_mqtt_component)


@ha.callback
def mock_component(hass, component):
    """Mock a component is setup."""
    if component in hass.config.components:
        AssertionError("Component {} is already setup".format(component))

    hass.config.components.add(component)


def mock_registry(hass, mock_entries=None):
    """Mock the Entity Registry."""
    registry = entity_registry.EntityRegistry(hass)
    registry.entities = mock_entries or OrderedDict()

    async def _get_reg():
        return registry

    hass.data[entity_registry.DATA_REGISTRY] = \
        hass.loop.create_task(_get_reg())
    return registry


def mock_device_registry(hass, mock_entries=None):
    """Mock the Device Registry."""
    registry = device_registry.DeviceRegistry(hass)
    registry.devices = mock_entries or OrderedDict()

    async def _get_reg():
        return registry

    hass.data[device_registry.DATA_REGISTRY] = \
        hass.loop.create_task(_get_reg())
    return registry


class MockUser(auth_models.User):
    """Mock a user in Home Assistant."""

    def __init__(self, id=None, is_owner=False, is_active=True,
                 name='Mock User', system_generated=False):
        """Initialize mock user."""
        kwargs = {
            'is_owner': is_owner,
            'is_active': is_active,
            'name': name,
            'system_generated': system_generated,
        }
        if id is not None:
            kwargs['id'] = id
        super().__init__(**kwargs)

    def add_to_hass(self, hass):
        """Test helper to add entry to hass."""
        return self.add_to_auth_manager(hass.auth)

    def add_to_auth_manager(self, auth_mgr):
        """Test helper to add entry to hass."""
        ensure_auth_manager_loaded(auth_mgr)
        auth_mgr._store._users[self.id] = self
        return self


async def register_auth_provider(hass, config):
    """Register an auth provider."""
    provider = await auth_providers.auth_provider_from_config(
        hass, hass.auth._store, config)
    assert provider is not None, 'Invalid config specified'
    key = (provider.type, provider.id)
    providers = hass.auth._providers

    if key in providers:
        raise ValueError('Provider already registered')

    providers[key] = provider
    return provider


@ha.callback
def ensure_auth_manager_loaded(auth_mgr):
    """Ensure an auth manager is considered loaded."""
    store = auth_mgr._store
    if store._users is None:
        store._set_defaults()


class MockModule:
    """Representation of a fake module."""

    # pylint: disable=invalid-name
    def __init__(self, domain=None, dependencies=None, setup=None,
                 requirements=None, config_schema=None, platform_schema=None,
                 async_setup=None, async_setup_entry=None,
                 async_unload_entry=None):
        """Initialize the mock module."""
        self.DOMAIN = domain
        self.DEPENDENCIES = dependencies or []
        self.REQUIREMENTS = requirements or []

        if config_schema is not None:
            self.CONFIG_SCHEMA = config_schema

        if platform_schema is not None:
            self.PLATFORM_SCHEMA = platform_schema

        if setup is not None:
            # We run this in executor, wrap it in function
            self.setup = lambda *args: setup(*args)

        if async_setup is not None:
            self.async_setup = async_setup

        if setup is None and async_setup is None:
            self.async_setup = mock_coro_func(True)

        if async_setup_entry is not None:
            self.async_setup_entry = async_setup_entry

        if async_unload_entry is not None:
            self.async_unload_entry = async_unload_entry


class MockPlatform:
    """Provide a fake platform."""

    # pylint: disable=invalid-name
    def __init__(self, setup_platform=None, dependencies=None,
                 platform_schema=None, async_setup_platform=None,
                 async_setup_entry=None, scan_interval=None):
        """Initialize the platform."""
        self.DEPENDENCIES = dependencies or []

        if platform_schema is not None:
            self.PLATFORM_SCHEMA = platform_schema

        if scan_interval is not None:
            self.SCAN_INTERVAL = scan_interval

        if setup_platform is not None:
            # We run this in executor, wrap it in function
            self.setup_platform = lambda *args: setup_platform(*args)

        if async_setup_platform is not None:
            self.async_setup_platform = async_setup_platform

        if async_setup_entry is not None:
            self.async_setup_entry = async_setup_entry

        if setup_platform is None and async_setup_platform is None:
            self.async_setup_platform = mock_coro_func()


class MockEntityPlatform(entity_platform.EntityPlatform):
    """Mock class with some mock defaults."""

    def __init__(
        self, hass,
        logger=None,
        domain='test_domain',
        platform_name='test_platform',
        platform=None,
        scan_interval=timedelta(seconds=15),
        entity_namespace=None,
        async_entities_added_callback=lambda: None
    ):
        """Initialize a mock entity platform."""
        if logger is None:
            logger = logging.getLogger('homeassistant.helpers.entity_platform')

        # Otherwise the constructor will blow up.
        if (isinstance(platform, Mock) and
                isinstance(platform.PARALLEL_UPDATES, Mock)):
            platform.PARALLEL_UPDATES = 0

        super().__init__(
            hass=hass,
            logger=logger,
            domain=domain,
            platform_name=platform_name,
            platform=platform,
            scan_interval=scan_interval,
            entity_namespace=entity_namespace,
            async_entities_added_callback=async_entities_added_callback,
        )


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
        if method is None:
            return self.calls[-1]
        try:
            return next(call for call in reversed(self.calls)
                        if call[0] == method)
        except StopIteration:
            return None


class MockConfigEntry(config_entries.ConfigEntry):
    """Helper for creating config entries that adds some defaults."""

    def __init__(self, *, domain='test', data=None, version=0, entry_id=None,
                 source=config_entries.SOURCE_USER, title='Mock Title',
                 state=None,
                 connection_class=config_entries.CONN_CLASS_UNKNOWN):
        """Initialize a mock config entry."""
        kwargs = {
            'entry_id': entry_id or 'mock-id',
            'domain': domain,
            'data': data or {},
            'version': version,
            'title': title,
            'connection_class': connection_class,
        }
        if source is not None:
            kwargs['source'] = source
        if state is not None:
            kwargs['state'] = state
        super().__init__(**kwargs)

    def add_to_hass(self, hass):
        """Test helper to add entry to hass."""
        hass.config_entries._entries.append(self)

    def add_to_manager(self, manager):
        """Test helper to add entry to entry manager."""
        manager._entries.append(self)


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


def mock_coro(return_value=None, exception=None):
    """Return a coro that returns a value or raise an exception."""
    return mock_coro_func(return_value, exception)()


def mock_coro_func(return_value=None, exception=None):
    """Return a method to create a coro function that returns a value."""
    @asyncio.coroutine
    def coro(*args, **kwargs):
        """Fake coroutine."""
        if exception:
            raise exception
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


class MockEntity(entity.Entity):
    """Mock Entity class."""

    def __init__(self, **values):
        """Initialize an entity."""
        self._values = values

        if 'entity_id' in values:
            self.entity_id = values['entity_id']

    @property
    def name(self):
        """Return the name of the entity."""
        return self._handle('name')

    @property
    def should_poll(self):
        """Return the ste of the polling."""
        return self._handle('should_poll')

    @property
    def unique_id(self):
        """Return the unique ID of the entity."""
        return self._handle('unique_id')

    @property
    def available(self):
        """Return True if entity is available."""
        return self._handle('available')

    @property
    def device_info(self):
        """Info how it links to a device."""
        return self._handle('device_info')

    def _handle(self, attr):
        """Return attribute value."""
        if attr in self._values:
            return self._values[attr]
        return getattr(super(), attr)


@contextmanager
def mock_storage(data=None):
    """Mock storage.

    Data is a dict {'key': {'version': version, 'data': data}}

    Written data will be converted to JSON to ensure JSON parsing works.
    """
    if data is None:
        data = {}

    orig_load = storage.Store._async_load

    async def mock_async_load(store):
        """Mock version of load."""
        if store._data is None:
            # No data to load
            if store.key not in data:
                return None

            mock_data = data.get(store.key)

            if 'data' not in mock_data or 'version' not in mock_data:
                _LOGGER.error('Mock data needs "version" and "data"')
                raise ValueError('Mock data needs "version" and "data"')

            store._data = mock_data

        # Route through original load so that we trigger migration
        loaded = await orig_load(store)
        _LOGGER.info('Loading data for %s: %s', store.key, loaded)
        return loaded

    def mock_write_data(store, path, data_to_write):
        """Mock version of write data."""
        # To ensure that the data can be serialized
        _LOGGER.info('Writing data to %s: %s', store.key, data_to_write)
        data[store.key] = json.loads(json.dumps(data_to_write))

    with patch('homeassistant.helpers.storage.Store._async_load',
               side_effect=mock_async_load, autospec=True), \
        patch('homeassistant.helpers.storage.Store._write_data',
              side_effect=mock_write_data, autospec=True):
        yield data


async def flush_store(store):
    """Make sure all delayed writes of a store are written."""
    if store._data is None:
        return

    await store._async_handle_write_data()
