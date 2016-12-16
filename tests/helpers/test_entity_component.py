"""The tests for the Entity component helper."""
# pylint: disable=protected-access
import asyncio
from collections import OrderedDict
import logging
import unittest
from unittest.mock import patch, Mock

import homeassistant.core as ha
import homeassistant.loader as loader
from homeassistant.components import group
from homeassistant.helpers.entity import Entity, generate_entity_id
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers import discovery
import homeassistant.util.dt as dt_util

from tests.common import (
    get_test_home_assistant, MockPlatform, MockModule, fire_time_changed,
    mock_coro)

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
        component = EntityComponent(_LOGGER, DOMAIN, self.hass,
                                    group_name='everyone')

        # No group after setup
        assert len(self.hass.states.entity_ids()) == 0

        component.add_entities([EntityTest(name='hello')])

        # group exists
        assert len(self.hass.states.entity_ids()) == 2
        assert self.hass.states.entity_ids('group') == ['group.everyone']

        group = self.hass.states.get('group.everyone')

        assert group.attributes.get('entity_id') == ('test_domain.hello',)

        # group extended
        component.add_entities([EntityTest(name='hello2')])

        assert len(self.hass.states.entity_ids()) == 3
        group = self.hass.states.get('group.everyone')

        assert sorted(group.attributes.get('entity_id')) == \
            ['test_domain.hello', 'test_domain.hello2']

    def test_polling_only_updates_entities_it_should_poll(self):
        """Test the polling of only updated entities."""
        component = EntityComponent(_LOGGER, DOMAIN, self.hass, 20)

        no_poll_ent = EntityTest(should_poll=False)
        no_poll_ent.async_update = Mock()
        poll_ent = EntityTest(should_poll=True)
        poll_ent.async_update = Mock()

        component.add_entities([no_poll_ent, poll_ent])

        no_poll_ent.async_update.reset_mock()
        poll_ent.async_update.reset_mock()

        fire_time_changed(self.hass, dt_util.utcnow().replace(second=0))
        self.hass.block_till_done()

        assert not no_poll_ent.async_update.called
        assert poll_ent.async_update.called

    def test_update_state_adds_entities(self):
        """Test if updating poll entities cause an entity to be added works."""
        component = EntityComponent(_LOGGER, DOMAIN, self.hass)

        ent1 = EntityTest()
        ent2 = EntityTest(should_poll=True)

        component.add_entities([ent2])
        assert 1 == len(self.hass.states.entity_ids())
        ent2.update = lambda *_: component.add_entities([ent1])

        fire_time_changed(self.hass, dt_util.utcnow().replace(second=0))
        self.hass.block_till_done()

        assert 2 == len(self.hass.states.entity_ids())

    def test_update_state_adds_entities_with_update_befor_add_true(self):
        """Test if call update befor add to state machine."""
        component = EntityComponent(_LOGGER, DOMAIN, self.hass)

        ent = EntityTest()
        ent.update = Mock(spec_set=True)

        component.add_entities([ent], True)
        self.hass.block_till_done()

        assert 1 == len(self.hass.states.entity_ids())
        assert ent.update.called

    def test_update_state_adds_entities_with_update_befor_add_false(self):
        """Test if not call update befor add to state machine."""
        component = EntityComponent(_LOGGER, DOMAIN, self.hass)

        ent = EntityTest()
        ent.update = Mock(spec_set=True)

        component.add_entities([ent], False)
        self.hass.block_till_done()

        assert 1 == len(self.hass.states.entity_ids())
        assert not ent.update.called

    def test_adds_entities_with_update_befor_add_true_deadlock_protect(self):
        """Test if call update befor add to state machine.

        It need to run update inside executor and never call
        async_add_entities with True
        """
        call = []
        component = EntityComponent(_LOGGER, DOMAIN, self.hass)

        @asyncio.coroutine
        def async_add_entities_fake(entities, update_befor_add):
            """Fake add_entities_call."""
            call.append(update_befor_add)
        component._platforms['core'].async_add_entities = \
            async_add_entities_fake

        ent = EntityTest()
        ent.update = Mock(spec_set=True)
        component.add_entities([ent], True)

        assert ent.update.called
        assert len(call) == 1
        assert not call[0]

    def test_not_adding_duplicate_entities(self):
        """Test for not adding duplicate entities."""
        component = EntityComponent(_LOGGER, DOMAIN, self.hass)

        assert 0 == len(self.hass.states.entity_ids())

        component.add_entities([None, EntityTest(unique_id='not_very_unique')])

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

        assert platform1_setup.called
        assert platform2_setup.called

    @patch('homeassistant.helpers.entity_component.EntityComponent'
           '._async_setup_platform', return_value=mock_coro()())
    @patch('homeassistant.bootstrap.async_setup_component',
           return_value=mock_coro(True)())
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
           'async_track_utc_time_change')
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
                'scan_interval': 30,
            }
        })

        assert mock_track.called
        assert [0, 30] == list(mock_track.call_args[1]['second'])

    @patch('homeassistant.helpers.entity_component.'
           'async_track_utc_time_change')
    def test_set_scan_interval_via_platform(self, mock_track):
        """Test the setting of the scan interval via platform."""
        def platform_setup(hass, config, add_devices, discovery_info=None):
            """Test the platform setup."""
            add_devices([EntityTest(should_poll=True)])

        platform = MockPlatform(platform_setup)
        platform.SCAN_INTERVAL = 30

        loader.set_component('test_domain.platform', platform)

        component = EntityComponent(_LOGGER, DOMAIN, self.hass)

        component.setup({
            DOMAIN: {
                'platform': 'platform',
            }
        })

        assert mock_track.called
        assert [0, 30] == list(mock_track.call_args[1]['second'])

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
