"""The testd for Core components."""
# pylint: disable=protected-access
import asyncio
import unittest
from unittest.mock import patch, Mock

import yaml

import homeassistant.core as ha
from homeassistant import config
from homeassistant.const import (
    STATE_ON, STATE_OFF, SERVICE_TURN_ON, SERVICE_TURN_OFF, SERVICE_TOGGLE)
import homeassistant.components as comps
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity
from homeassistant.util.async import run_coroutine_threadsafe

from tests.common import (
    get_test_home_assistant, mock_service, patch_yaml_files, mock_coro)


class TestComponentsCore(unittest.TestCase):
    """Test homeassistant.components module."""

    # pylint: disable=invalid-name
    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.assertTrue(run_coroutine_threadsafe(
            comps.async_setup(self.hass, {}), self.hass.loop
        ).result())

        self.hass.states.set('light.Bowl', STATE_ON)
        self.hass.states.set('light.Ceiling', STATE_OFF)

    # pylint: disable=invalid-name
    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_is_on(self):
        """Test is_on method."""
        self.assertTrue(comps.is_on(self.hass, 'light.Bowl'))
        self.assertFalse(comps.is_on(self.hass, 'light.Ceiling'))
        self.assertTrue(comps.is_on(self.hass))
        self.assertFalse(comps.is_on(self.hass, 'non_existing.entity'))

    def test_turn_on_without_entities(self):
        """Test turn_on method without entities."""
        calls = mock_service(self.hass, 'light', SERVICE_TURN_ON)
        comps.turn_on(self.hass)
        self.hass.block_till_done()
        self.assertEqual(0, len(calls))

    def test_turn_on(self):
        """Test turn_on method."""
        calls = mock_service(self.hass, 'light', SERVICE_TURN_ON)
        comps.turn_on(self.hass, 'light.Ceiling')
        self.hass.block_till_done()
        self.assertEqual(1, len(calls))

    def test_turn_off(self):
        """Test turn_off method."""
        calls = mock_service(self.hass, 'light', SERVICE_TURN_OFF)
        comps.turn_off(self.hass, 'light.Bowl')
        self.hass.block_till_done()
        self.assertEqual(1, len(calls))

    def test_toggle(self):
        """Test toggle method."""
        calls = mock_service(self.hass, 'light', SERVICE_TOGGLE)
        comps.toggle(self.hass, 'light.Bowl')
        self.hass.block_till_done()
        self.assertEqual(1, len(calls))

    @asyncio.coroutine
    @patch('homeassistant.core.ServiceRegistry.call')
    def test_turn_on_to_not_block_for_domains_without_service(self, mock_call):
        """Test if turn_on is blocking domain with no service."""
        mock_service(self.hass, 'light', SERVICE_TURN_ON)

        # We can't test if our service call results in services being called
        # because by mocking out the call service method, we mock out all
        # So we mimick how the service registry calls services
        service_call = ha.ServiceCall('homeassistant', 'turn_on', {
            'entity_id': ['light.test', 'sensor.bla', 'light.bla']
        })
        service = self.hass.services._services['homeassistant']['turn_on']
        yield from service.func(service_call)

        self.assertEqual(2, mock_call.call_count)
        self.assertEqual(
            ('light', 'turn_on', {'entity_id': ['light.bla', 'light.test']},
             True),
            mock_call.call_args_list[0][0])
        self.assertEqual(
            ('sensor', 'turn_on', {'entity_id': ['sensor.bla']}, False),
            mock_call.call_args_list[1][0])

    @patch('homeassistant.config.os.path.isfile', Mock(return_value=True))
    def test_reload_core_conf(self):
        """Test reload core conf service."""
        ent = entity.Entity()
        ent.entity_id = 'test.entity'
        ent.hass = self.hass
        ent.schedule_update_ha_state()
        self.hass.block_till_done()

        state = self.hass.states.get('test.entity')
        assert state is not None
        assert state.state == 'unknown'
        assert state.attributes == {}

        files = {
            config.YAML_CONFIG_FILE: yaml.dump({
                ha.DOMAIN: {
                    'latitude': 10,
                    'longitude': 20,
                    'customize': {
                        'test.Entity': {
                            'hello': 'world'
                        }
                    }
                }
            })
        }
        with patch_yaml_files(files, True):
            comps.reload_core_config(self.hass)
            self.hass.block_till_done()

        assert 10 == self.hass.config.latitude
        assert 20 == self.hass.config.longitude

        ent.schedule_update_ha_state()
        self.hass.block_till_done()

        state = self.hass.states.get('test.entity')
        assert state is not None
        assert state.state == 'unknown'
        assert state.attributes.get('hello') == 'world'

    @patch('homeassistant.config.os.path.isfile', Mock(return_value=True))
    @patch('homeassistant.components._LOGGER.error')
    @patch('homeassistant.config.async_process_ha_core_config')
    def test_reload_core_with_wrong_conf(self, mock_process, mock_error):
        """Test reload core conf service."""
        files = {
            config.YAML_CONFIG_FILE: yaml.dump(['invalid', 'config'])
        }
        with patch_yaml_files(files, True):
            comps.reload_core_config(self.hass)
            self.hass.block_till_done()

        assert mock_error.called
        assert mock_process.called is False

    @patch('homeassistant.core.HomeAssistant.async_stop',
           return_value=mock_coro())
    def test_stop_homeassistant(self, mock_stop):
        """Test stop service."""
        comps.stop(self.hass)
        self.hass.block_till_done()
        assert mock_stop.called

    @patch('homeassistant.core.HomeAssistant.async_stop',
           return_value=mock_coro())
    @patch('homeassistant.config.async_check_ha_config_file',
           return_value=mock_coro())
    def test_restart_homeassistant(self, mock_check, mock_restart):
        """Test stop service."""
        comps.restart(self.hass)
        self.hass.block_till_done()
        assert mock_restart.called
        assert mock_check.called

    @patch('homeassistant.core.HomeAssistant.async_stop',
           return_value=mock_coro())
    @patch('homeassistant.config.async_check_ha_config_file',
           side_effect=HomeAssistantError("Test error"))
    def test_restart_homeassistant_wrong_conf(self, mock_check, mock_restart):
        """Test stop service."""
        comps.restart(self.hass)
        self.hass.block_till_done()
        assert mock_check.called
        assert not mock_restart.called

    @patch('homeassistant.core.HomeAssistant.async_stop',
           return_value=mock_coro())
    @patch('homeassistant.config.async_check_ha_config_file',
           return_value=mock_coro())
    def test_check_config(self, mock_check, mock_stop):
        """Test stop service."""
        comps.check_config(self.hass)
        self.hass.block_till_done()
        assert mock_check.called
        assert not mock_stop.called
