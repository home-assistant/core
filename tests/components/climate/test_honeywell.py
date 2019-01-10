"""The test the Honeywell thermostat module."""
import socket
import unittest
from unittest import mock

import voluptuous as vol
import somecomfort

from homeassistant.const import (
    CONF_USERNAME, CONF_PASSWORD, TEMP_CELSIUS, TEMP_FAHRENHEIT)
from homeassistant.components.climate import (
    ATTR_FAN_MODE, ATTR_OPERATION_MODE, ATTR_FAN_LIST, ATTR_OPERATION_LIST)

import homeassistant.components.climate.honeywell as honeywell
import pytest


class TestHoneywell(unittest.TestCase):
    """A test class for Honeywell themostats."""

    @mock.patch('somecomfort.SomeComfort')
    @mock.patch('homeassistant.components.climate.'
                'honeywell.HoneywellUSThermostat')
    def test_setup_us(self, mock_ht, mock_sc):
        """Test for the US setup."""
        config = {
            CONF_USERNAME: 'user',
            CONF_PASSWORD: 'pass',
            honeywell.CONF_COOL_AWAY_TEMPERATURE: 18,
            honeywell.CONF_HEAT_AWAY_TEMPERATURE: 28,
            honeywell.CONF_REGION: 'us',
        }
        bad_pass_config = {
            CONF_USERNAME: 'user',
            honeywell.CONF_COOL_AWAY_TEMPERATURE: 18,
            honeywell.CONF_HEAT_AWAY_TEMPERATURE: 28,
            honeywell.CONF_REGION: 'us',
        }
        bad_region_config = {
            CONF_USERNAME: 'user',
            CONF_PASSWORD: 'pass',
            honeywell.CONF_COOL_AWAY_TEMPERATURE: 18,
            honeywell.CONF_HEAT_AWAY_TEMPERATURE: 28,
            honeywell.CONF_REGION: 'un',
        }

        with pytest.raises(vol.Invalid):
            honeywell.PLATFORM_SCHEMA(None)

        with pytest.raises(vol.Invalid):
            honeywell.PLATFORM_SCHEMA({})

        with pytest.raises(vol.Invalid):
            honeywell.PLATFORM_SCHEMA(bad_pass_config)

        with pytest.raises(vol.Invalid):
            honeywell.PLATFORM_SCHEMA(bad_region_config)

        hass = mock.MagicMock()
        add_entities = mock.MagicMock()

        locations = [
            mock.MagicMock(),
            mock.MagicMock(),
        ]
        devices_1 = [mock.MagicMock()]
        devices_2 = [mock.MagicMock(), mock.MagicMock]
        mock_sc.return_value.locations_by_id.values.return_value = \
            locations
        locations[0].devices_by_id.values.return_value = devices_1
        locations[1].devices_by_id.values.return_value = devices_2

        result = honeywell.setup_platform(hass, config, add_entities)
        assert result
        assert mock_sc.call_count == 1
        assert mock_sc.call_args == mock.call('user', 'pass')
        mock_ht.assert_has_calls([
            mock.call(mock_sc.return_value, devices_1[0], 18, 28,
                      'user', 'pass'),
            mock.call(mock_sc.return_value, devices_2[0], 18, 28,
                      'user', 'pass'),
            mock.call(mock_sc.return_value, devices_2[1], 18, 28,
                      'user', 'pass'),
        ])

    @mock.patch('somecomfort.SomeComfort')
    def test_setup_us_failures(self, mock_sc):
        """Test the US setup."""
        hass = mock.MagicMock()
        add_entities = mock.MagicMock()
        config = {
            CONF_USERNAME: 'user',
            CONF_PASSWORD: 'pass',
            honeywell.CONF_REGION: 'us',
        }

        mock_sc.side_effect = somecomfort.AuthError
        result = honeywell.setup_platform(hass, config, add_entities)
        assert not result
        assert not add_entities.called

        mock_sc.side_effect = somecomfort.SomeComfortError
        result = honeywell.setup_platform(hass, config, add_entities)
        assert not result
        assert not add_entities.called

    @mock.patch('somecomfort.SomeComfort')
    @mock.patch('homeassistant.components.climate.'
                'honeywell.HoneywellUSThermostat')
    def _test_us_filtered_devices(self, mock_ht, mock_sc, loc=None, dev=None):
        """Test for US filtered thermostats."""
        config = {
            CONF_USERNAME: 'user',
            CONF_PASSWORD: 'pass',
            honeywell.CONF_REGION: 'us',
            'location': loc,
            'thermostat': dev,
        }
        locations = {
            1: mock.MagicMock(locationid=mock.sentinel.loc1,
                              devices_by_id={
                                  11: mock.MagicMock(
                                      deviceid=mock.sentinel.loc1dev1),
                                  12: mock.MagicMock(
                                      deviceid=mock.sentinel.loc1dev2),
                              }),
            2: mock.MagicMock(locationid=mock.sentinel.loc2,
                              devices_by_id={
                                  21: mock.MagicMock(
                                      deviceid=mock.sentinel.loc2dev1),
                              }),
            3: mock.MagicMock(locationid=mock.sentinel.loc3,
                              devices_by_id={
                                  31: mock.MagicMock(
                                      deviceid=mock.sentinel.loc3dev1),
                              }),
        }
        mock_sc.return_value = mock.MagicMock(locations_by_id=locations)
        hass = mock.MagicMock()
        add_entities = mock.MagicMock()
        assert honeywell.setup_platform(hass, config, add_entities) is True

        return mock_ht.call_args_list, mock_sc

    def test_us_filtered_thermostat_1(self):
        """Test for US filtered thermostats."""
        result, client = self._test_us_filtered_devices(
            dev=mock.sentinel.loc1dev1)
        devices = [x[0][1].deviceid for x in result]
        assert [mock.sentinel.loc1dev1] == devices

    def test_us_filtered_thermostat_2(self):
        """Test for US filtered location."""
        result, client = self._test_us_filtered_devices(
            dev=mock.sentinel.loc2dev1)
        devices = [x[0][1].deviceid for x in result]
        assert [mock.sentinel.loc2dev1] == devices

    def test_us_filtered_location_1(self):
        """Test for US filtered locations."""
        result, client = self._test_us_filtered_devices(
            loc=mock.sentinel.loc1)
        devices = [x[0][1].deviceid for x in result]
        assert [mock.sentinel.loc1dev1, mock.sentinel.loc1dev2] == devices

    def test_us_filtered_location_2(self):
        """Test for US filtered locations."""
        result, client = self._test_us_filtered_devices(
            loc=mock.sentinel.loc2)
        devices = [x[0][1].deviceid for x in result]
        assert [mock.sentinel.loc2dev1] == devices

    @mock.patch('evohomeclient.EvohomeClient')
    @mock.patch('homeassistant.components.climate.honeywell.'
                'RoundThermostat')
    def test_eu_setup_full_config(self, mock_round, mock_evo):
        """Test the EU setup with complete configuration."""
        config = {
            CONF_USERNAME: 'user',
            CONF_PASSWORD: 'pass',
            honeywell.CONF_AWAY_TEMPERATURE: 20.0,
            honeywell.CONF_REGION: 'eu',
        }
        mock_evo.return_value.temperatures.return_value = [
            {'id': 'foo'}, {'id': 'bar'}]
        hass = mock.MagicMock()
        add_entities = mock.MagicMock()
        assert honeywell.setup_platform(hass, config, add_entities)
        assert mock_evo.call_count == 1
        assert mock_evo.call_args == mock.call('user', 'pass')
        assert mock_evo.return_value.temperatures.call_count == 1
        assert mock_evo.return_value.temperatures.call_args == \
            mock.call(force_refresh=True)
        mock_round.assert_has_calls([
            mock.call(mock_evo.return_value, 'foo', True, 20.0),
            mock.call(mock_evo.return_value, 'bar', False, 20.0),
        ])
        assert 2 == add_entities.call_count

    @mock.patch('evohomeclient.EvohomeClient')
    @mock.patch('homeassistant.components.climate.honeywell.'
                'RoundThermostat')
    def test_eu_setup_partial_config(self, mock_round, mock_evo):
        """Test the EU setup with partial configuration."""
        config = {
            CONF_USERNAME: 'user',
            CONF_PASSWORD: 'pass',
            honeywell.CONF_REGION: 'eu',
        }

        mock_evo.return_value.temperatures.return_value = [
            {'id': 'foo'}, {'id': 'bar'}]
        config[honeywell.CONF_AWAY_TEMPERATURE] = \
            honeywell.DEFAULT_AWAY_TEMPERATURE

        hass = mock.MagicMock()
        add_entities = mock.MagicMock()
        assert honeywell.setup_platform(hass, config, add_entities)
        mock_round.assert_has_calls([
            mock.call(mock_evo.return_value, 'foo', True, 16),
            mock.call(mock_evo.return_value, 'bar', False, 16),
        ])

    @mock.patch('evohomeclient.EvohomeClient')
    @mock.patch('homeassistant.components.climate.honeywell.'
                'RoundThermostat')
    def test_eu_setup_bad_temp(self, mock_round, mock_evo):
        """Test the EU setup with invalid temperature."""
        config = {
            CONF_USERNAME: 'user',
            CONF_PASSWORD: 'pass',
            honeywell.CONF_AWAY_TEMPERATURE: 'ponies',
            honeywell.CONF_REGION: 'eu',
        }

        with pytest.raises(vol.Invalid):
            honeywell.PLATFORM_SCHEMA(config)

    @mock.patch('evohomeclient.EvohomeClient')
    @mock.patch('homeassistant.components.climate.honeywell.'
                'RoundThermostat')
    def test_eu_setup_error(self, mock_round, mock_evo):
        """Test the EU setup with errors."""
        config = {
            CONF_USERNAME: 'user',
            CONF_PASSWORD: 'pass',
            honeywell.CONF_AWAY_TEMPERATURE: 20,
            honeywell.CONF_REGION: 'eu',
        }
        mock_evo.return_value.temperatures.side_effect = socket.error
        add_entities = mock.MagicMock()
        hass = mock.MagicMock()
        assert not honeywell.setup_platform(hass, config, add_entities)


