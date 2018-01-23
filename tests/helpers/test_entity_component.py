"""The tests for the Entity component helper."""
# pylint: disable=protected-access
import asyncio
from collections import OrderedDict
import logging
import unittest
from unittest.mock import patch, Mock, MagicMock
from datetime import timedelta

import homeassistant.core as ha
import homeassistant.loader as loader
from homeassistant.exceptions import PlatformNotReady
from homeassistant.components import group
from homeassistant.helpers.entity import Entity, generate_entity_id
from homeassistant.helpers.entity_component import (
    EntityComponent, DEFAULT_SCAN_INTERVAL, SLOW_SETUP_WARNING)
from homeassistant.helpers import entity_component
from homeassistant.setup import setup_component

from homeassistant.helpers import discovery
import homeassistant.util.dt as dt_util

from tests.common import (
    get_test_home_assistant, MockPlatform, MockModule, fire_time_changed,
    mock_coro, async_fire_time_changed)

_LOGGER = logging.getLogger(__name__)
DOMAIN = "test_domain"


class EntityTest(Entity):
    """Test for the Entity component."""

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

    def _handle(self, attr):
        """Helper for the attributes."""
        if attr in self._values:
            return self._values[attr]
        return getattr(super(), attr)


class TestHelpersEntityComponent(unittest.TestCase):
    """Test homeassistant.helpers.entity_component module."""

    def setUp(self):  # pylint: disable=invalid-name
        """Initialize a test Home Assistant instance."""
        self.hass = get_test_home_assistant()

    def tearDown(self):  # pylint: disable=invalid-name
        """Clean up the test Home Assistant instance."""
        self.hass.stop()

    def test_setting_up_group(self):
        """Setup the setting of a group."""
        setup_component(self.hass, 'group', {'group': {}})
        component = EntityComponent(_LOGGER, DOMAIN, self.hass,
                                    group_name='everyone')

        # No group after setup
        assert len(self.hass.states.entity_ids()) == 0

        component.add_entities([EntityTest()])
        self.hass.block_till_done()

        # group exists
        assert len(self.hass.states.entity_ids()) == 2
        assert self.hass.states.entity_ids('group') == ['group.everyone']

        group = self.hass.states.get('group.everyone')

        assert group.attributes.get('entity_id') == \
            ('test_domain.unnamed_device',)

        # group extended
        component.add_entities([EntityTest(name='goodbye')])
        self.hass.block_till_done()

        assert len(self.hass.states.entity_ids()) == 3
        group = self.hass.states.get('group.everyone')

        # Ordered in order of added to the group
        assert group.attributes.get('entity_id') == \
            ('test_domain.goodbye', 'test_domain.unnamed_device')

    def test_polling_only_updates_entities_it_should_poll(self):
        """Test the polling of only updated entities."""
        component = EntityComponent(
            _LOGGER, DOMAIN, self.hass, timedelta(seconds=20))

        no_poll_ent = EntityTest(should_poll=False)
        no_poll_ent.async_update = Mock()
        poll_ent = EntityTest(should_poll=True)
        poll_ent.async_update = Mock()

        component.add_entities([no_poll_ent, poll_ent])

        no_poll_ent.async_update.reset_mock()
        poll_ent.async_update.reset_mock()

        fire_time_changed(self.hass, dt_util.utcnow() + timedelta(seconds=20))
        self.hass.block_till_done()

        assert not no_poll_ent.async_update.called
        assert poll_ent.async_update.called

    def test_polling_updates_entities_with_exception(self):
        """Test the updated entities that not break with a exception."""
        component = EntityComponent(
            _LOGGER, DOMAIN, self.hass, timedelta(seconds=20))

        update_ok = []
        update_err = []

        def update_mock():
            """Mock normal update."""
            update_ok.append(None)

        def update_mock_err():
            """Mock error update."""
            update_err.append(None)
            raise AssertionError("Fake error update")

        ent1 = EntityTest(should_poll=True)
        ent1.update = update_mock_err
        ent2 = EntityTest(should_poll=True)
        ent2.update = update_mock
        ent3 = EntityTest(should_poll=True)
        ent3.update = update_mock
        ent4 = EntityTest(should_poll=True)
        ent4.update = update_mock

        component.add_entities([ent1, ent2, ent3, ent4])

        update_ok.clear()
        update_err.clear()

        fire_time_changed(self.hass, dt_util.utcnow() + timedelta(seconds=20))
        self.hass.block_till_done()

        assert len(update_ok) == 3
        assert len(update_err) == 1

    def test_update_state_adds_entities(self):
        """Test if updating poll entities cause an entity to be added works."""
        component = EntityComponent(_LOGGER, DOMAIN, self.hass)

        ent1 = EntityTest()
        ent2 = EntityTest(should_poll=True)

        component.add_entities([ent2])
        assert 1 == len(self.hass.states.entity_ids())
        ent2.update = lambda *_: component.add_entities([ent1])

        fire_time_changed(
            self.hass, dt_util.utcnow() + DEFAULT_SCAN_INTERVAL
        )
        self.hass.block_till_done()

        assert 2 == len(self.hass.states.entity_ids())

    def test_update_state_adds_entities_with_update_befor_add_true(self):
        """Test if call update before add to state machine."""
        component = EntityComponent(_LOGGER, DOMAIN, self.hass)

        ent = EntityTest()
        ent.update = Mock(spec_set=True)

        component.add_entities([ent], True)
        self.hass.block_till_done()

        assert 1 == len(self.hass.states.entity_ids())
        assert ent.update.called

    def test_update_state_adds_entities_with_update_befor_add_false(self):
        """Test if not call update before add to state machine."""
        component = EntityComponent(_LOGGER, DOMAIN, self.hass)

        ent = EntityTest()
        ent.update = Mock(spec_set=True)

        component.add_entities([ent], False)
        self.hass.block_till_done()

        assert 1 == len(self.hass.states.entity_ids())
        assert not ent.update.called

    def test_not_adding_duplicate_entities(self):
        """Test for not adding duplicate entities."""
        component = EntityComponent(_LOGGER, DOMAIN, self.hass)

        assert 0 == len(self.hass.states.entity_ids())

        component.add_entities([EntityTest(unique_id='not_very_unique')])

        assert 1 == len(self.hass.states.entity_ids())

        component.add_entities([EntityTest(unique_id='not_very_unique')])

        assert 1 == len(self.hass.states.entity_ids())

    def test_not_assigning_entity_id_if_prescribes_one(self):
        """Test for not assigning an entity ID."""
        component = EntityComponent(_LOGGER, DOMAIN, self.hass)

        assert 'hello.world' not in self.hass.states.entity_ids()

        component.add_entities([EntityTest(entity_id='hello.world')])

        assert 'hello.world' in self.hass.states.entity_ids()

    def test_extract_from_service_returns_all_if_no_entity_id(self):
        """Test the extraction of everything from service."""
        component = EntityComponent(_LOGGER, DOMAIN, self.hass)
        component.add_entities([
            EntityTest(name='test_1'),
            EntityTest(name='test_2'),
        ])

        call = ha.ServiceCall('test', 'service')

        assert ['test_domain.test_1', 'test_domain.test_2'] == \
            sorted(ent.entity_id for ent in
                   component.extract_from_service(call))

    def test_extract_from_service_filter_out_non_existing_entities(self):
        """Test the extraction of non existing entities from service."""
        component = EntityComponent(_LOGGER, DOMAIN, self.hass)
        component.add_entities([
            EntityTest(name='test_1'),
            EntityTest(name='test_2'),
        ])

        call = ha.ServiceCall('test', 'service', {
            'entity_id': ['test_domain.test_2', 'test_domain.non_exist']
        })

        assert ['test_domain.test_2'] == \
               [ent.entity_id for ent in component.extract_from_service(call)]

    def test_extract_from_service_no_group_expand(self):
        """Test not expanding a group."""
        component = EntityComponent(_LOGGER, DOMAIN, self.hass)
        test_group = group.Group.create_group(
            self.hass, 'test_group', ['light.Ceiling', 'light.Kitchen'])
        component.add_entities([test_group])

        call = ha.ServiceCall('test', 'service', {
            'entity_id': ['group.test_group']
        })

        extracted = component.extract_from_service(call, expand_group=False)
        self.assertEqual([test_group], extracted)

    def test_setup_loads_platforms(self):
        """Test the loading of the platforms."""
        component_setup = Mock(return_value=True)
        platform_setup = Mock(return_value=None)
        loader.set_component(
            'test_component',
            MockModule('test_component', setup=component_setup))
        loader.set_component('test_domain.mod2',
                             MockPlatform(platform_setup, ['test_component']))

        component = EntityComponent(_LOGGER, DOMAIN, self.hass)

        assert not component_setup.called
        assert not platform_setup.called

        component.setup({
            DOMAIN: {
                'platform': 'mod2',
            }
        })

        self.hass.block_till_done()
        assert component_setup.called
        assert platform_setup.called

    def test_setup_recovers_when_setup_raises(self):
        """Test the setup if exceptions are happening."""
        platform1_setup = Mock(side_effect=Exception('Broken'))
        platform2_setup = Mock(return_value=None)

        loader.set_component('test_domain.mod1', MockPlatform(platform1_setup))
        loader.set_component('test_domain.mod2', MockPlatform(platform2_setup))

        component = EntityComponent(_LOGGER, DOMAIN, self.hass)

        assert not platform1_setup.called
        assert not platform2_setup.called

        component.setup(OrderedDict([
            (DOMAIN, {'platform': 'mod1'}),
            ("{} 2".format(DOMAIN), {'platform': 'non_exist'}),
            ("{} 3".format(DOMAIN), {'platform': 'mod2'}),
        ]))

        self.hass.block_till_done()
        assert platform1_setup.called
        assert platform2_setup.called

    @patch('homeassistant.helpers.entity_component.EntityComponent'
           '._async_setup_platform', return_value=mock_coro())
    @patch('homeassistant.setup.async_setup_component',
           return_value=mock_coro(True))
    def test_setup_does_discovery(self, mock_setup_component, mock_setup):
        """Test setup for discovery."""
        component = EntityComponent(_LOGGER, DOMAIN, self.hass)

        component.setup({})

        discovery.load_platform(self.hass, DOMAIN, 'platform_test',
                                {'msg': 'discovery_info'})

        self.hass.block_till_done()

        assert mock_setup.called
        assert ('platform_test', {}, {'msg': 'discovery_info'}) == \
            mock_setup.call_args[0]

    @patch('homeassistant.helpers.entity_component.'
           'async_track_time_interval')
    def test_set_scan_interval_via_config(self, mock_track):
        """Test the setting of the scan interval via configuration."""
        def platform_setup(hass, config, add_devices, discovery_info=None):
            """Test the platform setup."""
            add_devices([EntityTest(should_poll=True)])

        loader.set_component('test_domain.platform',
                             MockPlatform(platform_setup))

        component = EntityComponent(_LOGGER, DOMAIN, self.hass)

        component.setup({
            DOMAIN: {
                'platform': 'platform',
                'scan_interval': timedelta(seconds=30),
            }
        })

        self.hass.block_till_done()
        assert mock_track.called
        assert timedelta(seconds=30) == mock_track.call_args[0][2]

    @patch('homeassistant.helpers.entity_component.'
           'async_track_time_interval')
    def test_set_scan_interval_via_platform(self, mock_track):
        """Test the setting of the scan interval via platform."""
        def platform_setup(hass, config, add_devices, discovery_info=None):
            """Test the platform setup."""
            add_devices([EntityTest(should_poll=True)])

        platform = MockPlatform(platform_setup)
        platform.SCAN_INTERVAL = timedelta(seconds=30)

        loader.set_component('test_domain.platform', platform)

        component = EntityComponent(_LOGGER, DOMAIN, self.hass)

        component.setup({
            DOMAIN: {
                'platform': 'platform',
            }
        })

        self.hass.block_till_done()
        assert mock_track.called
        assert timedelta(seconds=30) == mock_track.call_args[0][2]

    def test_set_entity_namespace_via_config(self):
        """Test setting an entity namespace."""
        def platform_setup(hass, config, add_devices, discovery_info=None):
            """Test the platform setup."""
            add_devices([
                EntityTest(name='beer'),
                EntityTest(name=None),
            ])

        platform = MockPlatform(platform_setup)

        loader.set_component('test_domain.platform', platform)

        component = EntityComponent(_LOGGER, DOMAIN, self.hass)

        component.setup({
            DOMAIN: {
                'platform': 'platform',
                'entity_namespace': 'yummy'
            }
        })

        self.hass.block_till_done()

        assert sorted(self.hass.states.entity_ids()) == \
            ['test_domain.yummy_beer', 'test_domain.yummy_unnamed_device']

    def test_adding_entities_with_generator_and_thread_callback(self):
        """Test generator in add_entities that calls thread method.

        We should make sure we resolve the generator to a list before passing
        it into an async context.
        """
        component = EntityComponent(_LOGGER, DOMAIN, self.hass)

        def create_entity(number):
            """Create entity helper."""
            entity = EntityTest()
            entity.entity_id = generate_entity_id(component.entity_id_format,
                                                  'Number', hass=self.hass)
            return entity

        component.add_entities(create_entity(i) for i in range(2))


