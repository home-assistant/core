"""The test for the Ecobee thermostat module."""
import unittest
from unittest import mock
import homeassistant.const as const
import homeassistant.components.climate.ecobee as ecobee
from homeassistant.components.climate import STATE_OFF


class TestEcobee(unittest.TestCase):
    """Tests for Ecobee climate."""

    def setUp(self):
        """Set up test variables."""
        vals = {'name': 'Ecobee',
                'program': {'climates': [{'name': 'Climate1',
                                          'climateRef': 'c1'},
                                         {'name': 'Climate2',
                                          'climateRef': 'c2'}],
                            'currentClimateRef': 'c1'},
                'runtime': {'actualTemperature': 300,
                            'actualHumidity': 15,
                            'desiredHeat': 400,
                            'desiredCool': 200,
                            'desiredFanMode': 'on'},
                'settings': {'hvacMode': 'auto',
                             'fanMinOnTime': 10,
                             'heatCoolMinDelta': 50,
                             'holdAction': 'nextTransition'},
                'equipmentStatus': 'fan',
                'events': [{'name': 'Event1',
                            'running': True,
                            'type': 'hold',
                            'holdClimateRef': 'away',
                            'endDate': '2017-01-01 10:00:00',
                            'startDate': '2017-02-02 11:00:00'}]}

        self.ecobee = mock.Mock()
        self.ecobee.__getitem__ = mock.Mock(side_effect=vals.__getitem__)
        self.ecobee.__setitem__ = mock.Mock(side_effect=vals.__setitem__)

        self.data = mock.Mock()
        self.data.ecobee.get_thermostat.return_value = self.ecobee
        self.thermostat = ecobee.Thermostat(self.data, 1, False)

    def test_name(self):
        """Test name property."""
        self.assertEqual('Ecobee', self.thermostat.name)

    def test_temperature_unit(self):
        """Test temperature unit property."""
        self.assertEqual(const.TEMP_FAHRENHEIT,
                         self.thermostat.temperature_unit)

    def test_current_temperature(self):
        """Test current temperature."""
        self.assertEqual(30, self.thermostat.current_temperature)
        self.ecobee['runtime']['actualTemperature'] = 404
        self.assertEqual(40.4, self.thermostat.current_temperature)

    def test_target_temperature_low(self):
        """Test target low temperature."""
        self.assertEqual(40, self.thermostat.target_temperature_low)
        self.ecobee['runtime']['desiredHeat'] = 502
        self.assertEqual(50.2, self.thermostat.target_temperature_low)

    def test_target_temperature_high(self):
        """Test target high temperature."""
        self.assertEqual(20, self.thermostat.target_temperature_high)
        self.ecobee['runtime']['desiredCool'] = 103
        self.assertEqual(10.3, self.thermostat.target_temperature_high)

    def test_target_temperature(self):
        """Test target temperature."""
        self.assertIsNone(self.thermostat.target_temperature)
        self.ecobee['settings']['hvacMode'] = 'heat'
        self.assertEqual(40, self.thermostat.target_temperature)
        self.ecobee['settings']['hvacMode'] = 'cool'
        self.assertEqual(20, self.thermostat.target_temperature)
        self.ecobee['settings']['hvacMode'] = 'auxHeatOnly'
        self.assertEqual(40, self.thermostat.target_temperature)
        self.ecobee['settings']['hvacMode'] = 'off'
        self.assertIsNone(self.thermostat.target_temperature)

    def test_desired_fan_mode(self):
        """Test desired fan mode property."""
        self.assertEqual('on', self.thermostat.current_fan_mode)
        self.ecobee['runtime']['desiredFanMode'] = 'auto'
        self.assertEqual('auto', self.thermostat.current_fan_mode)

    def test_fan(self):
        """Test fan property."""
        self.assertEqual(const.STATE_ON, self.thermostat.fan)
        self.ecobee['equipmentStatus'] = ''
        self.assertEqual(STATE_OFF, self.thermostat.fan)
        self.ecobee['equipmentStatus'] = 'heatPump, heatPump2'
        self.assertEqual(STATE_OFF, self.thermostat.fan)

    def test_current_hold_mode_away_temporary(self):
        """Test current hold mode when away."""
        # Temporary away hold
        self.assertEqual('away', self.thermostat.current_hold_mode)
        self.ecobee['events'][0]['endDate'] = '2018-01-01 09:49:00'
        self.assertEqual('away', self.thermostat.current_hold_mode)

    def test_current_hold_mode_away_permanent(self):
        """Test current hold mode when away permanently."""
        # Permanent away hold
        self.ecobee['events'][0]['endDate'] = '2019-01-01 10:17:00'
        self.assertIsNone(self.thermostat.current_hold_mode)

    def test_current_hold_mode_no_running_events(self):
        """Test current hold mode when no running events."""
        # No running events
        self.ecobee['events'][0]['running'] = False
        self.assertIsNone(self.thermostat.current_hold_mode)

    def test_current_hold_mode_vacation(self):
        """Test current hold mode when on vacation."""
        # Vacation Hold
        self.ecobee['events'][0]['type'] = 'vacation'
        self.assertEqual('vacation', self.thermostat.current_hold_mode)

    def test_current_hold_mode_climate(self):
        """Test current hold mode when heat climate is set."""
        # Preset climate hold
        self.ecobee['events'][0]['type'] = 'hold'
        self.ecobee['events'][0]['holdClimateRef'] = 'heatClimate'
        self.assertEqual('heatClimate', self.thermostat.current_hold_mode)

    def test_current_hold_mode_temperature_hold(self):
        """Test current hold mode when temperature hold is set."""
        # Temperature hold
        self.ecobee['events'][0]['type'] = 'hold'
        self.ecobee['events'][0]['holdClimateRef'] = ''
        self.assertEqual('temp', self.thermostat.current_hold_mode)

    def test_current_hold_mode_auto_hold(self):
        """Test current hold mode when auto heat is set."""
        # auto Hold
        self.ecobee['events'][0]['type'] = 'autoHeat'
        self.assertEqual('heat', self.thermostat.current_hold_mode)

    def test_current_operation(self):
        """Test current operation property."""
        self.assertEqual('auto', self.thermostat.current_operation)
        self.ecobee['settings']['hvacMode'] = 'heat'
        self.assertEqual('heat', self.thermostat.current_operation)
        self.ecobee['settings']['hvacMode'] = 'cool'
        self.assertEqual('cool', self.thermostat.current_operation)
        self.ecobee['settings']['hvacMode'] = 'auxHeatOnly'
        self.assertEqual('heat', self.thermostat.current_operation)
        self.ecobee['settings']['hvacMode'] = 'off'
        self.assertEqual('off', self.thermostat.current_operation)

    def test_operation_list(self):
        """Test operation list property."""
        self.assertEqual(['auto', 'auxHeatOnly', 'cool',
                          'heat', 'off'], self.thermostat.operation_list)

    def test_operation_mode(self):
        """Test operation mode property."""
        self.assertEqual('auto', self.thermostat.operation_mode)
        self.ecobee['settings']['hvacMode'] = 'heat'
        self.assertEqual('heat', self.thermostat.operation_mode)

    def test_mode(self):
        """Test mode property."""
        self.assertEqual('Climate1', self.thermostat.mode)
        self.ecobee['program']['currentClimateRef'] = 'c2'
        self.assertEqual('Climate2', self.thermostat.mode)

    def test_fan_min_on_time(self):
        """Test fan min on time property."""
        self.assertEqual(10, self.thermostat.fan_min_on_time)
        self.ecobee['settings']['fanMinOnTime'] = 100
        self.assertEqual(100, self.thermostat.fan_min_on_time)

    def test_device_state_attributes(self):
        """Test device state attributes property."""
        self.ecobee['equipmentStatus'] = 'heatPump2'
        self.assertEqual({'actual_humidity': 15,
                          'climate_list': ['Climate1', 'Climate2'],
                          'fan': 'off',
                          'fan_min_on_time': 10,
                          'climate_mode': 'Climate1',
                          'operation': 'heat'},
                         self.thermostat.device_state_attributes)

        self.ecobee['equipmentStatus'] = 'auxHeat2'
        self.assertEqual({'actual_humidity': 15,
                          'climate_list': ['Climate1', 'Climate2'],
                          'fan': 'off',
                          'fan_min_on_time': 10,
                          'climate_mode': 'Climate1',
                          'operation': 'heat'},
                         self.thermostat.device_state_attributes)
        self.ecobee['equipmentStatus'] = 'compCool1'
        self.assertEqual({'actual_humidity': 15,
                          'climate_list': ['Climate1', 'Climate2'],
                          'fan': 'off',
                          'fan_min_on_time': 10,
                          'climate_mode': 'Climate1',
                          'operation': 'cool'},
                         self.thermostat.device_state_attributes)
        self.ecobee['equipmentStatus'] = ''
        self.assertEqual({'actual_humidity': 15,
                          'climate_list': ['Climate1', 'Climate2'],
                          'fan': 'off',
                          'fan_min_on_time': 10,
                          'climate_mode': 'Climate1',
                          'operation': 'idle'},
                         self.thermostat.device_state_attributes)

        self.ecobee['equipmentStatus'] = 'Unknown'
        self.assertEqual({'actual_humidity': 15,
                          'climate_list': ['Climate1', 'Climate2'],
                          'fan': 'off',
                          'fan_min_on_time': 10,
                          'climate_mode': 'Climate1',
                          'operation': 'Unknown'},
                         self.thermostat.device_state_attributes)

    def test_is_away_mode_on(self):
        """Test away mode property."""
        self.assertFalse(self.thermostat.is_away_mode_on)
        # Temporary away hold
        self.ecobee['events'][0]['endDate'] = '2018-01-01 11:12:12'
        self.assertFalse(self.thermostat.is_away_mode_on)
        # Permanent away hold
        self.ecobee['events'][0]['endDate'] = '2019-01-01 13:12:12'
        self.assertTrue(self.thermostat.is_away_mode_on)
        # No running events
        self.ecobee['events'][0]['running'] = False
        self.assertFalse(self.thermostat.is_away_mode_on)
        # Vacation Hold
        self.ecobee['events'][0]['type'] = 'vacation'
        self.assertFalse(self.thermostat.is_away_mode_on)
        # Preset climate hold
        self.ecobee['events'][0]['type'] = 'hold'
        self.ecobee['events'][0]['holdClimateRef'] = 'heatClimate'
        self.assertFalse(self.thermostat.is_away_mode_on)
        # Temperature hold
        self.ecobee['events'][0]['type'] = 'hold'
        self.ecobee['events'][0]['holdClimateRef'] = ''
        self.assertFalse(self.thermostat.is_away_mode_on)
        # auto Hold
        self.ecobee['events'][0]['type'] = 'autoHeat'
        self.assertFalse(self.thermostat.is_away_mode_on)

    def test_is_aux_heat_on(self):
        """Test aux heat property."""
        self.assertFalse(self.thermostat.is_aux_heat_on)
        self.ecobee['equipmentStatus'] = 'fan, auxHeat'
        self.assertTrue(self.thermostat.is_aux_heat_on)

    def test_turn_away_mode_on_off(self):
        """Test turn away mode setter."""
        self.data.reset_mock()
        # Turn on first while the current hold mode is not away hold
        self.thermostat.turn_away_mode_on()
        self.data.ecobee.set_climate_hold.assert_has_calls(
            [mock.call(1, 'away', 'indefinite')])

        # Try with away hold
        self.data.reset_mock()
        self.ecobee['events'][0]['endDate'] = '2019-01-01 11:12:12'
        # Should not call set_climate_hold()
        self.assertFalse(self.data.ecobee.set_climate_hold.called)

        # Try turning off while hold mode is away hold
        self.data.reset_mock()
        self.thermostat.turn_away_mode_off()
        self.data.ecobee.resume_program.assert_has_calls([mock.call(1)])

        # Try turning off when it has already been turned off
        self.data.reset_mock()
        self.ecobee['events'][0]['endDate'] = '2017-01-01 14:00:00'
        self.thermostat.turn_away_mode_off()
        self.assertFalse(self.data.ecobee.resume_program.called)

    def test_set_hold_mode(self):
        """Test hold mode setter."""
        # Test same hold mode
        # Away->Away
        self.data.reset_mock()
        self.thermostat.set_hold_mode('away')
        self.assertFalse(self.data.ecobee.delete_vacation.called)
        self.assertFalse(self.data.ecobee.resume_program.called)
        self.assertFalse(self.data.ecobee.set_hold_temp.called)
        self.assertFalse(self.data.ecobee.set_climate_hold.called)

        # Away->'None'
        self.data.reset_mock()
        self.thermostat.set_hold_mode('None')
        self.assertFalse(self.data.ecobee.delete_vacation.called)
        self.data.ecobee.resume_program.assert_has_calls([mock.call(1)])
        self.assertFalse(self.data.ecobee.set_hold_temp.called)
        self.assertFalse(self.data.ecobee.set_climate_hold.called)

        # Vacation Hold -> None
        self.ecobee['events'][0]['type'] = 'vacation'
        self.data.reset_mock()
        self.thermostat.set_hold_mode(None)
        self.data.ecobee.delete_vacation.assert_has_calls(
            [mock.call(1, 'Event1')])
        self.assertFalse(self.data.ecobee.resume_program.called)
        self.assertFalse(self.data.ecobee.set_hold_temp.called)
        self.assertFalse(self.data.ecobee.set_climate_hold.called)

        # Away -> home, sleep
        for hold in ['home', 'sleep']:
            self.data.reset_mock()
            self.thermostat.set_hold_mode(hold)
            self.assertFalse(self.data.ecobee.delete_vacation.called)
            self.assertFalse(self.data.ecobee.resume_program.called)
            self.assertFalse(self.data.ecobee.set_hold_temp.called)
            self.data.ecobee.set_climate_hold.assert_has_calls(
                [mock.call(1, hold, 'nextTransition')])

        # Away -> temp
        self.data.reset_mock()
        self.thermostat.set_hold_mode('temp')
        self.assertFalse(self.data.ecobee.delete_vacation.called)
        self.assertFalse(self.data.ecobee.resume_program.called)
        self.data.ecobee.set_hold_temp.assert_has_calls(
            [mock.call(1, 35.0, 25.0, 'nextTransition')])
        self.assertFalse(self.data.ecobee.set_climate_hold.called)

    def test_set_auto_temp_hold(self):
        """Test auto temp hold setter."""
        self.data.reset_mock()
        self.thermostat.set_auto_temp_hold(20.0, 30)
        self.data.ecobee.set_hold_temp.assert_has_calls(
            [mock.call(1, 30, 20.0, 'nextTransition')])

    def test_set_temp_hold(self):
        """Test temp hold setter."""
        # Away mode or any mode other than heat or cool
        self.data.reset_mock()
        self.thermostat.set_temp_hold(30.0)
        self.data.ecobee.set_hold_temp.assert_has_calls(
            [mock.call(1, 35.0, 25.0, 'nextTransition')])

        # Heat mode
        self.data.reset_mock()
        self.ecobee['settings']['hvacMode'] = 'heat'
        self.thermostat.set_temp_hold(30)
        self.data.ecobee.set_hold_temp.assert_has_calls(
            [mock.call(1, 30, 30, 'nextTransition')])

        # Cool mode
        self.data.reset_mock()
        self.ecobee['settings']['hvacMode'] = 'cool'
        self.thermostat.set_temp_hold(30)
        self.data.ecobee.set_hold_temp.assert_has_calls(
            [mock.call(1, 30, 30, 'nextTransition')])

    def test_set_temperature(self):
        """Test set temperature."""
        # Auto -> Auto
        self.data.reset_mock()
        self.thermostat.set_temperature(target_temp_low=20,
                                        target_temp_high=30)
        self.data.ecobee.set_hold_temp.assert_has_calls(
            [mock.call(1, 30, 20, 'nextTransition')])

        # Auto -> Hold
        self.data.reset_mock()
        self.thermostat.set_temperature(temperature=20)
        self.data.ecobee.set_hold_temp.assert_has_calls(
            [mock.call(1, 25, 15, 'nextTransition')])

        # Cool -> Hold
        self.data.reset_mock()
        self.ecobee['settings']['hvacMode'] = 'cool'
        self.thermostat.set_temperature(temperature=20.5)
        self.data.ecobee.set_hold_temp.assert_has_calls(
            [mock.call(1, 20.5, 20.5, 'nextTransition')])

        # Heat -> Hold
        self.data.reset_mock()
        self.ecobee['settings']['hvacMode'] = 'heat'
        self.thermostat.set_temperature(temperature=20)
        self.data.ecobee.set_hold_temp.assert_has_calls(
            [mock.call(1, 20, 20, 'nextTransition')])

        # Heat -> Auto
        self.data.reset_mock()
        self.ecobee['settings']['hvacMode'] = 'heat'
        self.thermostat.set_temperature(target_temp_low=20,
                                        target_temp_high=30)
        self.assertFalse(self.data.ecobee.set_hold_temp.called)

    def test_set_operation_mode(self):
        """Test operation mode setter."""
        self.data.reset_mock()
        self.thermostat.set_operation_mode('auto')
        self.data.ecobee.set_hvac_mode.assert_has_calls(
            [mock.call(1, 'auto')])
        self.data.reset_mock()
        self.thermostat.set_operation_mode('heat')
        self.data.ecobee.set_hvac_mode.assert_has_calls(
            [mock.call(1, 'heat')])

    def test_set_fan_min_on_time(self):
        """Test fan min on time setter."""
        self.data.reset_mock()
        self.thermostat.set_fan_min_on_time(15)
        self.data.ecobee.set_fan_min_on_time.assert_has_calls(
            [mock.call(1, 15)])
        self.data.reset_mock()
        self.thermostat.set_fan_min_on_time(20)
        self.data.ecobee.set_fan_min_on_time.assert_has_calls(
            [mock.call(1, 20)])

    def test_resume_program(self):
        """Test resume program."""
        # False
        self.data.reset_mock()
        self.thermostat.resume_program(False)
        self.data.ecobee.resume_program.assert_has_calls(
            [mock.call(1, 'false')])
        self.data.reset_mock()
        self.thermostat.resume_program(None)
        self.data.ecobee.resume_program.assert_has_calls(
            [mock.call(1, 'false')])
        self.data.reset_mock()
        self.thermostat.resume_program(0)
        self.data.ecobee.resume_program.assert_has_calls(
            [mock.call(1, 'false')])

        # True
        self.data.reset_mock()
        self.thermostat.resume_program(True)
        self.data.ecobee.resume_program.assert_has_calls(
            [mock.call(1, 'true')])
        self.data.reset_mock()
        self.thermostat.resume_program(1)
        self.data.ecobee.resume_program.assert_has_calls(
            [mock.call(1, 'true')])

    def test_hold_preference(self):
        """Test hold preference."""
        self.assertEqual('nextTransition', self.thermostat.hold_preference())
        for action in ['useEndTime4hour', 'useEndTime2hour',
                       'nextPeriod', 'indefinite', 'askMe']:
            self.ecobee['settings']['holdAction'] = action
            self.assertEqual('nextTransition',
                             self.thermostat.hold_preference())

    def test_climate_list(self):
        """Test climate list property."""
        self.assertEqual(['Climate1', 'Climate2'],
                         self.thermostat.climate_list)

    def test_set_fan_mode_on(self):
        """Test set fan mode to on."""
        self.data.reset_mock()
        self.thermostat.set_fan_mode('on')
        self.data.ecobee.set_fan_mode.assert_has_calls(
            [mock.call(1, 'on', 20, 40, 'nextTransition')])

    def test_set_fan_mode_auto(self):
        """Test set fan mode to auto."""
        self.data.reset_mock()
        self.thermostat.set_fan_mode('auto')
        self.data.ecobee.set_fan_mode.assert_has_calls(
            [mock.call(1, 'auto', 20, 40, 'nextTransition')])
