"""The test the Honeywell thermostat module."""
import unittest
from unittest import mock

import pytest
import somecomfort

from homeassistant.components.climate.const import (
    ATTR_FAN_MODE,
    ATTR_FAN_MODES,
    ATTR_HVAC_MODES,
)
import homeassistant.components.honeywell.climate as honeywellClimate
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)

pytestmark = pytest.mark.skip("Need to be fixed!")


class TestHoneywell(unittest.TestCase):
    """A test class for Honeywell themostats."""

    # @mock.patch("somecomfort.SomeComfort")
    # @mock.patch("homeassistant.components.honeywell.climate.HoneywellUSThermostat")
    # def test_setup_us(self, mock_ht, mock_sc):
    #     """Test for the US setup."""
    #     config = {
    #         CONF_USERNAME: "user",
    #         CONF_PASSWORD: "pass",
    #     }
    #     bad_pass_config = {CONF_USERNAME: "user"}
    #     bad_region_config = {
    #         CONF_USERNAME: "user",
    #         CONF_PASSWORD: "pass",
    #     }

    #     with pytest.raises(vol.Invalid):
    #         honeywellClimate.PLATFORM_SCHEMA(None)

    #     with pytest.raises(vol.Invalid):
    #         honeywellClimate.PLATFORM_SCHEMA({})

    #     with pytest.raises(vol.Invalid):
    #         honeywellClimate.PLATFORM_SCHEMA(bad_pass_config)

    #     with pytest.raises(vol.Invalid):
    #         honeywellClimate.PLATFORM_SCHEMA(bad_region_config)

    #     hass = mock.MagicMock()
    #     add_entities = mock.MagicMock()

    #     locations = [mock.MagicMock(), mock.MagicMock()]
    #     devices_1 = [mock.MagicMock()]
    #     devices_2 = [mock.MagicMock(), mock.MagicMock]
    #     mock_sc.return_value.locations_by_id.values.return_value = locations
    #     locations[0].devices_by_id.values.return_value = devices_1
    #     locations[1].devices_by_id.values.return_value = devices_2

    #     result = honeywellClimate.setup_platform(hass, config, add_entities)
    #     assert result
    #     assert mock_sc.call_count == 1
    #     assert mock_sc.call_args == mock.call("user", "pass")
    #     mock_ht.assert_has_calls(
    #         [
    #             mock.call(mock_sc.return_value, devices_1[0], 18, 28, "user", "pass"),
    #             mock.call(mock_sc.return_value, devices_2[0], 18, 28, "user", "pass"),
    #             mock.call(mock_sc.return_value, devices_2[1], 18, 28, "user", "pass"),
    #         ]
    #     )

    @mock.patch("somecomfort.SomeComfort")
    def test_setup_us_failures(self, mock_sc):
        """Test the US setup."""
        hass = mock.MagicMock()
        add_entities = mock.MagicMock()
        config = {
            CONF_USERNAME: "user",
            CONF_PASSWORD: "pass",
        }

        mock_sc.side_effect = somecomfort.AuthError
        honeywellClimate.setup_platform(hass, config, add_entities)
        assert not add_entities.called

        mock_sc.side_effect = somecomfort.SomeComfortError
        honeywellClimate.setup_platform(hass, config, add_entities)
        assert not add_entities.called

    # @mock.patch("somecomfort.SomeComfort")
    # @mock.patch("homeassistant.components.honeywell.climate.HoneywellUSThermostat")
    # def _test_us_filtered_devices(self, mock_ht, mock_sc, loc=None, dev=None):
    #     """Test for US filtered thermostats."""
    #     config = {
    #         CONF_USERNAME: "user",
    #         CONF_PASSWORD: "pass",
    #         "location": loc,
    #         "thermostat": dev,
    #     }
    #     locations = {
    #         1: mock.MagicMock(
    #             locationid=mock.sentinel.loc1,
    #             devices_by_id={
    #                 11: mock.MagicMock(deviceid=mock.sentinel.loc1dev1),
    #                 12: mock.MagicMock(deviceid=mock.sentinel.loc1dev2),
    #             },
    #         ),
    #         2: mock.MagicMock(
    #             locationid=mock.sentinel.loc2,
    #             devices_by_id={21: mock.MagicMock(deviceid=mock.sentinel.loc2dev1)},
    #         ),
    #         3: mock.MagicMock(
    #             locationid=mock.sentinel.loc3,
    #             devices_by_id={31: mock.MagicMock(deviceid=mock.sentinel.loc3dev1)},
    #         ),
    #     }
    #     mock_sc.return_value = mock.MagicMock(locations_by_id=locations)
    #     hass = mock.MagicMock()
    #     add_entities = mock.MagicMock()
    #     assert honeywellClimate.setup_platform(hass, config, add_entities) is True

    #     return mock_ht.call_args_list, mock_sc

    # def test_us_filtered_thermostat_1(self):
    #     """Test for US filtered thermostats."""
    #     result, client = self._test_us_filtered_devices(dev=mock.sentinel.loc1dev1)
    #     devices = [x[0][1].deviceid for x in result]
    #     assert [mock.sentinel.loc1dev1] == devices

    # def test_us_filtered_thermostat_2(self):
    #     """Test for US filtered location."""
    #     result, client = self._test_us_filtered_devices(dev=mock.sentinel.loc2dev1)
    #     devices = [x[0][1].deviceid for x in result]
    #     assert [mock.sentinel.loc2dev1] == devices

    # def test_us_filtered_location_1(self):
    #     """Test for US filtered locations."""
    #     result, client = self._test_us_filtered_devices(loc=mock.sentinel.loc1)
    #     devices = [x[0][1].deviceid for x in result]
    #     assert [mock.sentinel.loc1dev1, mock.sentinel.loc1dev2] == devices

    # def test_us_filtered_location_2(self):
    #     """Test for US filtered locations."""
    #     result, client = self._test_us_filtered_devices(loc=mock.sentinel.loc2)
    #     devices = [x[0][1].deviceid for x in result]
    #     assert [mock.sentinel.loc2dev1] == devices