@asyncio.coroutine
def test_platform_warn_slow_setup(hass):
    """Warn we log when platform setup takes a long time."""
    platform = MockPlatform()

    loader.set_component('test_domain.platform', platform)

    component = EntityComponent(_LOGGER, DOMAIN, hass)

    with patch.object(hass.loop, 'call_later', MagicMock()) \
            as mock_call:
        yield from component.async_setup({
            DOMAIN: {
                'platform': 'platform',
            }
        })
        assert mock_call.called

        timeout, logger_method = mock_call.mock_calls[0][1][:2]

        assert timeout == SLOW_SETUP_WARNING
        assert logger_method == _LOGGER.warning

        assert mock_call().cancel.called


@asyncio.coroutine
def test_platform_error_slow_setup(hass, caplog):
    """Don't block startup more than SLOW_SETUP_MAX_WAIT."""
    with patch.object(entity_component, 'SLOW_SETUP_MAX_WAIT', 0):
        called = []

        @asyncio.coroutine
        def setup_platform(*args):
            called.append(1)
            yield from asyncio.sleep(1, loop=hass.loop)

        platform = MockPlatform(async_setup_platform=setup_platform)
        component = EntityComponent(_LOGGER, DOMAIN, hass)
        loader.set_component('test_domain.test_platform', platform)
        yield from component.async_setup({
            DOMAIN: {
                'platform': 'test_platform',
            }
        })
        assert len(called) == 1
        assert 'test_domain.test_platform' not in hass.config.components
        assert 'test_platform is taking longer than 0 seconds' in caplog.text


