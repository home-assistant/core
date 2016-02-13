"""
tests.components.thermostat.honeywell
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests the Honeywell thermostat module.
"""
import unittest
from unittest import mock

import somecomfort

from homeassistant.const import (CONF_USERNAME, CONF_PASSWORD,
                                 TEMP_CELCIUS, TEMP_FAHRENHEIT)
import homeassistant.components.thermostat.honeywell as honeywell


class TestHoneywell(unittest.TestCase):
    @mock.patch('somecomfort.SomeComfort')
    @mock.patch('homeassistant.components.thermostat.'
                'honeywell.HoneywellUSThermostat')
    def test_setup_us(self, mock_ht, mock_sc):
        config = {
            CONF_USERNAME: 'user',
            CONF_PASSWORD: 'pass',
            'region': 'us',
        }
        hass = mock.MagicMock()
        add_devices = mock.MagicMock()

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

        result = honeywell.setup_platform(hass, config, add_devices)
        self.assertTrue(result)
        mock_sc.assert_called_once_with('user', 'pass')
        mock_ht.assert_has_calls([
            mock.call(mock_sc.return_value, devices_1[0]),
            mock.call(mock_sc.return_value, devices_2[0]),
            mock.call(mock_sc.return_value, devices_2[1]),
        ])

    @mock.patch('somecomfort.SomeComfort')
    def test_setup_us_failures(self, mock_sc):
        hass = mock.MagicMock()
        add_devices = mock.MagicMock()
        config = {
            CONF_USERNAME: 'user',
            CONF_PASSWORD: 'pass',
            'region': 'us',
        }

        mock_sc.side_effect = somecomfort.AuthError
        result = honeywell.setup_platform(hass, config, add_devices)
        self.assertFalse(result)
        self.assertFalse(add_devices.called)

        mock_sc.side_effect = somecomfort.SomeComfortError
        result = honeywell.setup_platform(hass, config, add_devices)
        self.assertFalse(result)
        self.assertFalse(add_devices.called)

    @mock.patch('somecomfort.SomeComfort')
    @mock.patch('homeassistant.components.thermostat.'
                'honeywell.HoneywellUSThermostat')
    def _test_us_filtered_devices(self, mock_ht, mock_sc, loc=None, dev=None):
        config = {
            CONF_USERNAME: 'user',
            CONF_PASSWORD: 'pass',
            'region': 'us',
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
        add_devices = mock.MagicMock()
        self.assertEqual(True,
                         honeywell.setup_platform(hass, config, add_devices))

        return mock_ht.call_args_list, mock_sc

    def test_us_filtered_thermostat_1(self):
        result, client = self._test_us_filtered_devices(
            dev=mock.sentinel.loc1dev1)
        devices = [x[0][1].deviceid for x in result]
        self.assertEqual([mock.sentinel.loc1dev1], devices)

    def test_us_filtered_thermostat_2(self):
        result, client = self._test_us_filtered_devices(
            dev=mock.sentinel.loc2dev1)
        devices = [x[0][1].deviceid for x in result]
        self.assertEqual([mock.sentinel.loc2dev1], devices)

    def test_us_filtered_location_1(self):
        result, client = self._test_us_filtered_devices(
            loc=mock.sentinel.loc1)
        devices = [x[0][1].deviceid for x in result]
        self.assertEqual([mock.sentinel.loc1dev1,
                          mock.sentinel.loc1dev2], devices)

    def test_us_filtered_location_2(self):
        result, client = self._test_us_filtered_devices(
            loc=mock.sentinel.loc2)
        devices = [x[0][1].deviceid for x in result]
        self.assertEqual([mock.sentinel.loc2dev1], devices)


class TestHoneywellUS(unittest.TestCase):
    def setup_method(self, method):
        self.client = mock.MagicMock()
        self.device = mock.MagicMock()
        self.honeywell = honeywell.HoneywellUSThermostat(
            self.client, self.device)

        self.device.fan_running = True
        self.device.name = 'test'
        self.device.temperature_unit = 'F'
        self.device.current_temperature = 72
        self.device.setpoint_cool = 78
        self.device.setpoint_heat = 65
        self.device.system_mode = 'heat'
        self.device.fan_mode = 'auto'

    def test_properties(self):
        self.assertTrue(self.honeywell.is_fan_on)
        self.assertEqual('test', self.honeywell.name)
        self.assertEqual(72, self.honeywell.current_temperature)

    def test_unit_of_measurement(self):
        self.assertEqual(TEMP_FAHRENHEIT, self.honeywell.unit_of_measurement)
        self.device.temperature_unit = 'C'
        self.assertEqual(TEMP_CELCIUS, self.honeywell.unit_of_measurement)

    def test_target_temp(self):
        self.assertEqual(65, self.honeywell.target_temperature)
        self.device.system_mode = 'cool'
        self.assertEqual(78, self.honeywell.target_temperature)

    def test_set_temp(self):
        self.honeywell.set_temperature(70)
        self.assertEqual(70, self.device.setpoint_heat)
        self.assertEqual(70, self.honeywell.target_temperature)

        self.device.system_mode = 'cool'
        self.assertEqual(78, self.honeywell.target_temperature)
        self.honeywell.set_temperature(74)
        self.assertEqual(74, self.device.setpoint_cool)
        self.assertEqual(74, self.honeywell.target_temperature)

    def test_set_temp_fail(self):
        self.device.setpoint_heat = mock.MagicMock(
            side_effect=somecomfort.SomeComfortError)
        self.honeywell.set_temperature(123)

    def test_attributes(self):
        expected = {
            'fan': 'running',
            'fanmode': 'auto',
            'system_mode': 'heat',
        }
        self.assertEqual(expected, self.honeywell.device_state_attributes)
        expected['fan'] = 'idle'
        self.device.fan_running = False
        self.assertEqual(expected, self.honeywell.device_state_attributes)
