"""The test for the statistics sensor platform."""
import unittest
import statistics

import pytest

from homeassistant.setup import setup_component
from homeassistant.components.statistics.sensor import StatisticsSensor
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT, TEMP_CELSIUS, STATE_UNKNOWN)
from homeassistant.util import dt as dt_util
from tests.common import get_test_home_assistant
from unittest.mock import patch
from datetime import datetime, timedelta
from tests.common import init_recorder_component
from homeassistant.components import recorder


class TestStatisticsSensor(unittest.TestCase):
    """Test the Statistics sensor."""

    def setup_method(self, method):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.values = [17, 20, 15.2, 5, 3.8, 9.2, 6.7, 14, 6]
        self.count = len(self.values)
        self.min = min(self.values)
        self.max = max(self.values)
        self.total = sum(self.values)
        self.mean = round(sum(self.values) / len(self.values), 2)
        self.median = round(statistics.median(self.values), 2)
        self.deviation = round(statistics.stdev(self.values), 2)
        self.variance = round(statistics.variance(self.values), 2)
        self.change = round(self.values[-1] - self.values[0], 2)
        self.average_change = round(self.change / (len(self.values) - 1), 2)
        self.change_rate = round(self.average_change / (60 * (self.count - 1)),
                                 2)

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    def test_binary_sensor_source(self):
        """Test if source is a sensor."""
        values = ['on', 'off', 'on', 'off', 'on', 'off', 'on']
        assert setup_component(self.hass, 'sensor', {
            'sensor': {
                'platform': 'statistics',
                'name': 'test',
                'entity_id': 'binary_sensor.test_monitored',
            }
        })

        self.hass.start()
        self.hass.block_till_done()

        for value in values:
            self.hass.states.set('binary_sensor.test_monitored', value)
            self.hass.block_till_done()

        state = self.hass.states.get('sensor.test_count')

        assert str(len(values)) == state.state

    def test_sensor_source(self):
        """Test if source is a sensor."""
        assert setup_component(self.hass, 'sensor', {
            'sensor': {
                'platform': 'statistics',
                'name': 'test',
                'entity_id': 'sensor.test_monitored',
            }
        })

        self.hass.start()
        self.hass.block_till_done()

        for value in self.values:
            self.hass.states.set('sensor.test_monitored', value,
                                 {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
            self.hass.block_till_done()

        state = self.hass.states.get('sensor.test_mean')

        assert str(self.mean) == state.state
        assert self.min == state.attributes.get('min_value')
        assert self.max == state.attributes.get('max_value')
        assert self.variance == state.attributes.get('variance')
        assert self.median == state.attributes.get('median')
        assert self.deviation == \
            state.attributes.get('standard_deviation')
        assert self.mean == state.attributes.get('mean')
        assert self.count == state.attributes.get('count')
        assert self.total == state.attributes.get('total')
        assert '°C' == state.attributes.get('unit_of_measurement')
        assert self.change == state.attributes.get('change')
        assert self.average_change == \
            state.attributes.get('average_change')

    def test_sampling_size(self):
        """Test rotation."""
        assert setup_component(self.hass, 'sensor', {
            'sensor': {
                'platform': 'statistics',
                'name': 'test',
                'entity_id': 'sensor.test_monitored',
                'sampling_size': 5,
            }
        })

        self.hass.start()
        self.hass.block_till_done()

        for value in self.values:
            self.hass.states.set('sensor.test_monitored', value,
                                 {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
            self.hass.block_till_done()

        state = self.hass.states.get('sensor.test_mean')

        assert 3.8 == state.attributes.get('min_value')
        assert 14 == state.attributes.get('max_value')

    def test_sampling_size_1(self):
        """Test validity of stats requiring only one sample."""
        assert setup_component(self.hass, 'sensor', {
            'sensor': {
                'platform': 'statistics',
                'name': 'test',
                'entity_id': 'sensor.test_monitored',
                'sampling_size': 1,
            }
        })

        self.hass.start()
        self.hass.block_till_done()

        for value in self.values[-3:]:  # just the last 3 will do
            self.hass.states.set('sensor.test_monitored', value,
                                 {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
            self.hass.block_till_done()

        state = self.hass.states.get('sensor.test_mean')

        # require only one data point
        assert self.values[-1] == state.attributes.get('min_value')
        assert self.values[-1] == state.attributes.get('max_value')
        assert self.values[-1] == state.attributes.get('mean')
        assert self.values[-1] == state.attributes.get('median')
        assert self.values[-1] == state.attributes.get('total')
        assert 0 == state.attributes.get('change')
        assert 0 == state.attributes.get('average_change')

        # require at least two data points
        assert STATE_UNKNOWN == state.attributes.get('variance')
        assert STATE_UNKNOWN == \
            state.attributes.get('standard_deviation')

    def test_max_age(self):
        """Test value deprecation."""
        mock_data = {
            'return_time': datetime(2017, 8, 2, 12, 23, tzinfo=dt_util.UTC),
        }

        def mock_now():
            return mock_data['return_time']

        with patch('homeassistant.components.statistics.sensor.dt_util.utcnow',
                   new=mock_now):
            assert setup_component(self.hass, 'sensor', {
                'sensor': {
                    'platform': 'statistics',
                    'name': 'test',
                    'entity_id': 'sensor.test_monitored',
                    'max_age': {'minutes': 3}
                }
            })

            self.hass.start()
            self.hass.block_till_done()

            for value in self.values:
                self.hass.states.set('sensor.test_monitored', value,
                                     {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
                self.hass.block_till_done()
                # insert the next value one minute later
                mock_data['return_time'] += timedelta(minutes=1)

            state = self.hass.states.get('sensor.test_mean')

        assert 6 == state.attributes.get('min_value')
        assert 14 == state.attributes.get('max_value')

    def test_change_rate(self):
        """Test min_age/max_age and change_rate."""
        mock_data = {
            'return_time': datetime(2017, 8, 2, 12, 23, 42,
                                    tzinfo=dt_util.UTC),
        }

        def mock_now():
            return mock_data['return_time']

        with patch('homeassistant.components.statistics.sensor.dt_util.utcnow',
                   new=mock_now):
            assert setup_component(self.hass, 'sensor', {
                'sensor': {
                    'platform': 'statistics',
                    'name': 'test',
                    'entity_id': 'sensor.test_monitored'
                }
            })

            self.hass.start()
            self.hass.block_till_done()

            for value in self.values:
                self.hass.states.set('sensor.test_monitored', value,
                                     {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
                self.hass.block_till_done()
                # insert the next value one minute later
                mock_data['return_time'] += timedelta(minutes=1)

            state = self.hass.states.get('sensor.test_mean')

        assert datetime(2017, 8, 2, 12, 23, 42, tzinfo=dt_util.UTC) == \
            state.attributes.get('min_age')
        assert datetime(2017, 8, 2, 12, 23 + self.count - 1, 42,
                        tzinfo=dt_util.UTC) == \
            state.attributes.get('max_age')
        assert self.change_rate == state.attributes.get('change_rate')

    @pytest.mark.skip
    def test_initialize_from_database(self):
        """Test initializing the statistics from the database."""
        # enable the recorder
        init_recorder_component(self.hass)
        # store some values
        for value in self.values:
            self.hass.states.set('sensor.test_monitored', value,
                                 {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
            self.hass.block_till_done()
        # wait for the recorder to really store the data
        self.hass.data[recorder.DATA_INSTANCE].block_till_done()
        # only now create the statistics component, so that it must read the
        # data from the database
        assert setup_component(self.hass, 'sensor', {
            'sensor': {
                'platform': 'statistics',
                'name': 'test',
                'entity_id': 'sensor.test_monitored',
                'sampling_size': 100,
            }
        })

        self.hass.start()
        self.hass.block_till_done()

        # check if the result is as in test_sensor_source()
        state = self.hass.states.get('sensor.test_mean')
        assert str(self.mean) == state.state

    def test_initialize_from_database_with_maxage(self):
        """Test initializing the statistics from the database."""
        mock_data = {
            'return_time': datetime(2017, 8, 2, 12, 23, 42,
                                    tzinfo=dt_util.UTC),
        }

        def mock_now():
            return mock_data['return_time']

        # Testing correct retrieval from recorder, thus we do not
        # want purging to occur within the class itself.
        def mock_purge(self):
            return

        # Set maximum age to 3 hours.
        max_age = 3
        # Determine what our minimum age should be based on test values.
        expected_min_age = mock_data['return_time'] + \
            timedelta(hours=len(self.values) - max_age)

        # enable the recorder
        init_recorder_component(self.hass)

        with patch('homeassistant.components.statistics.sensor.dt_util.utcnow',
                   new=mock_now), \
                patch.object(StatisticsSensor, '_purge_old', mock_purge):
            # store some values
            for value in self.values:
                self.hass.states.set('sensor.test_monitored', value,
                                     {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
                self.hass.block_till_done()
                # insert the next value 1 hour later
                mock_data['return_time'] += timedelta(hours=1)

            # wait for the recorder to really store the data
            self.hass.data[recorder.DATA_INSTANCE].block_till_done()
            # only now create the statistics component, so that it must read
            # the data from the database
            assert setup_component(self.hass, 'sensor', {
                'sensor': {
                    'platform': 'statistics',
                    'name': 'test',
                    'entity_id': 'sensor.test_monitored',
                    'sampling_size': 100,
                    'max_age': {'hours': max_age}
                }
            })
            self.hass.block_till_done()

            self.hass.start()
            self.hass.block_till_done()

            # check if the result is as in test_sensor_source()
            state = self.hass.states.get('sensor.test_mean')

        assert expected_min_age == state.attributes.get('min_age')
        # The max_age timestamp should be 1 hour before what we have right
        # now in mock_data['return_time'].
        assert mock_data['return_time'] == state.attributes.get('max_age') +\
            timedelta(hours=1)
