"""The test for the History Statistics sensor platform."""
# pylint: disable=protected-access
import unittest
from unittest.mock import patch

import homeassistant.components.recorder as recorder
from homeassistant.bootstrap import setup_component
from homeassistant.components.sensor.history_stats import HistoryStatsHelper
from tests.common import get_test_home_assistant


class TestHistoryStatsSensor(unittest.TestCase):
    """Test the History Statistics sensor."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def init_recorder(self):
        """Initialize the recorder."""
        db_uri = 'sqlite://'
        with patch('homeassistant.core.Config.path', return_value=db_uri):
            setup_component(self.hass, recorder.DOMAIN, {
                "recorder": {
                    "db_url": db_uri}})
        self.hass.start()
        recorder._INSTANCE.block_till_db_ready()
        self.hass.block_till_done()
        recorder._INSTANCE.block_till_done()

    def test_setup(self):
        """Test the history statistics sensor setup."""
        self.init_recorder()
        config = {
            'history': {
            },
            'sensor': {
                'platform': 'history_stats',
                'entity_id': 'binary_sensor.test_id',
                'state': 'on',
                'start': '\'{{ _TODAY_ }}\'',
                'end': '\'{{ _NOW_ }}\'',
            }
        }

        self.assertTrue(setup_component(self.hass, 'sensor', config))

    def test_template_parsing(self):
        """Test of template parsing."""
        h = HistoryStatsHelper
        expressions = [
            '_THIS_MINUTE_',
            '_THIS_HOUR_',
            '_TODAY_',
            '_THIS_WEEK_',
            '_THIS_MONTH_',
            '_THIS_YEAR_',
            '_ONE_MINUTE_',
            '_ONE_HOUR_',
            '_ONE_DAY_',
            '_ONE_WEEK_',
        ]

        expected = [
            'as_timestamp(now().replace(second=0))',
            'as_timestamp(now().replace(second=0).replace(minute=0))',
            'as_timestamp(now().replace(second=0).replace(minute=0).'
            'replace(hour=0))',
            'as_timestamp(now().replace(second=0).replace(minute=0).'
            'replace(hour=0)) - now().weekday() * 86400',
            'as_timestamp(now().replace(second=0).replace(minute=0).'
            'replace(hour=0).replace(day=1))',
            'as_timestamp(now().replace(second=0).replace(minute=0).'
            'replace(hour=0).replace(day=1).replace(month=1))',
            '60',
            '3600',
            '86400',
            '604800',
        ]

        unchanged = [
            'now()',
            'as_timestamp(now())',
            'as_timestamp(now().replace(second=0)) + 3600'
            '_NOT_A_VALID__ALIAS',
        ]

        # Check that parsed expression = expected
        for i, expr in enumerate(expressions):
            result = h.parse_time_expr(expr)
            self.assertTrue(result == expected[i])

        # Check that parsing doesn't alter real function
        for i, expr in enumerate(unchanged):
            result = h.parse_time_expr(expr)
            self.assertTrue(result == expr)
