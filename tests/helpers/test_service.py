"""Test service helpers."""
import asyncio
from collections import OrderedDict
from copy import deepcopy
import unittest
from unittest.mock import Mock, patch

import voluptuous as vol
import pytest

# To prevent circular import when running just this file
import homeassistant.components  # noqa
from homeassistant import core as ha, loader, exceptions
from homeassistant.const import STATE_ON, STATE_OFF, ATTR_ENTITY_ID
from homeassistant.setup import async_setup_component
import homeassistant.helpers.config_validation as cv
from homeassistant.auth.permissions import PolicyPermissions
from homeassistant.helpers import (
    service, template, device_registry as dev_reg, entity_registry as ent_reg)
from tests.common import (
    get_test_home_assistant, mock_service, mock_coro, mock_registry,
    mock_device_registry)


@pytest.fixture
def mock_service_platform_call():
    """Mock service platform call."""
    with patch('homeassistant.helpers.service._handle_service_platform_call',
               side_effect=lambda *args: mock_coro()) as mock_call:
        yield mock_call


@pytest.fixture
def mock_entities():
    """Return mock entities in an ordered dict."""
    kitchen = Mock(
        entity_id='light.kitchen',
        available=True,
        should_poll=False,
    )
    living_room = Mock(
        entity_id='light.living_room',
        available=True,
        should_poll=False,
    )
    entities = OrderedDict()
    entities[kitchen.entity_id] = kitchen
    entities[living_room.entity_id] = living_room
    return entities