class TestHoneywellRound(unittest.TestCase):
    """A test class for Honeywell Round thermostats."""

    def setup_method(self, method):
        """Test the setup method."""
        def fake_temperatures(force_refresh=None):
            """Create fake temperatures."""
            temps = [
                {'id': '1', 'temp': 20, 'setpoint': 21,
                 'thermostat': 'main', 'name': 'House'},
                {'id': '2', 'temp': 21, 'setpoint': 22,
                 'thermostat': 'DOMESTIC_HOT_WATER'},
            ]
            return temps

        self.device = mock.MagicMock()
        self.device.temperatures.side_effect = fake_temperatures
        self.round1 = honeywell.RoundThermostat(self.device, '1',
                                                True, 16)
        self.round1.update()
        self.round2 = honeywell.RoundThermostat(self.device, '2',
                                                False, 17)
        self.round2.update()

    def test_attributes(self):
        """Test the attributes."""
        assert 'House' == self.round1.name
        assert TEMP_CELSIUS == self.round1.temperature_unit
        assert 20 == self.round1.current_temperature
        assert 21 == self.round1.target_temperature
        assert not self.round1.is_away_mode_on

        assert 'Hot Water' == self.round2.name
        assert TEMP_CELSIUS == self.round2.temperature_unit
        assert 21 == self.round2.current_temperature
        assert self.round2.target_temperature is None
        assert not self.round2.is_away_mode_on

    def test_away_mode(self):
        """Test setting the away mode."""
        assert not self.round1.is_away_mode_on
        self.round1.turn_away_mode_on()
        assert self.round1.is_away_mode_on
        assert self.device.set_temperature.call_count == 1
        assert self.device.set_temperature.call_args == mock.call('House', 16)

        self.device.set_temperature.reset_mock()
        self.round1.turn_away_mode_off()
        assert not self.round1.is_away_mode_on
        assert self.device.cancel_temp_override.call_count == 1
        assert self.device.cancel_temp_override.call_args == mock.call('House')

    def test_set_temperature(self):
        """Test setting the temperature."""
        self.round1.set_temperature(temperature=25)
        assert self.device.set_temperature.call_count == 1
        assert self.device.set_temperature.call_args == mock.call('House', 25)

    def test_set_operation_mode(self) -> None:
        """Test setting the system operation."""
        self.round1.set_operation_mode('cool')
        assert 'cool' == self.round1.current_operation
        assert 'cool' == self.device.system_mode

        self.round1.set_operation_mode('heat')
        assert 'heat' == self.round1.current_operation
        assert 'heat' == self.device.system_mode


