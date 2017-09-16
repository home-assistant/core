"""Test service helpers."""
import asyncio
from copy import deepcopy
import unittest
from unittest.mock import patch

import voluptuous as vol

# To prevent circular import when running just this file
import homeassistant.components  # noqa
from homeassistant import core as ha, loader
from homeassistant.const import (
    ATTR_ENTITY_ID, SERVICE_TURN_ON, STATE_OFF, STATE_ON)
from homeassistant.helpers import service, template
import homeassistant.helpers.config_validation as cv

from tests.common import (
    get_test_home_assistant, mock_service, async_mock_service)


class TestServiceHelpers(unittest.TestCase):
    """Test the Home Assistant service helpers."""

    def setUp(self):     # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.calls = mock_service(self.hass, 'test_domain', 'test_service')

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop down everything that was started."""
        self.hass.stop()

    def test_template_service_call(self):
        """Test service call with tempating."""
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

        self.assertEqual('goodbye', self.calls[0].data['hello'])
        self.assertEqual('complex', self.calls[0].data['data']['value'])
        self.assertEqual('simple', self.calls[0].data['data']['simple'])
        self.assertEqual('list', self.calls[0].data['list'][0])

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

        self.assertEqual('goodbye', self.calls[0].data['hello'])

    def test_split_entity_string(self):
        """Test splitting of entity string."""
        service.call_from_config(self.hass, {
            'service': 'test_domain.test_service',
            'entity_id': 'hello.world, sensor.beer'
        })
        self.hass.block_till_done()
        self.assertEqual(['hello.world', 'sensor.beer'],
                         self.calls[-1].data.get('entity_id'))

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
        """Test failling if service is missing."""
        service.call_from_config(self.hass, None)
        self.assertEqual(1, mock_log.call_count)

        service.call_from_config(self.hass, {})
        self.assertEqual(2, mock_log.call_count)

        service.call_from_config(self.hass, {
            'service': 'invalid'
        })
        self.assertEqual(3, mock_log.call_count)

    def test_extract_entity_ids(self):
        """Test extract_entity_ids method."""
        self.hass.states.set('light.Bowl', STATE_ON)
        self.hass.states.set('light.Ceiling', STATE_OFF)
        self.hass.states.set('light.Kitchen', STATE_OFF)

        loader.get_component('group').Group.create_group(
            self.hass, 'test', ['light.Ceiling', 'light.Kitchen'])

        call = ha.ServiceCall('light', 'turn_on',
                              {ATTR_ENTITY_ID: 'light.Bowl'})

        self.assertEqual(['light.bowl'],
                         service.extract_entity_ids(self.hass, call))

        call = ha.ServiceCall('light', 'turn_on',
                              {ATTR_ENTITY_ID: 'group.test'})

        self.assertEqual(['light.ceiling', 'light.kitchen'],
                         service.extract_entity_ids(self.hass, call))

        self.assertEqual(['group.test'], service.extract_entity_ids(
            self.hass, call, expand_group=False))


@asyncio.coroutine
def test_get_state_services(hass):
    """Test async_get_state_services."""
    domain = 'light'
    schema = vol.Schema({
        'entity_id': cv.entity_ids, 'transition': 999, 'brightness': 100})
    async_mock_service(hass, domain, SERVICE_TURN_ON, schema, 'on')
    state_attrs = {'transition': 999, 'brightness': 100}
    state = ha.State('light.test', 'on', state_attrs)

    services = service.async_get_state_services(hass, domain, state)

    assert SERVICE_TURN_ON in services
    assert services[SERVICE_TURN_ON].data == state_attrs


@asyncio.coroutine
def test_get_state_services_no_domain(hass, caplog):
    """Test async_get_state_services with no services for domain."""
    domain = 'light'
    state_attrs = {'transition': 999, 'brightness': 100}
    state = ha.State('light.test', 'on', state_attrs)

    services = service.async_get_state_services(hass, domain, state)

    assert services is None
    assert 'WARNING' in caplog.text
    assert "No services found for domain {}".format(domain) in caplog.text


@asyncio.coroutine
def test_get_state_services_no_schema(hass):
    """Test async_get_state_services with no schema for service."""
    domain = 'light'
    async_mock_service(hass, domain, SERVICE_TURN_ON, state='on')
    state_attrs = {'transition': 999, 'brightness': 100}
    state = ha.State('light.test', 'on', state_attrs)

    services = service.async_get_state_services(hass, domain, state)

    assert SERVICE_TURN_ON in services
    assert not services[SERVICE_TURN_ON].data


@asyncio.coroutine
def test_get_state_services_no_required(hass):
    """Test get_state_services with no state and no required node in schema."""
    domain = 'test'
    schema = vol.Schema({'entity_id': cv.entity_ids, 'test_attr': 999})
    async_mock_service(hass, domain, 'test_service', schema)
    state_attrs = {'test_attr': 999}
    state = ha.State('test.test', None, state_attrs)

    services = service.async_get_state_services(hass, domain, state)

    assert not services


@asyncio.coroutine
def test_get_state_services_not_valid(hass):
    """Test async_get_state_services with not valid state attributes."""
    domain = 'light'
    schema = vol.Schema({
        'entity_id': cv.entity_ids, 'transition': 999, 'brightness': 100})
    async_mock_service(hass, domain, SERVICE_TURN_ON, schema, 'on')
    state_attrs = {'transition': 4444, 'brightness': 555}
    state = ha.State('light.test', 'on', state_attrs)

    services = service.async_get_state_services(hass, domain, state)

    assert SERVICE_TURN_ON not in services


@asyncio.coroutine
def test_get_state_services_no_attributes(hass):
    """Test async_get_state_services with no state attributes."""
    domain = 'light'
    schema = vol.Schema({
        'entity_id': cv.entity_ids, 'transition': 999, 'brightness': 100})
    async_mock_service(hass, domain, SERVICE_TURN_ON, schema, 'on')
    state_attrs = {}
    state = ha.State('light.test', 'on', state_attrs)

    services = service.async_get_state_services(hass, domain, state)

    assert SERVICE_TURN_ON in services
    assert not services[SERVICE_TURN_ON].data
