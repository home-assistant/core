"""The tests for the demo climate component."""
import unittest

import pytest
import voluptuous as vol

from homeassistant.util.unit_system import (
    METRIC_SYSTEM
)
from homeassistant.setup import setup_component
from homeassistant.components.climate import (
    DOMAIN, SERVICE_TURN_OFF, SERVICE_TURN_ON)
from homeassistant.const import (ATTR_ENTITY_ID)

from tests.common import get_test_home_assistant
from tests.components.climate import common


ENTITY_CLIMATE = 'climate.hvac'
ENTITY_ECOBEE = 'climate.ecobee'
ENTITY_HEATPUMP = 'climate.heatpump'


class TestDemoClimate(unittest.TestCase):
    """Test the demo climate hvac."""

    def setUp(self):  # pylint: disable=invalid-name
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.config.units = METRIC_SYSTEM
        assert setup_component(self.hass, DOMAIN, {
            'climate': {
                'platform': 'demo',
            }})

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop down everything that was started."""
        self.hass.stop()

    def test_setup_params(self):
        """Test the initial parameters."""
        state = self.hass.states.get(ENTITY_CLIMATE)
        assert 21 == state.attributes.get('temperature')
        assert 'on' == state.attributes.get('away_mode')
        assert 22 == state.attributes.get('current_temperature')
        assert "On High" == state.attributes.get('fan_mode')
        assert 67 == state.attributes.get('humidity')
        assert 54 == state.attributes.get('current_humidity')
        assert "Off" == state.attributes.get('swing_mode')
        assert "cool" == state.attributes.get('operation_mode')
        assert 'off' == state.attributes.get('aux_heat')

    def test_default_setup_params(self):
        """Test the setup with default parameters."""
        state = self.hass.states.get(ENTITY_CLIMATE)
        assert 7 == state.attributes.get('min_temp')
        assert 35 == state.attributes.get('max_temp')
        assert 30 == state.attributes.get('min_humidity')
        assert 99 == state.attributes.get('max_humidity')

    def test_set_only_target_temp_bad_attr(self):
        """Test setting the target temperature without required attribute."""
        state = self.hass.states.get(ENTITY_CLIMATE)
        assert 21 == state.attributes.get('temperature')
        with pytest.raises(vol.Invalid):
            common.set_temperature(self.hass, None, ENTITY_CLIMATE)
        self.hass.block_till_done()
        assert 21 == state.attributes.get('temperature')

    def test_set_only_target_temp(self):
        """Test the setting of the target temperature."""
        state = self.hass.states.get(ENTITY_CLIMATE)
        assert 21 == state.attributes.get('temperature')
        common.set_temperature(self.hass, 30, ENTITY_CLIMATE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        assert 30.0 == state.attributes.get('temperature')

    def test_set_only_target_temp_with_convert(self):
        """Test the setting of the target temperature."""
        state = self.hass.states.get(ENTITY_HEATPUMP)
        assert 20 == state.attributes.get('temperature')
        common.set_temperature(self.hass, 21, ENTITY_HEATPUMP)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_HEATPUMP)
        assert 21.0 == state.attributes.get('temperature')

    def test_set_target_temp_range(self):
        """Test the setting of the target temperature with range."""
        state = self.hass.states.get(ENTITY_ECOBEE)
        assert state.attributes.get('temperature') is None
        assert 21.0 == state.attributes.get('target_temp_low')
        assert 24.0 == state.attributes.get('target_temp_high')
        common.set_temperature(self.hass, target_temp_high=25,
                               target_temp_low=20, entity_id=ENTITY_ECOBEE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_ECOBEE)
        assert state.attributes.get('temperature') is None
        assert 20.0 == state.attributes.get('target_temp_low')
        assert 25.0 == state.attributes.get('target_temp_high')

    def test_set_target_temp_range_bad_attr(self):
        """Test setting the target temperature range without attribute."""
        state = self.hass.states.get(ENTITY_ECOBEE)
        assert state.attributes.get('temperature') is None
        assert 21.0 == state.attributes.get('target_temp_low')
        assert 24.0 == state.attributes.get('target_temp_high')
        with pytest.raises(vol.Invalid):
            common.set_temperature(self.hass, temperature=None,
                                   entity_id=ENTITY_ECOBEE,
                                   target_temp_low=None,
                                   target_temp_high=None)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_ECOBEE)
        assert state.attributes.get('temperature') is None
        assert 21.0 == state.attributes.get('target_temp_low')
        assert 24.0 == state.attributes.get('target_temp_high')

    def test_set_target_humidity_bad_attr(self):
        """Test setting the target humidity without required attribute."""
        state = self.hass.states.get(ENTITY_CLIMATE)
        assert 67 == state.attributes.get('humidity')
        with pytest.raises(vol.Invalid):
            common.set_humidity(self.hass, None, ENTITY_CLIMATE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        assert 67 == state.attributes.get('humidity')

    def test_set_target_humidity(self):
        """Test the setting of the target humidity."""
        state = self.hass.states.get(ENTITY_CLIMATE)
        assert 67 == state.attributes.get('humidity')
        common.set_humidity(self.hass, 64, ENTITY_CLIMATE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        assert 64.0 == state.attributes.get('humidity')

    def test_set_fan_mode_bad_attr(self):
        """Test setting fan mode without required attribute."""
        state = self.hass.states.get(ENTITY_CLIMATE)
        assert "On High" == state.attributes.get('fan_mode')
        with pytest.raises(vol.Invalid):
            common.set_fan_mode(self.hass, None, ENTITY_CLIMATE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        assert "On High" == state.attributes.get('fan_mode')

    def test_set_fan_mode(self):
        """Test setting of new fan mode."""
        state = self.hass.states.get(ENTITY_CLIMATE)
        assert "On High" == state.attributes.get('fan_mode')
        common.set_fan_mode(self.hass, "On Low", ENTITY_CLIMATE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        assert "On Low" == state.attributes.get('fan_mode')

    def test_set_swing_mode_bad_attr(self):
        """Test setting swing mode without required attribute."""
        state = self.hass.states.get(ENTITY_CLIMATE)
        assert "Off" == state.attributes.get('swing_mode')
        with pytest.raises(vol.Invalid):
            common.set_swing_mode(self.hass, None, ENTITY_CLIMATE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        assert "Off" == state.attributes.get('swing_mode')

    def test_set_swing(self):
        """Test setting of new swing mode."""
        state = self.hass.states.get(ENTITY_CLIMATE)
        assert "Off" == state.attributes.get('swing_mode')
        common.set_swing_mode(self.hass, "Auto", ENTITY_CLIMATE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        assert "Auto" == state.attributes.get('swing_mode')

    def test_set_operation_bad_attr_and_state(self):
        """Test setting operation mode without required attribute.

        Also check the state.
        """
        state = self.hass.states.get(ENTITY_CLIMATE)
        assert "cool" == state.attributes.get('operation_mode')
        assert "cool" == state.state
        with pytest.raises(vol.Invalid):
            common.set_operation_mode(self.hass, None, ENTITY_CLIMATE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        assert "cool" == state.attributes.get('operation_mode')
        assert "cool" == state.state

    def test_set_operation(self):
        """Test setting of new operation mode."""
        state = self.hass.states.get(ENTITY_CLIMATE)
        assert "cool" == state.attributes.get('operation_mode')
        assert "cool" == state.state
        common.set_operation_mode(self.hass, "heat", ENTITY_CLIMATE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        assert "heat" == state.attributes.get('operation_mode')
        assert "heat" == state.state

    def test_set_away_mode_bad_attr(self):
        """Test setting the away mode without required attribute."""
        state = self.hass.states.get(ENTITY_CLIMATE)
        assert 'on' == state.attributes.get('away_mode')
        common.set_away_mode(self.hass, None, ENTITY_CLIMATE)
        self.hass.block_till_done()
        assert 'on' == state.attributes.get('away_mode')

    def test_set_away_mode_on(self):
        """Test setting the away mode on/true."""
        common.set_away_mode(self.hass, True, ENTITY_CLIMATE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        assert 'on' == state.attributes.get('away_mode')

    def test_set_away_mode_off(self):
        """Test setting the away mode off/false."""
        common.set_away_mode(self.hass, False, ENTITY_CLIMATE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        assert 'off' == state.attributes.get('away_mode')

    def test_set_hold_mode_home(self):
        """Test setting the hold mode home."""
        common.set_hold_mode(self.hass, 'home', ENTITY_ECOBEE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_ECOBEE)
        assert 'home' == state.attributes.get('hold_mode')

    def test_set_hold_mode_away(self):
        """Test setting the hold mode away."""
        common.set_hold_mode(self.hass, 'away', ENTITY_ECOBEE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_ECOBEE)
        assert 'away' == state.attributes.get('hold_mode')

    def test_set_hold_mode_none(self):
        """Test setting the hold mode off/false."""
        common.set_hold_mode(self.hass, 'off', ENTITY_ECOBEE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_ECOBEE)
        assert 'off' == state.attributes.get('hold_mode')

    def test_set_aux_heat_bad_attr(self):
        """Test setting the auxiliary heater without required attribute."""
        state = self.hass.states.get(ENTITY_CLIMATE)
        assert 'off' == state.attributes.get('aux_heat')
        common.set_aux_heat(self.hass, None, ENTITY_CLIMATE)
        self.hass.block_till_done()
        assert 'off' == state.attributes.get('aux_heat')

    def test_set_aux_heat_on(self):
        """Test setting the axillary heater on/true."""
        common.set_aux_heat(self.hass, True, ENTITY_CLIMATE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        assert 'on' == state.attributes.get('aux_heat')

    def test_set_aux_heat_off(self):
        """Test setting the auxiliary heater off/false."""
        common.set_aux_heat(self.hass, False, ENTITY_CLIMATE)
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_CLIMATE)
        assert 'off' == state.attributes.get('aux_heat')

    def test_set_on_off(self):
        """Test on/off service."""
        state = self.hass.states.get(ENTITY_ECOBEE)
        assert 'auto' == state.state

        self.hass.services.call(DOMAIN, SERVICE_TURN_OFF,
                                {ATTR_ENTITY_ID: ENTITY_ECOBEE})
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_ECOBEE)
        assert 'off' == state.state

        self.hass.services.call(DOMAIN, SERVICE_TURN_ON,
                                {ATTR_ENTITY_ID: ENTITY_ECOBEE})
        self.hass.block_till_done()
        state = self.hass.states.get(ENTITY_ECOBEE)
        assert 'auto' == state.state
