"""The test for the sql sensor platform."""
import unittest

import pytest
import voluptuous as vol

from homeassistant.components.sql.sensor import validate_sql_select
from homeassistant.const import STATE_UNKNOWN
from homeassistant.setup import setup_component

from tests.common import get_test_home_assistant


class TestSQLSensor(unittest.TestCase):
    """Test the SQL sensor."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    def test_query(self):
        """Test the SQL sensor."""
        config = {
            "sensor": {
                "platform": "sql",
                "db_url": "sqlite://",
                "queries": [
                    {
                        "name": "count_tables",
                        "query": "SELECT 5 as value",
                        "column": "value",
                    }
                ],
            }
        }

        assert setup_component(self.hass, "sensor", config)
        self.hass.block_till_done()

        state = self.hass.states.get("sensor.count_tables")
        assert state.state == "5"
        assert state.attributes["value"] == 5

    def test_invalid_query(self):
        """Test the SQL sensor for invalid queries."""
        with pytest.raises(vol.Invalid):
            validate_sql_select("DROP TABLE *")

        config = {
            "sensor": {
                "platform": "sql",
                "db_url": "sqlite://",
                "queries": [
                    {
                        "name": "count_tables",
                        "query": "SELECT * value FROM sqlite_master;",
                        "column": "value",
                    }
                ],
            }
        }

        assert setup_component(self.hass, "sensor", config)
        self.hass.block_till_done()

        state = self.hass.states.get("sensor.count_tables")
        assert state.state == STATE_UNKNOWN