@asyncio.coroutine
def test_extract_from_service_available_device(hass):
    """Test the extraction of entity from service and device is available."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)
    yield from component.async_add_entities([
        EntityTest(name='test_1'),
        EntityTest(name='test_2', available=False),
        EntityTest(name='test_3'),
        EntityTest(name='test_4', available=False),
    ])

    call_1 = ha.ServiceCall('test', 'service')

    assert ['test_domain.test_1', 'test_domain.test_3'] == \
        sorted(ent.entity_id for ent in
               component.async_extract_from_service(call_1))

    call_2 = ha.ServiceCall('test', 'service', data={
        'entity_id': ['test_domain.test_3', 'test_domain.test_4'],
    })

    assert ['test_domain.test_3'] == \
        sorted(ent.entity_id for ent in
               component.async_extract_from_service(call_2))


@asyncio.coroutine
def test_updated_state_used_for_entity_id(hass):
    """Test that first update results used for entity ID generation."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)

    class EntityTestNameFetcher(EntityTest):
        """Mock entity that fetches a friendly name."""

        @asyncio.coroutine
        def async_update(self):
            """Mock update that assigns a name."""
            self._values['name'] = "Living Room"

    yield from component.async_add_entities([EntityTestNameFetcher()], True)

    entity_ids = hass.states.async_entity_ids()
    assert 1 == len(entity_ids)
    assert entity_ids[0] == "test_domain.living_room"