class TestServiceHelpers(unittest.TestCase):
    """Test the Home Assistant service helpers."""

    def setUp(self):     # pylint: disable=invalid-name
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.calls = mock_service(self.hass, 'test_domain', 'test_service')

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop down everything that was started."""
        self.hass.stop()

    def test_template_service_call(self):
        """Test service call with templating."""
        config = {
            'service_template': '{{ \'test_domain.test_service\' }}',
            'entity_id': 'hello.world',
            'data_template': {
                'hello': '{{ \'goodbye\' }}',
                'data': {
                    'value': '{{ \'complex\' }}',
                    'simple': 'simple'
                },
                'list': ['{{ \'list\' }}', '2'],
            },
        }

        service.call_from_config(self.hass, config)
        self.hass.block_till_done()

        assert 'goodbye' == self.calls[0].data['hello']
        assert 'complex' == self.calls[0].data['data']['value']
        assert 'simple' == self.calls[0].data['data']['simple']
        assert 'list' == self.calls[0].data['list'][0]

    def test_passing_variables_to_templates(self):
        """Test passing variables to templates."""
        config = {
            'service_template': '{{ var_service }}',
            'entity_id': 'hello.world',
            'data_template': {
                'hello': '{{ var_data }}',
            },
        }

        service.call_from_config(self.hass, config, variables={
            'var_service': 'test_domain.test_service',
            'var_data': 'goodbye',
        })
        self.hass.block_till_done()

        assert 'goodbye' == self.calls[0].data['hello']

    def test_bad_template(self):
        """Test passing bad template."""
        config = {
            'service_template': '{{ var_service }}',
            'entity_id': 'hello.world',
            'data_template': {
                'hello': '{{ states + unknown_var }}'
            }
        }

        service.call_from_config(self.hass, config, variables={
            'var_service': 'test_domain.test_service',
            'var_data': 'goodbye',
        })
        self.hass.block_till_done()

        assert len(self.calls) == 0

    def test_split_entity_string(self):
        """Test splitting of entity string."""
        service.call_from_config(self.hass, {
            'service': 'test_domain.test_service',
            'entity_id': 'hello.world, sensor.beer'
        })
        self.hass.block_till_done()
        assert ['hello.world', 'sensor.beer'] == \
            self.calls[-1].data.get('entity_id')

    def test_not_mutate_input(self):
        """Test for immutable input."""
        config = cv.SERVICE_SCHEMA({
            'service': 'test_domain.test_service',
            'entity_id': 'hello.world, sensor.beer',
            'data': {
                'hello': 1,
            },
            'data_template': {
                'nested': {
                    'value': '{{ 1 + 1 }}'
                }
            }
        })
        orig = deepcopy(config)

        # Only change after call is each template getting hass attached
        template.attach(self.hass, orig)

        service.call_from_config(self.hass, config, validate_config=False)
        assert orig == config

    @patch('homeassistant.helpers.service._LOGGER.error')
    def test_fail_silently_if_no_service(self, mock_log):
        """Test failing if service is missing."""
        service.call_from_config(self.hass, None)
        assert 1 == mock_log.call_count

        service.call_from_config(self.hass, {})
        assert 2 == mock_log.call_count

        service.call_from_config(self.hass, {
            'service': 'invalid'
        })
        assert 3 == mock_log.call_count


async def test_extract_entity_ids(hass):
    """Test extract_entity_ids method."""
    hass.states.async_set('light.Bowl', STATE_ON)
    hass.states.async_set('light.Ceiling', STATE_OFF)
    hass.states.async_set('light.Kitchen', STATE_OFF)

    await loader.get_component(hass, 'group').Group.async_create_group(
        hass, 'test', ['light.Ceiling', 'light.Kitchen'])

    call = ha.ServiceCall('light', 'turn_on',
                          {ATTR_ENTITY_ID: 'light.Bowl'})

    assert {'light.bowl'} == \
        await service.async_extract_entity_ids(hass, call)

    call = ha.ServiceCall('light', 'turn_on',
                          {ATTR_ENTITY_ID: 'group.test'})

    assert {'light.ceiling', 'light.kitchen'} == \
        await service.async_extract_entity_ids(hass, call)

    assert {'group.test'} == await service.async_extract_entity_ids(
        hass, call, expand_group=False)


async def test_extract_entity_ids_from_area(hass):
    """Test extract_entity_ids method with areas."""
    hass.states.async_set('light.Bowl', STATE_ON)
    hass.states.async_set('light.Ceiling', STATE_OFF)
    hass.states.async_set('light.Kitchen', STATE_OFF)

    device_in_area = dev_reg.DeviceEntry(area_id='test-area')
    device_no_area = dev_reg.DeviceEntry()
    device_diff_area = dev_reg.DeviceEntry(area_id='diff-area')

    mock_device_registry(hass, {
        device_in_area.id: device_in_area,
        device_no_area.id: device_no_area,
        device_diff_area.id: device_diff_area,
    })

    entity_in_area = ent_reg.RegistryEntry(
        entity_id='light.in_area',
        unique_id='in-area-id',
        platform='test',
        device_id=device_in_area.id,
    )
    entity_no_area = ent_reg.RegistryEntry(
        entity_id='light.no_area',
        unique_id='no-area-id',
        platform='test',
        device_id=device_no_area.id,
    )
    entity_diff_area = ent_reg.RegistryEntry(
        entity_id='light.diff_area',
        unique_id='diff-area-id',
        platform='test',
        device_id=device_diff_area.id,
    )
    mock_registry(hass, {
        entity_in_area.entity_id: entity_in_area,
        entity_no_area.entity_id: entity_no_area,
        entity_diff_area.entity_id: entity_diff_area,
    })

    call = ha.ServiceCall('light', 'turn_on',
                          {'area_id': 'test-area'})

    assert {'light.in_area'} == \
        await service.async_extract_entity_ids(hass, call)

    call = ha.ServiceCall('light', 'turn_on',
                          {'area_id': ['test-area', 'diff-area']})

    assert {'light.in_area', 'light.diff_area'} == \
        await service.async_extract_entity_ids(hass, call)


@asyncio.coroutine
def test_async_get_all_descriptions(hass):
    """Test async_get_all_descriptions."""
    group = loader.get_component(hass, 'group')
    group_config = {group.DOMAIN: {}}
    yield from async_setup_component(hass, group.DOMAIN, group_config)
    descriptions = yield from service.async_get_all_descriptions(hass)

    assert len(descriptions) == 1

    assert 'description' in descriptions['group']['reload']
    assert 'fields' in descriptions['group']['reload']

    logger = loader.get_component(hass, 'logger')
    logger_config = {logger.DOMAIN: {}}
    yield from async_setup_component(hass, logger.DOMAIN, logger_config)
    descriptions = yield from service.async_get_all_descriptions(hass)

    assert len(descriptions) == 2

    assert 'description' in descriptions[logger.DOMAIN]['set_level']
    assert 'fields' in descriptions[logger.DOMAIN]['set_level']


async def test_call_context_user_not_exist(hass):
    """Check we don't allow deleted users to do things."""
    with pytest.raises(exceptions.UnknownUser) as err:
        await service.entity_service_call(hass, [], Mock(), ha.ServiceCall(
            'test_domain', 'test_service', context=ha.Context(
                user_id='non-existing')))

    assert err.value.context.user_id == 'non-existing'


async def test_call_context_target_all(hass, mock_service_platform_call,
                                       mock_entities):
    """Check we only target allowed entities if targetting all."""
    with patch('homeassistant.auth.AuthManager.async_get_user',
               return_value=mock_coro(Mock(permissions=PolicyPermissions({
                   'entities': {
                       'entity_ids': {
                           'light.kitchen': True
                       }
                   }
               }, None)))):
        await service.entity_service_call(hass, [
            Mock(entities=mock_entities)
        ], Mock(), ha.ServiceCall('test_domain', 'test_service',
                                  context=ha.Context(user_id='mock-id')))

    assert len(mock_service_platform_call.mock_calls) == 1
    entities = mock_service_platform_call.mock_calls[0][1][2]
    assert entities == [mock_entities['light.kitchen']]


