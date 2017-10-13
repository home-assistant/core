"""Tests the HASS workday binary sensor."""
from freezegun import freeze_time
from homeassistant.components.binary_sensor.workalendar import day_to_string
from homeassistant.setup import setup_component

from tests.common import (
    get_test_home_assistant, assert_setup_component)


class TestWorkdaySetup(object):
    """Test class for workday sensor."""

    def setup_method(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

        # Set valid default config for test
        self.config_province = {
            'binary_sensor': {
                'platform': 'workalendar',
                'country': 'europe.Italy',
            },
        }

        self.config_noprovince = {
            'binary_sensor': {
                'platform': 'workalendar',
                'country': 'europe.Italy',
            },
        }

        self.config_state = {
            'binary_sensor': {
                'platform': 'workalendar',
                'country': 'usa.California',
            },
        }

        self.config_nostate = {
            'binary_sensor': {
                'platform': 'workalendar',
                'country': 'usa.UnitedStates',
            },
        }

        self.config_includeholiday = {
            'binary_sensor': {
                'platform': 'workalendar',
                'country': 'europe.Italy',
                'workdays': ['holiday'],
                'excludes': ['sat', 'sun']
            },
        }

        self.config_tomorrow = {
            'binary_sensor': {
                'platform': 'workalendar',
                'country': 'europe.Germany',
                'days_offset': 1
            },
        }

        self.config_day_after_tomorrow = {
            'binary_sensor': {
                'platform': 'workalendar',
                'country': 'europe.Germany',
                'days_offset': 2
            },
        }

        self.config_yesterday = {
            'binary_sensor': {
                'platform': 'workalendar',
                'country': 'europe.Germany',
                'days_offset': -1
            },
        }

    def teardown_method(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_setup_component_province(self):
        """Setup workday component."""
        with assert_setup_component(1, 'binary_sensor'):
            setup_component(self.hass, 'binary_sensor', self.config_province)

        assert self.hass.states.get('binary_sensor.workday_sensor') is not None

    # Freeze time to a workday
    @freeze_time("Mar 15th, 2017")
    def test_workday_province(self):
        """Test if workdays are reported correctly."""
        with assert_setup_component(1, 'binary_sensor'):
            setup_component(self.hass, 'binary_sensor', self.config_province)

        assert self.hass.states.get('binary_sensor.workday_sensor') is not None

        self.hass.start()

        entity = self.hass.states.get('binary_sensor.workday_sensor')
        assert entity.state == 'on'

    # Freeze time to a weekend
    @freeze_time("Mar 12th, 2017")
    def test_weekend_province(self):
        """Test if weekends are reported correctly."""
        with assert_setup_component(1, 'binary_sensor'):
            setup_component(self.hass, 'binary_sensor', self.config_province)

        assert self.hass.states.get('binary_sensor.workday_sensor') is not None

        self.hass.start()

        entity = self.hass.states.get('binary_sensor.workday_sensor')
        assert entity.state == 'off'

    # Freeze time to a public holiday in province BW
    @freeze_time("Jan 6th, 2017")
    def test_public_holiday_province(self):
        """Test if public holidays are reported correctly."""
        with assert_setup_component(1, 'binary_sensor'):
            setup_component(self.hass, 'binary_sensor', self.config_province)

        assert self.hass.states.get('binary_sensor.workday_sensor') is not None

        self.hass.start()

        entity = self.hass.states.get('binary_sensor.workday_sensor')
        assert entity.state == 'off'

    def test_setup_component_noprovince(self):
        """Setup workday component."""
        with assert_setup_component(1, 'binary_sensor'):
            setup_component(self.hass, 'binary_sensor', self.config_noprovince)

        assert self.hass.states.get('binary_sensor.workday_sensor') is not None

    # Freeze time to a public holiday in state CA
    @freeze_time("Mar 31st, 2017")
    def test_public_holiday_state(self):
        """Test if public holidays are reported correctly."""
        with assert_setup_component(1, 'binary_sensor'):
            setup_component(self.hass, 'binary_sensor', self.config_state)

        assert self.hass.states.get('binary_sensor.workday_sensor') is not None

        self.hass.start()

        entity = self.hass.states.get('binary_sensor.workday_sensor')
        assert entity.state == 'off'

    # Freeze time to a public holiday in state CA
    @freeze_time("Mar 31st, 2017")
    def test_public_holiday_nostate(self):
        """Test if public holidays are reported correctly."""
        with assert_setup_component(1, 'binary_sensor'):
            setup_component(self.hass, 'binary_sensor', self.config_nostate)

        assert self.hass.states.get('binary_sensor.workday_sensor') is not None

        self.hass.start()

        entity = self.hass.states.get('binary_sensor.workday_sensor')
        assert entity.state == 'on'

    # Freeze time to a public holiday in province BW
    @freeze_time("Jan 6th, 2017")
    def test_public_holiday_includeholiday(self):
        """Test if public holidays are reported correctly."""
        with assert_setup_component(1, 'binary_sensor'):
            setup_component(self.hass, 'binary_sensor',
                            self.config_includeholiday)

        assert self.hass.states.get('binary_sensor.workday_sensor') is not None

        self.hass.start()

        entity = self.hass.states.get('binary_sensor.workday_sensor')
        assert entity.state == 'on'

    # Freeze time to a saturday to test offset
    @freeze_time("Aug 5th, 2017")
    def test_tomorrow(self):
        """Test if tomorrow are reported correctly."""
        with assert_setup_component(1, 'binary_sensor'):
            setup_component(self.hass, 'binary_sensor',
                            self.config_tomorrow)

        assert self.hass.states.get('binary_sensor.workday_sensor') is not None

        self.hass.start()

        entity = self.hass.states.get('binary_sensor.workday_sensor')
        assert entity.state == 'off'

    # Freeze time to a saturday to test offset
    @freeze_time("Aug 5th, 2017")
    def test_day_after_tomorrow(self):
        """Test if the day after tomorrow are reported correctly."""
        with assert_setup_component(1, 'binary_sensor'):
            setup_component(self.hass, 'binary_sensor',
                            self.config_day_after_tomorrow)

        assert self.hass.states.get('binary_sensor.workday_sensor') is not None

        self.hass.start()

        entity = self.hass.states.get('binary_sensor.workday_sensor')
        assert entity.state == 'on'

    # Freeze time to a saturday to test offset
    @freeze_time("Aug 5th, 2017")
    def test_yesterday(self):
        """Test if yesterday are reported correctly."""
        with assert_setup_component(1, 'binary_sensor'):
            setup_component(self.hass, 'binary_sensor',
                            self.config_yesterday)

        assert self.hass.states.get('binary_sensor.workday_sensor') is not None

        self.hass.start()

        entity = self.hass.states.get('binary_sensor.workday_sensor')
        assert entity.state == 'on'

    def test_day_to_string(self):
        """Test if day_to_string is behaving correctly."""
        assert day_to_string(0) == 'mon'
        assert day_to_string(1) == 'tue'
        assert day_to_string(7) == 'holiday'
        assert day_to_string(8) is None