@asyncio.coroutine
def test_platform_not_ready(hass):
    """Test that we retry when platform not ready."""
    platform1_setup = Mock(side_effect=[PlatformNotReady, PlatformNotReady,
                                        None])
    loader.set_component('test_domain.mod1', MockPlatform(platform1_setup))

    component = EntityComponent(_LOGGER, DOMAIN, hass)

    yield from component.async_setup({
        DOMAIN: {
            'platform': 'mod1'
        }
    })

    assert len(platform1_setup.mock_calls) == 1
    assert 'test_domain.mod1' not in hass.config.components

    utcnow = dt_util.utcnow()

    with patch('homeassistant.util.dt.utcnow', return_value=utcnow):
        # Should not trigger attempt 2
        async_fire_time_changed(hass, utcnow + timedelta(seconds=29))
        yield from hass.async_block_till_done()
        assert len(platform1_setup.mock_calls) == 1

        # Should trigger attempt 2
        async_fire_time_changed(hass, utcnow + timedelta(seconds=30))
        yield from hass.async_block_till_done()
        assert len(platform1_setup.mock_calls) == 2
        assert 'test_domain.mod1' not in hass.config.components

        # This should not trigger attempt 3
        async_fire_time_changed(hass, utcnow + timedelta(seconds=59))
        yield from hass.async_block_till_done()
        assert len(platform1_setup.mock_calls) == 2

        # Trigger attempt 3, which succeeds
        async_fire_time_changed(hass, utcnow + timedelta(seconds=60))
        yield from hass.async_block_till_done()
        assert len(platform1_setup.mock_calls) == 3
        assert 'test_domain.mod1' in hass.config.components