async def test_call_context_target_specific(hass, mock_service_platform_call,
                                            mock_entities):
    """Check targeting specific entities."""
    with patch('homeassistant.auth.AuthManager.async_get_user',
               return_value=mock_coro(Mock(permissions=PolicyPermissions({
                   'entities': {
                       'entity_ids': {
                           'light.kitchen': True
                       }
                   }
               }, None)))):
        await service.entity_service_call(hass, [
            Mock(entities=mock_entities)
        ], Mock(), ha.ServiceCall('test_domain', 'test_service', {
            'entity_id': 'light.kitchen'
        }, context=ha.Context(user_id='mock-id')))

    assert len(mock_service_platform_call.mock_calls) == 1
    entities = mock_service_platform_call.mock_calls[0][1][2]
    assert entities == [mock_entities['light.kitchen']]


async def test_call_context_target_specific_no_auth(
        hass, mock_service_platform_call, mock_entities):
    """Check targeting specific entities without auth."""
    with pytest.raises(exceptions.Unauthorized) as err:
        with patch('homeassistant.auth.AuthManager.async_get_user',
                   return_value=mock_coro(Mock(
                       permissions=PolicyPermissions({}, None)))):
            await service.entity_service_call(hass, [
                Mock(entities=mock_entities)
            ], Mock(), ha.ServiceCall('test_domain', 'test_service', {
                'entity_id': 'light.kitchen'
            }, context=ha.Context(user_id='mock-id')))

    assert err.value.context.user_id == 'mock-id'
    assert err.value.entity_id == 'light.kitchen'


async def test_call_no_context_target_all(hass, mock_service_platform_call,
                                          mock_entities):
    """Check we target all if no user context given."""
    await service.entity_service_call(hass, [
        Mock(entities=mock_entities)
    ], Mock(), ha.ServiceCall('test_domain', 'test_service'))

    assert len(mock_service_platform_call.mock_calls) == 1
    entities = mock_service_platform_call.mock_calls[0][1][2]
    assert entities == list(mock_entities.values())


async def test_call_no_context_target_specific(
        hass, mock_service_platform_call, mock_entities):
    """Check we can target specified entities."""
    await service.entity_service_call(hass, [
        Mock(entities=mock_entities)
    ], Mock(), ha.ServiceCall('test_domain', 'test_service', {
        'entity_id': ['light.kitchen', 'light.non-existing']
    }))

    assert len(mock_service_platform_call.mock_calls) == 1
    entities = mock_service_platform_call.mock_calls[0][1][2]
    assert entities == [mock_entities['light.kitchen']]


async def test_call_with_match_all(hass, mock_service_platform_call,
                                   mock_entities, caplog):
    """Check we only target allowed entities if targetting all."""
    await service.entity_service_call(hass, [
        Mock(entities=mock_entities)
    ], Mock(), ha.ServiceCall('test_domain', 'test_service', {
        'entity_id': 'all'
    }))

    assert len(mock_service_platform_call.mock_calls) == 1
    entities = mock_service_platform_call.mock_calls[0][1][2]
    assert entities == [
        mock_entities['light.kitchen'], mock_entities['light.living_room']]
    assert ('Not passing an entity ID to a service to target '
            'all entities is deprecated') not in caplog.text


async def test_call_with_omit_entity_id(hass, mock_service_platform_call,
                                        mock_entities, caplog):
    """Check we only target allowed entities if targetting all."""
    await service.entity_service_call(hass, [
        Mock(entities=mock_entities)
    ], Mock(), ha.ServiceCall('test_domain', 'test_service'))

    assert len(mock_service_platform_call.mock_calls) == 1
    entities = mock_service_platform_call.mock_calls[0][1][2]
    assert entities == [
        mock_entities['light.kitchen'], mock_entities['light.living_room']]
    assert ('Not passing an entity ID to a service to target '
            'all entities is deprecated') in caplog.text


async def test_register_admin_service(hass, hass_read_only_user,
                                      hass_admin_user):
    """Test the register admin service."""
    calls = []

    async def mock_service(call):
        calls.append(call)

    hass.helpers.service.async_register_admin_service(
        'test', 'test', mock_service, vol.Schema({})
    )

    with pytest.raises(exceptions.UnknownUser):
        await hass.services.async_call(
            'test', 'test', {}, blocking=True, context=ha.Context(
                user_id='non-existing'
            ))
    assert len(calls) == 0

    with pytest.raises(exceptions.Unauthorized):
        await hass.services.async_call(
            'test', 'test', {}, blocking=True, context=ha.Context(
                user_id=hass_read_only_user.id
            ))
    assert len(calls) == 0

    await hass.services.async_call(
        'test', 'test', {}, blocking=True, context=ha.Context(
            user_id=hass_admin_user.id
        ))
    assert len(calls) == 1
    assert calls[0].context.user_id == hass_admin_user.id
