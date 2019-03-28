"""The tests for Core components."""
# pylint: disable=protected-access
import unittest
from unittest.mock import patch, Mock

import yaml

import homeassistant.core as ha
from homeassistant import config
from homeassistant.const import (
    ATTR_ENTITY_ID, STATE_ON, STATE_OFF, SERVICE_HOMEASSISTANT_RESTART,
    SERVICE_HOMEASSISTANT_STOP, SERVICE_TURN_ON, SERVICE_TURN_OFF,
    SERVICE_TOGGLE)
import homeassistant.components as comps
from homeassistant.setup import async_setup_component
from homeassistant.components.homeassistant import (
    SERVICE_CHECK_CONFIG, SERVICE_RELOAD_CORE_CONFIG)
import homeassistant.helpers.intent as intent
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity
from homeassistant.util.async_ import run_coroutine_threadsafe

from tests.common import (
    get_test_home_assistant, mock_service, patch_yaml_files, mock_coro,
    async_mock_service)


def turn_on(hass, entity_id=None, **service_data):
    """Turn specified entity on if possible.

    This is a legacy helper method. Do not use it for new tests.
    """
    if entity_id is not None:
        service_data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(ha.DOMAIN, SERVICE_TURN_ON, service_data)


def turn_off(hass, entity_id=None, **service_data):
    """Turn specified entity off.

    This is a legacy helper method. Do not use it for new tests.
    """
    if entity_id is not None:
        service_data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(ha.DOMAIN, SERVICE_TURN_OFF, service_data)


def toggle(hass, entity_id=None, **service_data):
    """Toggle specified entity.

    This is a legacy helper method. Do not use it for new tests.
    """
    if entity_id is not None:
        service_data[ATTR_ENTITY_ID] = entity_id

    hass.services.call(ha.DOMAIN, SERVICE_TOGGLE, service_data)


def stop(hass):
    """Stop Home Assistant.

    This is a legacy helper method. Do not use it for new tests.
    """
    hass.services.call(ha.DOMAIN, SERVICE_HOMEASSISTANT_STOP)


def restart(hass):
    """Stop Home Assistant.

    This is a legacy helper method. Do not use it for new tests.
    """
    hass.services.call(ha.DOMAIN, SERVICE_HOMEASSISTANT_RESTART)


def check_config(hass):
    """Check the config files.

    This is a legacy helper method. Do not use it for new tests.
    """
    hass.services.call(ha.DOMAIN, SERVICE_CHECK_CONFIG)


def reload_core_config(hass):
    """Reload the core config.

    This is a legacy helper method. Do not use it for new tests.
    """
    hass.services.call(ha.DOMAIN, SERVICE_RELOAD_CORE_CONFIG)


class TestComponentsCore(unittest.TestCase):
    """Test homeassistant.components module."""

    # pylint: disable=invalid-name
    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        assert run_coroutine_threadsafe(
            async_setup_component(self.hass, 'homeassistant', {}),
            self.hass.loop
        ).result()

        self.hass.states.set('light.Bowl', STATE_ON)
        self.hass.states.set('light.Ceiling', STATE_OFF)

    # pylint: disable=invalid-name
    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_is_on(self):
        """Test is_on method."""
        assert comps.is_on(self.hass, 'light.Bowl')
        assert not comps.is_on(self.hass, 'light.Ceiling')
        assert comps.is_on(self.hass)
        assert not comps.is_on(self.hass, 'non_existing.entity')

    def test_turn_on_without_entities(self):
        """Test turn_on method without entities."""
        calls = mock_service(self.hass, 'light', SERVICE_TURN_ON)
        turn_on(self.hass)
        self.hass.block_till_done()
        assert 0 == len(calls)

    def test_turn_on(self):
        """Test turn_on method."""
        calls = mock_service(self.hass, 'light', SERVICE_TURN_ON)
        turn_on(self.hass, 'light.Ceiling')
        self.hass.block_till_done()
        assert 1 == len(calls)

    def test_turn_off(self):
        """Test turn_off method."""
        calls = mock_service(self.hass, 'light', SERVICE_TURN_OFF)
        turn_off(self.hass, 'light.Bowl')
        self.hass.block_till_done()
        assert 1 == len(calls)

    def test_toggle(self):
        """Test toggle method."""
        calls = mock_service(self.hass, 'light', SERVICE_TOGGLE)
        toggle(self.hass, 'light.Bowl')
        self.hass.block_till_done()
        assert 1 == len(calls)

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
            reload_core_config(self.hass)
            self.hass.block_till_done()

        assert self.hass.config.latitude == 10
        assert self.hass.config.longitude == 20

        ent.schedule_update_ha_state()
        self.hass.block_till_done()

        state = self.hass.states.get('test.entity')
        assert state is not None
        assert state.state == 'unknown'
        assert state.attributes.get('hello') == 'world'

    @patch('homeassistant.config.os.path.isfile', Mock(return_value=True))
    @patch('homeassistant.components.homeassistant._LOGGER.error')
    @patch('homeassistant.config.async_process_ha_core_config')
    def test_reload_core_with_wrong_conf(self, mock_process, mock_error):
        """Test reload core conf service."""
        files = {
            config.YAML_CONFIG_FILE: yaml.dump(['invalid', 'config'])
        }
        with patch_yaml_files(files, True):
            reload_core_config(self.hass)
            self.hass.block_till_done()

        assert mock_error.called
        assert mock_process.called is False

    @patch('homeassistant.core.HomeAssistant.async_stop',
           return_value=mock_coro())
    def test_stop_homeassistant(self, mock_stop):
        """Test stop service."""
        stop(self.hass)
        self.hass.block_till_done()
        assert mock_stop.called

    @patch('homeassistant.core.HomeAssistant.async_stop',
           return_value=mock_coro())
    @patch('homeassistant.config.async_check_ha_config_file',
           return_value=mock_coro())
    def test_restart_homeassistant(self, mock_check, mock_restart):
        """Test stop service."""
        restart(self.hass)
        self.hass.block_till_done()
        assert mock_restart.called
        assert mock_check.called

    @patch('homeassistant.core.HomeAssistant.async_stop',
           return_value=mock_coro())
    @patch('homeassistant.config.async_check_ha_config_file',
           side_effect=HomeAssistantError("Test error"))
    def test_restart_homeassistant_wrong_conf(self, mock_check, mock_restart):
        """Test stop service."""
        restart(self.hass)
        self.hass.block_till_done()
        assert mock_check.called
        assert not mock_restart.called

    @patch('homeassistant.core.HomeAssistant.async_stop',
           return_value=mock_coro())
    @patch('homeassistant.config.async_check_ha_config_file',
           return_value=mock_coro())
    def test_check_config(self, mock_check, mock_stop):
        """Test stop service."""
        check_config(self.hass)
        self.hass.block_till_done()
        assert mock_check.called
        assert not mock_stop.called