class TestHoneywellUS(unittest.TestCase):
    """A test class for Honeywell US thermostats."""

    def setup_method(self, method):
        """Test the setup method."""
        self.device = mock.MagicMock()
        self.cool_away_temp = 18
        self.heat_away_temp = 28
        self.honeywell = honeywellClimate.HoneywellUSThermostat(
            self.device,
            self.cool_away_temp,
            self.heat_away_temp,
        )

        self.device.fan_running = True
        self.device.name = "test"
        self.device.temperature_unit = "F"
        self.device.current_temperature = 72
        self.device.setpoint_cool = 78
        self.device.setpoint_heat = 65
        self.device.system_mode = "heat"
        self.device.fan_mode = "auto"

    def test_properties(self):
        """Test the properties."""
        assert self.honeywell.set_fan_mode("on")
        assert self.honeywell.name == "test"
        assert self.honeywell.current_temperature == 72

    def test_unit_of_measurement(self):
        """Test the unit of measurement."""
        assert self.honeywell.temperature_unit == TEMP_FAHRENHEIT
        self.device.temperature_unit = "C"
        assert self.honeywell.temperature_unit == TEMP_CELSIUS

    def test_target_temp(self):
        """Test the target temperature."""
        assert self.honeywell.target_temperature == 65
        self.device.system_mode = "cool"
        assert self.honeywell.target_temperature == 78

    def test_set_temp(self):
        """Test setting the temperature."""
        self.honeywell.set_temperature(temperature=70)
        assert self.device.setpoint_heat == 70
        assert self.honeywell.target_temperature == 70

        self.device.system_mode = "cool"
        assert self.honeywell.target_temperature == 78
        self.honeywell.set_temperature(temperature=74)
        assert self.device.setpoint_cool == 74
        assert self.honeywell.target_temperature == 74

    def test_set_hvac_mode(self) -> None:
        """Test setting the operation mode."""
        self.honeywell.set_hvac_mode("cool")
        assert self.device.system_mode == "cool"

        self.honeywell.set_hvac_mode("heat")
        assert self.device.system_mode == "heat"

    def test_set_temp_fail(self):
        """Test if setting the temperature fails."""
        self.device.setpoint_heat = mock.MagicMock(
            side_effect=somecomfort.SomeComfortError
        )
        self.honeywell.set_temperature(temperature=123)

    def test_attributes(self):
        """Test the attributes."""
        expected = {
            honeywellClimate.ATTR_FAN_ACTION: "running",
            ATTR_FAN_MODE: "auto",
            ATTR_FAN_MODES: somecomfort.FAN_MODES,
            ATTR_HVAC_MODES: somecomfort.SYSTEM_MODES,
        }
        assert expected == self.honeywell.extra_state_attributes
        expected["fan"] = "idle"
        self.device.fan_running = False
        assert self.honeywell.extra_state_attributes == expected

    def test_with_no_fan(self):
        """Test if there is on fan."""
        self.device.fan_running = False
        self.device.fan_mode = None
        expected = {
            honeywellClimate.ATTR_FAN_ACTION: "idle",
            ATTR_FAN_MODE: None,
            ATTR_FAN_MODES: somecomfort.FAN_MODES,
            ATTR_HVAC_MODES: somecomfort.SYSTEM_MODES,
        }
        assert self.honeywell.extra_state_attributes == expected

    def test_heat_away_mode(self):
        """Test setting the heat away mode."""
        self.honeywell.set_hvac_mode("heat")
        assert not self.honeywell._away
        self.honeywell._turn_away_mode_on()
        assert self.honeywell._away
        assert self.device.setpoint_heat == self.heat_away_temp
        assert self.device.hold_heat is True

        self.honeywell._turn_away_mode_off()
        assert not self.honeywell._away
        assert self.device.hold_heat is False

    # @mock.patch("somecomfort.SomeComfort")
    # def test_retry(self, test_somecomfort):
    #     """Test retry connection."""
    #     old_device = self.honeywell._device
    #     self.honeywell._retry()
    #     assert self.honeywell._device == old_device
