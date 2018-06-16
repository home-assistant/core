"""Test service helpers."""
import asyncio
from copy import deepcopy
import unittest
from unittest.mock import patch

# To prevent circular import when running just this file
import homeassistant.components  # noqa
from homeassistant import core as ha, loader
from homeassistant.const import STATE_ON, STATE_OFF, ATTR_ENTITY_ID
from homeassistant.helpers import service, template
from homeassistant.setup import async_setup_component
import homeassistant.helpers.config_validation as cv

from tests.common import get_test_home_assistant, mock_service


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

        self.assertEqual(len(self.calls), 0)

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
        """Test failing if service is missing."""
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

        loader.get_component(self.hass, 'group').Group.create_group(
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