@asyncio.coroutine
def test_pararell_updates_async_platform(hass):
    """Warn we log when platform setup takes a long time."""
    platform = MockPlatform()

    @asyncio.coroutine
    def mock_update(*args, **kwargs):
        pass

    platform.async_setup_platform = mock_update

    loader.set_component('test_domain.platform', platform)

    component = EntityComponent(_LOGGER, DOMAIN, hass)
    component._platforms = {}

    yield from component.async_setup({
        DOMAIN: {
            'platform': 'platform',
        }
    })

    handle = list(component._platforms.values())[-1]

    assert handle.parallel_updates is None


@asyncio.coroutine
def test_pararell_updates_async_platform_with_constant(hass):
    """Warn we log when platform setup takes a long time."""
    platform = MockPlatform()

    @asyncio.coroutine
    def mock_update(*args, **kwargs):
        pass

    platform.async_setup_platform = mock_update
    platform.PARALLEL_UPDATES = 1

    loader.set_component('test_domain.platform', platform)

    component = EntityComponent(_LOGGER, DOMAIN, hass)
    component._platforms = {}

    yield from component.async_setup({
        DOMAIN: {
            'platform': 'platform',
        }
    })

    handle = list(component._platforms.values())[-1]

    assert handle.parallel_updates is not None


@asyncio.coroutine
def test_pararell_updates_sync_platform(hass):
    """Warn we log when platform setup takes a long time."""
    platform = MockPlatform()

    loader.set_component('test_domain.platform', platform)

    component = EntityComponent(_LOGGER, DOMAIN, hass)
    component._platforms = {}

    yield from component.async_setup({
        DOMAIN: {
            'platform': 'platform',
        }
    })

    handle = list(component._platforms.values())[-1]

    assert handle.parallel_updates is not None


@asyncio.coroutine
def test_raise_error_on_update(hass):
    """Test the add entity if they raise an error on update."""
    updates = []
    component = EntityComponent(_LOGGER, DOMAIN, hass)
    entity1 = EntityTest(name='test_1')
    entity2 = EntityTest(name='test_2')

    def _raise():
        """Helper to raise a exception."""
        raise AssertionError

    entity1.update = _raise
    entity2.update = lambda: updates.append(1)

    yield from component.async_add_entities([entity1, entity2], True)

    assert len(updates) == 1
    assert 1 in updates


@asyncio.coroutine
def test_async_remove_with_platform(hass):
    """Remove an entity from a platform."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)
    entity1 = EntityTest(name='test_1')
    yield from component.async_add_entities([entity1])
    assert len(hass.states.async_entity_ids()) == 1
    yield from entity1.async_remove()
    assert len(hass.states.async_entity_ids()) == 0
