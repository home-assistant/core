"""Test Z-Wave node entity."""
import unittest
from unittest.mock import patch, Mock
from tests.common import get_test_home_assistant
import tests.mock.zwave as mock_zwave
import pytest
from homeassistant.components.zwave import node_entity


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
        self.base_entity = node_entity.ZWaveBaseEntity()
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


@pytest.mark.usefixtures('mock_openzwave')
class TestZWaveNodeEntity(unittest.TestCase):
    """Class to test ZWaveNodeEntity."""

    def setUp(self):
        """Initialize values for this testcase class."""
        self.node = mock_zwave.MockNode(
            query_stage='Dynamic', is_awake=True, is_ready=False,
            is_failed=False, is_info_received=True, max_baud_rate=40000,
            is_zwave_plus=False, capabilities=[], neighbors=[], location=None)
        self.entity = node_entity.ZWaveNodeEntity(self.node)

    def test_network_node_changed_from_value(self):
        """Test for network_node_changed."""
        value = mock_zwave.MockValue(node=self.node)
        with patch.object(self.entity, 'maybe_schedule_update') as mock:
            mock_zwave.value_changed(value)
            mock.assert_called_once_with()

    def test_network_node_changed_from_node(self):
        """Test for network_node_changed."""
        with patch.object(self.entity, 'maybe_schedule_update') as mock:
            mock_zwave.node_changed(self.node)
            mock.assert_called_once_with()

    def test_network_node_changed_from_another_node(self):
        """Test for network_node_changed."""
        with patch.object(self.entity, 'maybe_schedule_update') as mock:
            node = mock_zwave.MockNode(node_id=1024)
            mock_zwave.node_changed(node)
            self.assertFalse(mock.called)

    def test_network_node_changed_from_notification(self):
        """Test for network_node_changed."""
        with patch.object(self.entity, 'maybe_schedule_update') as mock:
            mock_zwave.notification(node_id=self.node.node_id)
            mock.assert_called_once_with()

    def test_network_node_changed_from_another_notification(self):
        """Test for network_node_changed."""
        with patch.object(self.entity, 'maybe_schedule_update') as mock:
            mock_zwave.notification(node_id=1024)
            self.assertFalse(mock.called)

    def test_node_changed(self):
        """Test node_changed function."""
        self.assertEqual({'node_id': self.node.node_id},
                         self.entity.device_state_attributes)

        self.node.get_values.return_value = {
            1: mock_zwave.MockValue(data=1800)
        }
        self.entity.node_changed()

        self.assertEqual(
            {'node_id': self.node.node_id,
             'query_stage': 'Dynamic',
             'is_awake': True,
             'is_ready': False,
             'is_failed': False,
             'is_info_received': True,
             'max_baud_rate': 40000,
             'is_zwave_plus': False,
             'battery_level': 42,
             'wake_up_interval': 1800},
            self.entity.device_state_attributes)

        self.node.can_wake_up_value = False
        self.entity.node_changed()

        self.assertNotIn(
            'wake_up_interval', self.entity.device_state_attributes)

    def test_name(self):
        """Test name property."""
        self.assertEqual('Mock Node', self.entity.name)

    def test_state_before_update(self):
        """Test state before update was called."""
        self.assertIsNone(self.entity.state)

    def test_state_not_ready(self):
        """Test state property."""
        self.node.is_ready = False
        self.entity.node_changed()
        self.assertEqual('Dynamic', self.entity.state)

        self.node.is_failed = True
        self.entity.node_changed()
        self.assertEqual('Dead (Dynamic)', self.entity.state)

        self.node.is_failed = False
        self.node.is_awake = False
        self.entity.node_changed()
        self.assertEqual('Sleeping (Dynamic)', self.entity.state)

    def test_state_ready(self):
        """Test state property."""
        self.node.is_ready = True
        self.entity.node_changed()
        self.assertEqual('Ready', self.entity.state)

        self.node.is_failed = True
        self.entity.node_changed()
        self.assertEqual('Dead', self.entity.state)

        self.node.is_failed = False
        self.node.is_awake = False
        self.entity.node_changed()
        self.assertEqual('Sleeping', self.entity.state)

    def test_not_polled(self):
        """Test should_poll property."""
        self.assertFalse(self.entity.should_poll)


def test_sub_status():
    """Test sub_status function."""
    assert node_entity.sub_status('Status', 'Stage') == 'Status (Stage)'
    assert node_entity.sub_status('Status', '') == 'Status'
