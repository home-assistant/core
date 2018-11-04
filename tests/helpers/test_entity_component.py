"""The tests for the Entity component helper."""
# pylint: disable=protected-access
import asyncio
from collections import OrderedDict
import logging
import unittest
from unittest.mock import patch, Mock
from datetime import timedelta

import pytest

import homeassistant.core as ha
import homeassistant.loader as loader
from homeassistant.exceptions import PlatformNotReady
from homeassistant.components import group
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.setup import setup_component, async_setup_component

from homeassistant.helpers import discovery
import homeassistant.util.dt as dt_util

from tests.common import (
    get_test_home_assistant, MockPlatform, MockModule, mock_coro,
    async_fire_time_changed, MockEntity, MockConfigEntry)

_LOGGER = logging.getLogger(__name__)
DOMAIN = "test_domain"


class TestHelpersEntityComponent(unittest.TestCase):
    """Test homeassistant.helpers.entity_component module."""

    def setUp(self):  # pylint: disable=invalid-name
        """Initialize a test Home Assistant instance."""
        self.hass = get_test_home_assistant()

    def tearDown(self):  # pylint: disable=invalid-name
        """Clean up the test Home Assistant instance."""
        self.hass.stop()

    def test_setting_up_group(self):
        """Set up the setting of a group."""
        setup_component(self.hass, 'group', {'group': {}})
        component = EntityComponent(_LOGGER, DOMAIN, self.hass,
                                    group_name='everyone')

        # No group after setup
        assert len(self.hass.states.entity_ids()) == 0

        component.add_entities([MockEntity()])
        self.hass.block_till_done()

        # group exists
        assert len(self.hass.states.entity_ids()) == 2
        assert self.hass.states.entity_ids('group') == ['group.everyone']

        group = self.hass.states.get('group.everyone')

        assert group.attributes.get('entity_id') == \
            ('test_domain.unnamed_device',)

        # group extended
        component.add_entities([MockEntity(name='goodbye')])
        self.hass.block_till_done()

        assert len(self.hass.states.entity_ids()) == 3
        group = self.hass.states.get('group.everyone')

        # Ordered in order of added to the group
        assert group.attributes.get('entity_id') == \
            ('test_domain.goodbye', 'test_domain.unnamed_device')

    def test_setup_loads_platforms(self):
        """Test the loading of the platforms."""
        component_setup = Mock(return_value=True)
        platform_setup = Mock(return_value=None)
        loader.set_component(
            self.hass, 'test_component',
            MockModule('test_component', setup=component_setup))
        loader.set_component(self.hass, 'test_domain.mod2',
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

        loader.set_component(self.hass, 'test_domain.mod1',
                             MockPlatform(platform1_setup))
        loader.set_component(self.hass, 'test_domain.mod2',
                             MockPlatform(platform2_setup))

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
                                {'msg': 'discovery_info'}, {DOMAIN: {}})

        self.hass.block_till_done()

        assert mock_setup.called
        assert ('platform_test', {}, {'msg': 'discovery_info'}) == \
            mock_setup.call_args[0]

    @patch('homeassistant.helpers.entity_platform.'
           'async_track_time_interval')
    def test_set_scan_interval_via_config(self, mock_track):
        """Test the setting of the scan interval via configuration."""
        def platform_setup(hass, config, add_entities, discovery_info=None):
            """Test the platform setup."""
            add_entities([MockEntity(should_poll=True)])

        loader.set_component(self.hass, 'test_domain.platform',
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

    def test_set_entity_namespace_via_config(self):
        """Test setting an entity namespace."""
        def platform_setup(hass, config, add_entities, discovery_info=None):
            """Test the platform setup."""
            add_entities([
                MockEntity(name='beer'),
                MockEntity(name=None),
            ])

        platform = MockPlatform(platform_setup)

        loader.set_component(self.hass, 'test_domain.platform', platform)

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


@asyncio.coroutine
def test_extract_from_service_available_device(hass):
    """Test the extraction of entity from service and device is available."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)
    yield from component.async_add_entities([
        MockEntity(name='test_1'),
        MockEntity(name='test_2', available=False),
        MockEntity(name='test_3'),
        MockEntity(name='test_4', available=False),
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
def test_platform_not_ready(hass):
    """Test that we retry when platform not ready."""
    platform1_setup = Mock(side_effect=[PlatformNotReady, PlatformNotReady,
                                        None])
    loader.set_component(hass, 'test_domain.mod1',
                         MockPlatform(platform1_setup))

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
def test_extract_from_service_returns_all_if_no_entity_id(hass):
    """Test the extraction of everything from service."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)
    yield from component.async_add_entities([
        MockEntity(name='test_1'),
        MockEntity(name='test_2'),
    ])

    call = ha.ServiceCall('test', 'service')

    assert ['test_domain.test_1', 'test_domain.test_2'] == \
        sorted(ent.entity_id for ent in
               component.async_extract_from_service(call))


@asyncio.coroutine
def test_extract_from_service_filter_out_non_existing_entities(hass):
    """Test the extraction of non existing entities from service."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)
    yield from component.async_add_entities([
        MockEntity(name='test_1'),
        MockEntity(name='test_2'),
    ])

    call = ha.ServiceCall('test', 'service', {
        'entity_id': ['test_domain.test_2', 'test_domain.non_exist']
    })

    assert ['test_domain.test_2'] == \
           [ent.entity_id for ent
            in component.async_extract_from_service(call)]


@asyncio.coroutine
def test_extract_from_service_no_group_expand(hass):
    """Test not expanding a group."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)
    test_group = yield from group.Group.async_create_group(
        hass, 'test_group', ['light.Ceiling', 'light.Kitchen'])
    yield from component.async_add_entities([test_group])

    call = ha.ServiceCall('test', 'service', {
        'entity_id': ['group.test_group']
    })

    extracted = component.async_extract_from_service(call, expand_group=False)
    assert extracted == [test_group]


@asyncio.coroutine
def test_setup_dependencies_platform(hass):
    """Test we setup the dependencies of a platform.

    We're explictely testing that we process dependencies even if a component
    with the same name has already been loaded.
    """
    loader.set_component(hass, 'test_component', MockModule('test_component'))
    loader.set_component(hass, 'test_component2',
                         MockModule('test_component2'))
    loader.set_component(
        hass, 'test_domain.test_component',
        MockPlatform(dependencies=['test_component', 'test_component2']))

    component = EntityComponent(_LOGGER, DOMAIN, hass)

    yield from async_setup_component(hass, 'test_component', {})

    yield from component.async_setup({
        DOMAIN: {
            'platform': 'test_component',
        }
    })

    assert 'test_component' in hass.config.components
    assert 'test_component2' in hass.config.components
    assert 'test_domain.test_component' in hass.config.components


async def test_setup_entry(hass):
    """Test setup entry calls async_setup_entry on platform."""
    mock_setup_entry = Mock(return_value=mock_coro(True))
    loader.set_component(
        hass, 'test_domain.entry_domain',
        MockPlatform(async_setup_entry=mock_setup_entry,
                     scan_interval=timedelta(seconds=5)))

    component = EntityComponent(_LOGGER, DOMAIN, hass)
    entry = MockConfigEntry(domain='entry_domain')

    assert await component.async_setup_entry(entry)
    assert len(mock_setup_entry.mock_calls) == 1
    p_hass, p_entry, p_add_entities = mock_setup_entry.mock_calls[0][1]
    assert p_hass is hass
    assert p_entry is entry

    assert component._platforms[entry.entry_id].scan_interval == \
        timedelta(seconds=5)


async def test_setup_entry_platform_not_exist(hass):
    """Test setup entry fails if platform doesnt exist."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)
    entry = MockConfigEntry(domain='non_existing')

    assert (await component.async_setup_entry(entry)) is False


async def test_setup_entry_fails_duplicate(hass):
    """Test we don't allow setting up a config entry twice."""
    mock_setup_entry = Mock(return_value=mock_coro(True))
    loader.set_component(
        hass, 'test_domain.entry_domain',
        MockPlatform(async_setup_entry=mock_setup_entry))

    component = EntityComponent(_LOGGER, DOMAIN, hass)
    entry = MockConfigEntry(domain='entry_domain')

    assert await component.async_setup_entry(entry)

    with pytest.raises(ValueError):
        await component.async_setup_entry(entry)


async def test_unload_entry_resets_platform(hass):
    """Test unloading an entry removes all entities."""
    mock_setup_entry = Mock(return_value=mock_coro(True))
    loader.set_component(
        hass, 'test_domain.entry_domain',
        MockPlatform(async_setup_entry=mock_setup_entry))

    component = EntityComponent(_LOGGER, DOMAIN, hass)
    entry = MockConfigEntry(domain='entry_domain')

    assert await component.async_setup_entry(entry)
    assert len(mock_setup_entry.mock_calls) == 1
    add_entities = mock_setup_entry.mock_calls[0][1][2]
    add_entities([MockEntity()])
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids()) == 1

    assert await component.async_unload_entry(entry)
    assert len(hass.states.async_entity_ids()) == 0


async def test_unload_entry_fails_if_never_loaded(hass):
    """."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)
    entry = MockConfigEntry(domain='entry_domain')

    with pytest.raises(ValueError):
        await component.async_unload_entry(entry)


async def test_update_entity(hass):
    """Test that we can update an entity with the helper."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)
    entity = MockEntity()
    entity.async_update_ha_state = Mock(return_value=mock_coro())
    await component.async_add_entities([entity])

    # Called as part of async_add_entities
    assert len(entity.async_update_ha_state.mock_calls) == 1

    await hass.helpers.entity_component.async_update_entity(entity.entity_id)

    assert len(entity.async_update_ha_state.mock_calls) == 2
    assert entity.async_update_ha_state.mock_calls[-1][1][0] is True
