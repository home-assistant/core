"""Test Z-Wave node entity."""
import unittest
from unittest.mock import patch, Mock
from tests.common import get_test_home_assistant
import pytest
from homeassistant.components import zwave


@pytest.mark.usefixtures('mock_openzwave')
class TestZWaveBaseEntity(unittest.TestCase):
    """Class to test ZWaveBaseEntity."""

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()

        def call_soon(time, func, *args):
            """Replace call_later by call_soon."""
            return self.hass.loop.call_soon(func, *args)

        self.hass.loop.call_later = call_soon
        self.base_entity = zwave.ZWaveBaseEntity()
        self.base_entity.hass = self.hass
        self.hass.start()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    def test_maybe_schedule_update(self):
        """Test maybe_schedule_update."""
        with patch.object(self.base_entity, 'async_update_ha_state',
                          Mock()) as mock_update:
            self.base_entity.maybe_schedule_update()
            self.hass.block_till_done()
            mock_update.assert_called_once_with()

    def test_maybe_schedule_update_called_twice(self):
        """Test maybe_schedule_update called twice."""
        with patch.object(self.base_entity, 'async_update_ha_state',
                          Mock()) as mock_update:
            self.base_entity.maybe_schedule_update()
            self.base_entity.maybe_schedule_update()
            self.hass.block_till_done()
            mock_update.assert_called_once_with()
