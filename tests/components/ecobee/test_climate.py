"""The test for the Ecobee thermostat module."""
import unittest
from unittest import mock

from homeassistant.components.ecobee import climate as ecobee
import homeassistant.const as const
from homeassistant.const import STATE_OFF


class TestEcobee(unittest.TestCase):
    """Tests for Ecobee climate."""

    def setUp(self):
        """Set up test variables."""
        vals = {
            "name": "Ecobee",
            "program": {
                "climates": [
                    {"name": "Climate1", "climateRef": "c1"},
                    {"name": "Climate2", "climateRef": "c2"},
                ],
                "currentClimateRef": "c1",
            },
            "runtime": {
                "actualTemperature": 300,
                "actualHumidity": 15,
                "desiredHeat": 400,
                "desiredCool": 200,
                "desiredFanMode": "on",
            },
            "settings": {
                "hvacMode": "auto",
                "heatStages": 1,
                "coolStages": 1,
                "fanMinOnTime": 10,
                "heatCoolMinDelta": 50,
                "holdAction": "nextTransition",
            },
            "equipmentStatus": "fan",
            "events": [
                {
                    "name": "Event1",
                    "running": True,
                    "type": "hold",
                    "holdClimateRef": "away",
                    "endDate": "2017-01-01 10:00:00",
                    "startDate": "2017-02-02 11:00:00",
                }
            ],
        }

        self.ecobee = mock.Mock()
        self.ecobee.__getitem__ = mock.Mock(side_effect=vals.__getitem__)
        self.ecobee.__setitem__ = mock.Mock(side_effect=vals.__setitem__)

        self.data = mock.Mock()
        self.data.ecobee.get_thermostat.return_value = self.ecobee
        self.thermostat = ecobee.Thermostat(self.data, 1)

    def test_name(self):
        """Test name property."""
        assert "Ecobee" == self.thermostat.name

    def test_current_temperature(self):
        """Test current temperature."""
        assert 30 == self.thermostat.current_temperature
        self.ecobee["runtime"]["actualTemperature"] = const.HTTP_NOT_FOUND
        assert 40.4 == self.thermostat.current_temperature

    def test_target_temperature_low(self):
        """Test target low temperature."""
        assert 40 == self.thermostat.target_temperature_low
        self.ecobee["runtime"]["desiredHeat"] = 502
        assert 50.2 == self.thermostat.target_temperature_low

    def test_target_temperature_high(self):
        """Test target high temperature."""
        assert 20 == self.thermostat.target_temperature_high
        self.ecobee["runtime"]["desiredCool"] = 103
        assert 10.3 == self.thermostat.target_temperature_high

    def test_target_temperature(self):
        """Test target temperature."""
        assert self.thermostat.target_temperature is None
        self.ecobee["settings"]["hvacMode"] = "heat"
        assert 40 == self.thermostat.target_temperature
        self.ecobee["settings"]["hvacMode"] = "cool"
        assert 20 == self.thermostat.target_temperature
        self.ecobee["settings"]["hvacMode"] = "auxHeatOnly"
        assert 40 == self.thermostat.target_temperature
        self.ecobee["settings"]["hvacMode"] = "off"
        assert self.thermostat.target_temperature is None

    def test_desired_fan_mode(self):
        """Test desired fan mode property."""
        assert "on" == self.thermostat.fan_mode
        self.ecobee["runtime"]["desiredFanMode"] = "auto"
        assert "auto" == self.thermostat.fan_mode

    def test_fan(self):
        """Test fan property."""
        assert const.STATE_ON == self.thermostat.fan
        self.ecobee["equipmentStatus"] = ""
        assert STATE_OFF == self.thermostat.fan
        self.ecobee["equipmentStatus"] = "heatPump, heatPump2"
        assert STATE_OFF == self.thermostat.fan

    def test_hvac_mode(self):
        """Test current operation property."""
        assert "auto" == self.thermostat.hvac_mode
        self.ecobee["settings"]["hvacMode"] = "heat"
        assert "heat" == self.thermostat.hvac_mode
        self.ecobee["settings"]["hvacMode"] = "cool"
        assert "cool" == self.thermostat.hvac_mode
        self.ecobee["settings"]["hvacMode"] = "auxHeatOnly"
        assert "heat" == self.thermostat.hvac_mode
        self.ecobee["settings"]["hvacMode"] = "off"
        assert "off" == self.thermostat.hvac_mode

    def test_hvac_modes(self):
        """Test operation list property."""
        assert ["auto", "heat", "cool", "off"] == self.thermostat.hvac_modes

    def test_hvac_mode2(self):
        """Test operation mode property."""
        assert "auto" == self.thermostat.hvac_mode
        self.ecobee["settings"]["hvacMode"] = "heat"
        assert "heat" == self.thermostat.hvac_mode

    def test_device_state_attributes(self):
        """Test device state attributes property."""
        self.ecobee["equipmentStatus"] = "heatPump2"
        assert {
            "fan": "off",
            "climate_mode": "Climate1",
            "fan_min_on_time": 10,
            "equipment_running": "heatPump2",
        } == self.thermostat.device_state_attributes

        self.ecobee["equipmentStatus"] = "auxHeat2"
        assert {
            "fan": "off",
            "climate_mode": "Climate1",
            "fan_min_on_time": 10,
            "equipment_running": "auxHeat2",
        } == self.thermostat.device_state_attributes
        self.ecobee["equipmentStatus"] = "compCool1"
        assert {
            "fan": "off",
            "climate_mode": "Climate1",
            "fan_min_on_time": 10,
            "equipment_running": "compCool1",
        } == self.thermostat.device_state_attributes
        self.ecobee["equipmentStatus"] = ""
        assert {
            "fan": "off",
            "climate_mode": "Climate1",
            "fan_min_on_time": 10,
            "equipment_running": "",
        } == self.thermostat.device_state_attributes

        self.ecobee["equipmentStatus"] = "Unknown"
        assert {
            "fan": "off",
            "climate_mode": "Climate1",
            "fan_min_on_time": 10,
            "equipment_running": "Unknown",
        } == self.thermostat.device_state_attributes

        self.ecobee["program"]["currentClimateRef"] = "c2"
        assert {
            "fan": "off",
            "climate_mode": "Climate2",
            "fan_min_on_time": 10,
            "equipment_running": "Unknown",
        } == self.thermostat.device_state_attributes

    def test_is_aux_heat_on(self):
        """Test aux heat property."""
        assert not self.thermostat.is_aux_heat
        self.ecobee["equipmentStatus"] = "fan, auxHeat"
        assert self.thermostat.is_aux_heat

    def test_set_temperature(self):
        """Test set temperature."""
        # Auto -> Auto
        self.data.reset_mock()
        self.thermostat.set_temperature(target_temp_low=20, target_temp_high=30)
        self.data.ecobee.set_hold_temp.assert_has_calls(
            [mock.call(1, 30, 20, "nextTransition")]
        )

        # Auto -> Hold
        self.data.reset_mock()
        self.thermostat.set_temperature(temperature=20)
        self.data.ecobee.set_hold_temp.assert_has_calls(
            [mock.call(1, 25, 15, "nextTransition")]
        )

        # Cool -> Hold
        self.data.reset_mock()
        self.ecobee["settings"]["hvacMode"] = "cool"
        self.thermostat.set_temperature(temperature=20.5)
        self.data.ecobee.set_hold_temp.assert_has_calls(
            [mock.call(1, 20.5, 20.5, "nextTransition")]
        )

        # Heat -> Hold
        self.data.reset_mock()
        self.ecobee["settings"]["hvacMode"] = "heat"
        self.thermostat.set_temperature(temperature=20)
        self.data.ecobee.set_hold_temp.assert_has_calls(
            [mock.call(1, 20, 20, "nextTransition")]
        )

        # Heat -> Auto
        self.data.reset_mock()
        self.ecobee["settings"]["hvacMode"] = "heat"
        self.thermostat.set_temperature(target_temp_low=20, target_temp_high=30)
        assert not self.data.ecobee.set_hold_temp.called

    def test_set_hvac_mode(self):
        """Test operation mode setter."""
        self.data.reset_mock()
        self.thermostat.set_hvac_mode("auto")
        self.data.ecobee.set_hvac_mode.assert_has_calls([mock.call(1, "auto")])
        self.data.reset_mock()
        self.thermostat.set_hvac_mode("heat")
        self.data.ecobee.set_hvac_mode.assert_has_calls([mock.call(1, "heat")])

    def test_set_fan_min_on_time(self):
        """Test fan min on time setter."""
        self.data.reset_mock()
        self.thermostat.set_fan_min_on_time(15)
        self.data.ecobee.set_fan_min_on_time.assert_has_calls([mock.call(1, 15)])
        self.data.reset_mock()
        self.thermostat.set_fan_min_on_time(20)
        self.data.ecobee.set_fan_min_on_time.assert_has_calls([mock.call(1, 20)])

    def test_resume_program(self):
        """Test resume program."""
        # False
        self.data.reset_mock()
        self.thermostat.resume_program(False)
        self.data.ecobee.resume_program.assert_has_calls([mock.call(1, "false")])
        self.data.reset_mock()
        self.thermostat.resume_program(None)
        self.data.ecobee.resume_program.assert_has_calls([mock.call(1, "false")])
        self.data.reset_mock()
        self.thermostat.resume_program(0)
        self.data.ecobee.resume_program.assert_has_calls([mock.call(1, "false")])

        # True
        self.data.reset_mock()
        self.thermostat.resume_program(True)
        self.data.ecobee.resume_program.assert_has_calls([mock.call(1, "true")])
        self.data.reset_mock()
        self.thermostat.resume_program(1)
        self.data.ecobee.resume_program.assert_has_calls([mock.call(1, "true")])

    def test_hold_preference(self):
        """Test hold preference."""
        assert "nextTransition" == self.thermostat.hold_preference()
        for action in [
            "useEndTime4hour",
            "useEndTime2hour",
            "nextPeriod",
            "indefinite",
            "askMe",
        ]:
            self.ecobee["settings"]["holdAction"] = action
            assert "nextTransition" == self.thermostat.hold_preference()

    def test_set_fan_mode_on(self):
        """Test set fan mode to on."""
        self.data.reset_mock()
        self.thermostat.set_fan_mode("on")
        self.data.ecobee.set_fan_mode.assert_has_calls(
            [mock.call(1, "on", 20, 40, "nextTransition")]
        )

    def test_set_fan_mode_auto(self):
        """Test set fan mode to auto."""
        self.data.reset_mock()
        self.thermostat.set_fan_mode("auto")
        self.data.ecobee.set_fan_mode.assert_has_calls(
            [mock.call(1, "auto", 20, 40, "nextTransition")]
        )
