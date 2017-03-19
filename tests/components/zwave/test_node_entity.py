"""Test Z-Wave node entity."""
import unittest
import pytest
from tests.common import get_test_home_assistant

from homeassistant.components import zwave


@pytest.mark.usefixtures('mock_openzwave')
class TestZWaveBaseEntity(unittest.TestCase):
    """Class to test ZWaveBaseEntity."""

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()
        self.base_entity = zwave.ZWaveBaseEntity()
        self.base_entity.hass = self.hass
        self.hass.start()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    def test_maybe_schedule_update(self):
        """Test maybe_schedule_update."""
        self.base_entity.maybe_schedule_update()
        self.hass.block_till_done()
        self.assertTrue(self.base_entity._update_scheduled)