async def test_turn_on_intent(hass):
    """Test HassTurnOn intent."""
    result = await async_setup_component(hass, 'homeassistant', {})
    assert result

    hass.states.async_set('light.test_light', 'off')
    calls = async_mock_service(hass, 'light', SERVICE_TURN_ON)

    response = await intent.async_handle(
        hass, 'test', 'HassTurnOn', {'name': {'value': 'test light'}}
    )
    await hass.async_block_till_done()

    assert response.speech['plain']['speech'] == 'Turned test light on'
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == 'light'
    assert call.service == 'turn_on'
    assert call.data == {'entity_id': ['light.test_light']}


async def test_turn_off_intent(hass):
    """Test HassTurnOff intent."""
    result = await async_setup_component(hass, 'homeassistant', {})
    assert result

    hass.states.async_set('light.test_light', 'on')
    calls = async_mock_service(hass, 'light', SERVICE_TURN_OFF)

    response = await intent.async_handle(
        hass, 'test', 'HassTurnOff', {'name': {'value': 'test light'}}
    )
    await hass.async_block_till_done()

    assert response.speech['plain']['speech'] == 'Turned test light off'
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == 'light'
    assert call.service == 'turn_off'
    assert call.data == {'entity_id': ['light.test_light']}


async def test_toggle_intent(hass):
    """Test HassToggle intent."""
    result = await async_setup_component(hass, 'homeassistant', {})
    assert result

    hass.states.async_set('light.test_light', 'off')
    calls = async_mock_service(hass, 'light', SERVICE_TOGGLE)

    response = await intent.async_handle(
        hass, 'test', 'HassToggle', {'name': {'value': 'test light'}}
    )
    await hass.async_block_till_done()

    assert response.speech['plain']['speech'] == 'Toggled test light'
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == 'light'
    assert call.service == 'toggle'
    assert call.data == {'entity_id': ['light.test_light']}


async def test_turn_on_multiple_intent(hass):
    """Test HassTurnOn intent with multiple similar entities.

    This tests that matching finds the proper entity among similar names.
    """
    result = await async_setup_component(hass, 'homeassistant', {})
    assert result

    hass.states.async_set('light.test_light', 'off')
    hass.states.async_set('light.test_lights_2', 'off')
    hass.states.async_set('light.test_lighter', 'off')
    calls = async_mock_service(hass, 'light', SERVICE_TURN_ON)

    response = await intent.async_handle(
        hass, 'test', 'HassTurnOn', {'name': {'value': 'test lights'}}
    )
    await hass.async_block_till_done()

    assert response.speech['plain']['speech'] == 'Turned test lights 2 on'
    assert len(calls) == 1
    call = calls[0]
    assert call.domain == 'light'
    assert call.service == 'turn_on'
    assert call.data == {'entity_id': ['light.test_lights_2']}


async def test_turn_on_to_not_block_for_domains_without_service(hass):
    """Test if turn_on is blocking domain with no service."""
    await async_setup_component(hass, 'homeassistant', {})
    async_mock_service(hass, 'light', SERVICE_TURN_ON)
    hass.states.async_set('light.Bowl', STATE_ON)
    hass.states.async_set('light.Ceiling', STATE_OFF)

    # We can't test if our service call results in services being called
    # because by mocking out the call service method, we mock out all
    # So we mimic how the service registry calls services
    service_call = ha.ServiceCall('homeassistant', 'turn_on', {
        'entity_id': ['light.test', 'sensor.bla', 'light.bla']
    })
    service = hass.services._services['homeassistant']['turn_on']

    with patch('homeassistant.core.ServiceRegistry.async_call',
               side_effect=lambda *args: mock_coro()) as mock_call:
        await service.func(service_call)

    assert mock_call.call_count == 2
    assert mock_call.call_args_list[0][0] == (
        'light', 'turn_on', {'entity_id': ['light.bla', 'light.test']}, True)
    assert mock_call.call_args_list[1][0] == (
        'sensor', 'turn_on', {'entity_id': ['sensor.bla']}, False)


async def test_entity_update(hass):
    """Test being able to call entity update."""
    await async_setup_component(hass, 'homeassistant', {})

    with patch('homeassistant.helpers.entity_component.async_update_entity',
               return_value=mock_coro()) as mock_update:
        await hass.services.async_call('homeassistant', 'update_entity', {
            'entity_id': ['light.kitchen']
        }, blocking=True)

    assert len(mock_update.mock_calls) == 1
    assert mock_update.mock_calls[0][1][1] == 'light.kitchen'
