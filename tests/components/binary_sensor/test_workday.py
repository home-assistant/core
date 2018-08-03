"""Tests the HASS workday binary sensor."""
from datetime import date
from unittest.mock import patch

from homeassistant.components.binary_sensor.workday import day_to_string
from homeassistant.setup import setup_component

from tests.common import (
    get_test_home_assistant, assert_setup_component)


FUNCTION_PATH = 'homeassistant.components.binary_sensor.workday.get_date'


class TestWorkdaySetup:
    """Test class for workday sensor."""

    def setup_method(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

        # Set valid default config for test
        self.config_province = {
            'binary_sensor': {
                'platform': 'workday',
                'country': 'DE',
                'province': 'BW'
            },
        }

        self.config_noprovince = {
            'binary_sensor': {
                'platform': 'workday',
                'country': 'DE',
            },
        }

        self.config_invalidprovince = {
            'binary_sensor': {
                'platform': 'workday',
                'country': 'DE',
                'province': 'invalid'
            },
        }

        self.config_state = {
            'binary_sensor': {
                'platform': 'workday',
                'country': 'US',
                'province': 'CA'
            },
        }

        self.config_nostate = {
            'binary_sensor': {
                'platform': 'workday',
                'country': 'US',
            },
        }

        self.config_includeholiday = {
            'binary_sensor': {
                'platform': 'workday',
                'country': 'DE',
                'province': 'BW',
                'workdays': ['holiday'],
                'excludes': ['sat', 'sun']
            },
        }

        self.config_tomorrow = {
            'binary_sensor': {
                'platform': 'workday',
                'country': 'DE',
                'days_offset': 1
            },
        }

        self.config_day_after_tomorrow = {
            'binary_sensor': {
                'platform': 'workday',
                'country': 'DE',
                'days_offset': 2
            },
        }

        self.config_yesterday = {
            'binary_sensor': {
                'platform': 'workday',
                'country': 'DE',
                'days_offset': -1
            },
        }

    def teardown_method(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_setup_component_province(self):
        """Setup workday component."""
        with assert_setup_component(1, 'binary_sensor'):
            setup_component(self.hass, 'binary_sensor',
                            self.config_province)

        entity = self.hass.states.get('binary_sensor.workday_sensor')
        assert entity is not None

    # Freeze time to a workday - Mar 15th, 2017
    @patch(FUNCTION_PATH, return_value=date(2017, 3, 15))
    def test_workday_province(self, mock_date):
        """Test if workdays are reported correctly."""
        with assert_setup_component(1, 'binary_sensor'):
            setup_component(self.hass, 'binary_sensor',
                            self.config_province)

        self.hass.start()

        entity = self.hass.states.get('binary_sensor.workday_sensor')
        assert entity.state == 'on'

    # Freeze time to a weekend - Mar 12th, 2017
    @patch(FUNCTION_PATH, return_value=date(2017, 3, 12))
    def test_weekend_province(self, mock_date):
        """Test if weekends are reported correctly."""
        with assert_setup_component(1, 'binary_sensor'):
            setup_component(self.hass, 'binary_sensor',
                            self.config_province)

        self.hass.start()

        entity = self.hass.states.get('binary_sensor.workday_sensor')
        assert entity.state == 'off'

    # Freeze time to a public holiday in province BW - Jan 6th, 2017
    @patch(FUNCTION_PATH, return_value=date(2017, 1, 6))
    def test_public_holiday_province(self, mock_date):
        """Test if public holidays are reported correctly."""
        with assert_setup_component(1, 'binary_sensor'):
            setup_component(self.hass, 'binary_sensor',
                            self.config_province)

        self.hass.start()

        entity = self.hass.states.get('binary_sensor.workday_sensor')
        assert entity.state == 'off'

    def test_setup_component_noprovince(self):
        """Setup workday component."""
        with assert_setup_component(1, 'binary_sensor'):
            setup_component(self.hass, 'binary_sensor',
                            self.config_noprovince)

        entity = self.hass.states.get('binary_sensor.workday_sensor')
        assert entity is not None

    # Freeze time to a public holiday in province BW - Jan 6th, 2017
    @patch(FUNCTION_PATH, return_value=date(2017, 1, 6))
    def test_public_holiday_noprovince(self, mock_date):
        """Test if public holidays are reported correctly."""
        with assert_setup_component(1, 'binary_sensor'):
            setup_component(self.hass, 'binary_sensor',
                            self.config_noprovince)

        self.hass.start()

        entity = self.hass.states.get('binary_sensor.workday_sensor')
        assert entity.state == 'on'

    # Freeze time to a public holiday in state CA - Mar 31st, 2017
    @patch(FUNCTION_PATH, return_value=date(2017, 3, 31))
    def test_public_holiday_state(self, mock_date):
        """Test if public holidays are reported correctly."""
        with assert_setup_component(1, 'binary_sensor'):
            setup_component(self.hass, 'binary_sensor', self.config_state)

        self.hass.start()

        entity = self.hass.states.get('binary_sensor.workday_sensor')
        assert entity.state == 'off'

    # Freeze time to a public holiday in state CA - Mar 31st, 2017
    @patch(FUNCTION_PATH, return_value=date(2017, 3, 31))
    def test_public_holiday_nostate(self, mock_date):
        """Test if public holidays are reported correctly."""
        with assert_setup_component(1, 'binary_sensor'):
            setup_component(self.hass, 'binary_sensor', self.config_nostate)

        self.hass.start()

        entity = self.hass.states.get('binary_sensor.workday_sensor')
        assert entity.state == 'on'

    def test_setup_component_invalidprovince(self):
        """Setup workday component."""
        with assert_setup_component(1, 'binary_sensor'):
            setup_component(self.hass, 'binary_sensor',
                            self.config_invalidprovince)

        entity = self.hass.states.get('binary_sensor.workday_sensor')
        assert entity is None

    # Freeze time to a public holiday in province BW - Jan 6th, 2017
    @patch(FUNCTION_PATH, return_value=date(2017, 1, 6))
    def test_public_holiday_includeholiday(self, mock_date):
        """Test if public holidays are reported correctly."""
        with assert_setup_component(1, 'binary_sensor'):
            setup_component(self.hass, 'binary_sensor',
                            self.config_includeholiday)

        self.hass.start()

        entity = self.hass.states.get('binary_sensor.workday_sensor')
        assert entity.state == 'on'

    # Freeze time to a saturday to test offset - Aug 5th, 2017
    @patch(FUNCTION_PATH, return_value=date(2017, 8, 5))
    def test_tomorrow(self, mock_date):
        """Test if tomorrow are reported correctly."""
        with assert_setup_component(1, 'binary_sensor'):
            setup_component(self.hass, 'binary_sensor',
                            self.config_tomorrow)

        self.hass.start()

        entity = self.hass.states.get('binary_sensor.workday_sensor')
        assert entity.state == 'off'

    # Freeze time to a saturday to test offset - Aug 5th, 2017
    @patch(FUNCTION_PATH, return_value=date(2017, 8, 5))
    def test_day_after_tomorrow(self, mock_date):
        """Test if the day after tomorrow are reported correctly."""
        with assert_setup_component(1, 'binary_sensor'):
            setup_component(self.hass, 'binary_sensor',
                            self.config_day_after_tomorrow)

        self.hass.start()

        entity = self.hass.states.get('binary_sensor.workday_sensor')
        assert entity.state == 'on'

    # Freeze time to a saturday to test offset - Aug 5th, 2017
    @patch(FUNCTION_PATH, return_value=date(2017, 8, 5))
    def test_yesterday(self, mock_date):
        """Test if yesterday are reported correctly."""
        with assert_setup_component(1, 'binary_sensor'):
            setup_component(self.hass, 'binary_sensor',
                            self.config_yesterday)

        self.hass.start()

        entity = self.hass.states.get('binary_sensor.workday_sensor')
        assert entity.state == 'on'

    def test_day_to_string(self):
        """Test if day_to_string is behaving correctly."""
        assert day_to_string(0) == 'mon'
        assert day_to_string(1) == 'tue'
        assert day_to_string(7) == 'holiday'
        assert day_to_string(8) is None
