"""Tests the Home Assistant workday binary sensor."""
from datetime import date
from unittest.mock import patch

import pytest
import voluptuous as vol

import homeassistant.components.workday.binary_sensor as binary_sensor
from homeassistant.setup import setup_component

from tests.common import assert_setup_component, get_test_home_assistant

FUNCTION_PATH = "homeassistant.components.workday.binary_sensor.get_date"


class TestWorkdaySetup:
    """Test class for workday sensor."""

    def setup_method(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

        # Set valid default config for test
        self.config_province = {
            "binary_sensor": {"platform": "workday", "country": "DE", "province": "BW"}
        }

        self.config_noprovince = {
            "binary_sensor": {"platform": "workday", "country": "DE"}
        }

        self.config_invalidprovince = {
            "binary_sensor": {
                "platform": "workday",
                "country": "DE",
                "province": "invalid",
            }
        }

        self.config_state = {
            "binary_sensor": {"platform": "workday", "country": "US", "province": "CA"}
        }

        self.config_nostate = {
            "binary_sensor": {"platform": "workday", "country": "US"}
        }

        self.config_includeholiday = {
            "binary_sensor": {
                "platform": "workday",
                "country": "DE",
                "province": "BW",
                "workdays": ["holiday"],
                "excludes": ["sat", "sun"],
            }
        }

        self.config_example1 = {
            "binary_sensor": {
                "platform": "workday",
                "country": "US",
                "workdays": ["mon", "tue", "wed", "thu", "fri"],
                "excludes": ["sat", "sun"],
            }
        }

        self.config_example2 = {
            "binary_sensor": {
                "platform": "workday",
                "country": "DE",
                "province": "BW",
                "workdays": ["mon", "wed", "fri"],
                "excludes": ["sat", "sun", "holiday"],
                "add_holidays": ["2020-02-24"],
            }
        }

        self.config_remove_holidays = {
            "binary_sensor": {
                "platform": "workday",
                "country": "US",
                "workdays": ["mon", "tue", "wed", "thu", "fri"],
                "excludes": ["sat", "sun", "holiday"],
                "remove_holidays": ["2020-12-25", "2020-11-26"],
            }
        }

        self.config_remove_named_holidays = {
            "binary_sensor": {
                "platform": "workday",
                "country": "US",
                "workdays": ["mon", "tue", "wed", "thu", "fri"],
                "excludes": ["sat", "sun", "holiday"],
                "remove_holidays": ["Not a Holiday", "Christmas", "Thanksgiving"],
            }
        }

        self.config_tomorrow = {
            "binary_sensor": {"platform": "workday", "country": "DE", "days_offset": 1}
        }

        self.config_day_after_tomorrow = {
            "binary_sensor": {"platform": "workday", "country": "DE", "days_offset": 2}
        }

        self.config_yesterday = {
            "binary_sensor": {"platform": "workday", "country": "DE", "days_offset": -1}
        }

    def teardown_method(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_valid_country(self):
        """Test topic name/filter validation."""
        # Invalid UTF-8, must not contain U+D800 to U+DFFF
        with pytest.raises(vol.Invalid):
            binary_sensor.valid_country("\ud800")
        with pytest.raises(vol.Invalid):
            binary_sensor.valid_country("\udfff")
        # Country MUST NOT be empty
        with pytest.raises(vol.Invalid):
            binary_sensor.valid_country("")
        # Country must be supported by holidays
        with pytest.raises(vol.Invalid):
            binary_sensor.valid_country("HomeAssistantLand")

    def test_setup_component_province(self):
        """Set up workday component."""
        with assert_setup_component(1, "binary_sensor"):
            setup_component(self.hass, "binary_sensor", self.config_province)
            self.hass.block_till_done()

        entity = self.hass.states.get("binary_sensor.workday_sensor")
        assert entity is not None

    # Freeze time to a workday - Mar 15th, 2017
    @patch(FUNCTION_PATH, return_value=date(2017, 3, 15))
    def test_workday_province(self, mock_date):
        """Test if workdays are reported correctly."""
        with assert_setup_component(1, "binary_sensor"):
            setup_component(self.hass, "binary_sensor", self.config_province)
            self.hass.block_till_done()

        self.hass.start()

        entity = self.hass.states.get("binary_sensor.workday_sensor")
        assert entity.state == "on"

    # Freeze time to a weekend - Mar 12th, 2017
    @patch(FUNCTION_PATH, return_value=date(2017, 3, 12))
    def test_weekend_province(self, mock_date):
        """Test if weekends are reported correctly."""
        with assert_setup_component(1, "binary_sensor"):
            setup_component(self.hass, "binary_sensor", self.config_province)
            self.hass.block_till_done()

        self.hass.start()

        entity = self.hass.states.get("binary_sensor.workday_sensor")
        assert entity.state == "off"

    # Freeze time to a public holiday in province BW - Jan 6th, 2017
    @patch(FUNCTION_PATH, return_value=date(2017, 1, 6))
    def test_public_holiday_province(self, mock_date):
        """Test if public holidays are reported correctly."""
        with assert_setup_component(1, "binary_sensor"):
            setup_component(self.hass, "binary_sensor", self.config_province)
            self.hass.block_till_done()

        self.hass.start()

        entity = self.hass.states.get("binary_sensor.workday_sensor")
        assert entity.state == "off"

    def test_setup_component_noprovince(self):
        """Set up workday component."""
        with assert_setup_component(1, "binary_sensor"):
            setup_component(self.hass, "binary_sensor", self.config_noprovince)
            self.hass.block_till_done()

        entity = self.hass.states.get("binary_sensor.workday_sensor")
        assert entity is not None

    # Freeze time to a public holiday in province BW - Jan 6th, 2017
    @patch(FUNCTION_PATH, return_value=date(2017, 1, 6))
    def test_public_holiday_noprovince(self, mock_date):
        """Test if public holidays are reported correctly."""
        with assert_setup_component(1, "binary_sensor"):
            setup_component(self.hass, "binary_sensor", self.config_noprovince)
            self.hass.block_till_done()

        self.hass.start()

        entity = self.hass.states.get("binary_sensor.workday_sensor")
        assert entity.state == "on"

    # Freeze time to a public holiday in state CA - Mar 31st, 2017
    @patch(FUNCTION_PATH, return_value=date(2017, 3, 31))
    def test_public_holiday_state(self, mock_date):
        """Test if public holidays are reported correctly."""
        with assert_setup_component(1, "binary_sensor"):
            setup_component(self.hass, "binary_sensor", self.config_state)

        self.hass.start()

        entity = self.hass.states.get("binary_sensor.workday_sensor")
        assert entity.state == "off"

    # Freeze time to a public holiday in state CA - Mar 31st, 2017
    @patch(FUNCTION_PATH, return_value=date(2017, 3, 31))
    def test_public_holiday_nostate(self, mock_date):
        """Test if public holidays are reported correctly."""
        with assert_setup_component(1, "binary_sensor"):
            setup_component(self.hass, "binary_sensor", self.config_nostate)

        self.hass.start()

        entity = self.hass.states.get("binary_sensor.workday_sensor")
        assert entity.state == "on"

    def test_setup_component_invalidprovince(self):
        """Set up workday component."""
        with assert_setup_component(1, "binary_sensor"):
            setup_component(self.hass, "binary_sensor", self.config_invalidprovince)

        entity = self.hass.states.get("binary_sensor.workday_sensor")
        assert entity is None

    # Freeze time to a public holiday in province BW - Jan 6th, 2017
    @patch(FUNCTION_PATH, return_value=date(2017, 1, 6))
    def test_public_holiday_includeholiday(self, mock_date):
        """Test if public holidays are reported correctly."""
        with assert_setup_component(1, "binary_sensor"):
            setup_component(self.hass, "binary_sensor", self.config_includeholiday)

        self.hass.start()

        entity = self.hass.states.get("binary_sensor.workday_sensor")
        assert entity.state == "on"

    # Freeze time to a saturday to test offset - Aug 5th, 2017
    @patch(FUNCTION_PATH, return_value=date(2017, 8, 5))
    def test_tomorrow(self, mock_date):
        """Test if tomorrow are reported correctly."""
        with assert_setup_component(1, "binary_sensor"):
            setup_component(self.hass, "binary_sensor", self.config_tomorrow)

        self.hass.start()

        entity = self.hass.states.get("binary_sensor.workday_sensor")
        assert entity.state == "off"

    # Freeze time to a saturday to test offset - Aug 5th, 2017
    @patch(FUNCTION_PATH, return_value=date(2017, 8, 5))
    def test_day_after_tomorrow(self, mock_date):
        """Test if the day after tomorrow are reported correctly."""
        with assert_setup_component(1, "binary_sensor"):
            setup_component(self.hass, "binary_sensor", self.config_day_after_tomorrow)

        self.hass.start()

        entity = self.hass.states.get("binary_sensor.workday_sensor")
        assert entity.state == "on"

    # Freeze time to a saturday to test offset - Aug 5th, 2017
    @patch(FUNCTION_PATH, return_value=date(2017, 8, 5))
    def test_yesterday(self, mock_date):
        """Test if yesterday are reported correctly."""
        with assert_setup_component(1, "binary_sensor"):
            setup_component(self.hass, "binary_sensor", self.config_yesterday)

        self.hass.start()

        entity = self.hass.states.get("binary_sensor.workday_sensor")
        assert entity.state == "on"

    # Freeze time to a Presidents day to test Holiday on a Work day - Jan 20th, 2020
    #   Presidents day Feb 17th 2020 is mon.
    @patch(FUNCTION_PATH, return_value=date(2020, 2, 17))
    def test_config_example1_holiday(self, mock_date):
        """Test if public holidays are reported correctly."""
        with assert_setup_component(1, "binary_sensor"):
            setup_component(self.hass, "binary_sensor", self.config_example1)

        self.hass.start()

        entity = self.hass.states.get("binary_sensor.workday_sensor")
        assert entity.state == "on"

    # Freeze time to test tue - Feb 18th, 2020
    @patch(FUNCTION_PATH, return_value=date(2020, 2, 18))
    def test_config_example2_tue(self, mock_date):
        """Test if public holidays are reported correctly."""
        with assert_setup_component(1, "binary_sensor"):
            setup_component(self.hass, "binary_sensor", self.config_example2)

        self.hass.start()

        entity = self.hass.states.get("binary_sensor.workday_sensor")
        assert entity.state == "off"

    # Freeze time to test mon, but added as holiday - Feb 24th, 2020
    @patch(FUNCTION_PATH, return_value=date(2020, 2, 24))
    def test_config_example2_add_holiday(self, mock_date):
        """Test if public holidays are reported correctly."""
        with assert_setup_component(1, "binary_sensor"):
            setup_component(self.hass, "binary_sensor", self.config_example2)

        self.hass.start()

        entity = self.hass.states.get("binary_sensor.workday_sensor")
        assert entity.state == "off"

    def test_day_to_string(self):
        """Test if day_to_string is behaving correctly."""
        assert binary_sensor.day_to_string(0) == "mon"
        assert binary_sensor.day_to_string(1) == "tue"
        assert binary_sensor.day_to_string(7) == "holiday"
        assert binary_sensor.day_to_string(8) is None

    # Freeze time to test Fri, but remove holiday - December 25, 2020
    @patch(FUNCTION_PATH, return_value=date(2020, 12, 25))
    def test_config_remove_holidays_xmas(self, mock_date):
        """Test if removed holidays are reported correctly."""
        with assert_setup_component(1, "binary_sensor"):
            setup_component(self.hass, "binary_sensor", self.config_remove_holidays)

        self.hass.start()

        entity = self.hass.states.get("binary_sensor.workday_sensor")
        assert entity.state == "on"

    # Freeze time to test Fri, but remove holiday by name - Christmas
    @patch(FUNCTION_PATH, return_value=date(2020, 12, 25))
    def test_config_remove_named_holidays_xmas(self, mock_date):
        """Test if removed by name holidays are reported correctly."""
        with assert_setup_component(1, "binary_sensor"):
            setup_component(
                self.hass, "binary_sensor", self.config_remove_named_holidays
            )

        self.hass.start()

        entity = self.hass.states.get("binary_sensor.workday_sensor")
        assert entity.state == "on"