class TestHoneywellUS(unittest.TestCase):
    """A test class for Honeywell US thermostats."""

    def setup_method(self, method):
        """Test the setup method."""
        self.client = mock.MagicMock()
        self.device = mock.MagicMock()
        self.cool_away_temp = 18
        self.heat_away_temp = 28
        self.honeywell = honeywell.HoneywellUSThermostat(
            self.client, self.device,
            self.cool_away_temp, self.heat_away_temp,
            'user', 'password')

        self.device.fan_running = True
        self.device.name = 'test'
        self.device.temperature_unit = 'F'
        self.device.current_temperature = 72
        self.device.setpoint_cool = 78
        self.device.setpoint_heat = 65
        self.device.system_mode = 'heat'
        self.device.fan_mode = 'auto'

    def test_properties(self):
        """Test the properties."""
        assert self.honeywell.is_fan_on
        assert 'test' == self.honeywell.name
        assert 72 == self.honeywell.current_temperature

    def test_unit_of_measurement(self):
        """Test the unit of measurement."""
        assert TEMP_FAHRENHEIT == self.honeywell.temperature_unit
        self.device.temperature_unit = 'C'
        assert TEMP_CELSIUS == self.honeywell.temperature_unit

    def test_target_temp(self):
        """Test the target temperature."""
        assert 65 == self.honeywell.target_temperature
        self.device.system_mode = 'cool'
        assert 78 == self.honeywell.target_temperature

    def test_set_temp(self):
        """Test setting the temperature."""
        self.honeywell.set_temperature(temperature=70)
        assert 70 == self.device.setpoint_heat
        assert 70 == self.honeywell.target_temperature

        self.device.system_mode = 'cool'
        assert 78 == self.honeywell.target_temperature
        self.honeywell.set_temperature(temperature=74)
        assert 74 == self.device.setpoint_cool
        assert 74 == self.honeywell.target_temperature

    def test_set_operation_mode(self) -> None:
        """Test setting the operation mode."""
        self.honeywell.set_operation_mode('cool')
        assert 'cool' == self.device.system_mode

        self.honeywell.set_operation_mode('heat')
        assert 'heat' == self.device.system_mode

    def test_set_temp_fail(self):
        """Test if setting the temperature fails."""
        self.device.setpoint_heat = mock.MagicMock(
            side_effect=somecomfort.SomeComfortError)
        self.honeywell.set_temperature(temperature=123)

    def test_attributes(self):
        """Test the attributes."""
        expected = {
            honeywell.ATTR_FAN: 'running',
            ATTR_FAN_MODE: 'auto',
            ATTR_OPERATION_MODE: 'heat',
            ATTR_FAN_LIST: somecomfort.FAN_MODES,
            ATTR_OPERATION_LIST: somecomfort.SYSTEM_MODES,
        }
        assert expected == self.honeywell.device_state_attributes
        expected['fan'] = 'idle'
        self.device.fan_running = False
        assert expected == self.honeywell.device_state_attributes

    def test_with_no_fan(self):
        """Test if there is on fan."""
        self.device.fan_running = False
        self.device.fan_mode = None
        expected = {
            honeywell.ATTR_FAN: 'idle',
            ATTR_FAN_MODE: None,
            ATTR_OPERATION_MODE: 'heat',
            ATTR_FAN_LIST: somecomfort.FAN_MODES,
            ATTR_OPERATION_LIST: somecomfort.SYSTEM_MODES,
        }
        assert expected == self.honeywell.device_state_attributes

    def test_heat_away_mode(self):
        """Test setting the heat away mode."""
        self.honeywell.set_operation_mode('heat')
        assert not self.honeywell.is_away_mode_on
        self.honeywell.turn_away_mode_on()
        assert self.honeywell.is_away_mode_on
        assert self.device.setpoint_heat == self.heat_away_temp
        assert self.device.hold_heat is True

        self.honeywell.turn_away_mode_off()
        assert not self.honeywell.is_away_mode_on
        assert self.device.hold_heat is False

    @mock.patch('somecomfort.SomeComfort')
    def test_retry(self, test_somecomfort):
        """Test retry connection."""
        old_device = self.honeywell._device
        self.honeywell._retry()
        assert self.honeywell._device == old_device
