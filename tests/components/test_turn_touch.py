"""Tests for the Turn Touch component."""
import unittest
from unittest.mock import patch, PropertyMock
import pytest
from bluepy.btle import ADDR_TYPE_PUBLIC
from turntouch import TurnTouch, TurnTouchException
from homeassistant.core import callback
from homeassistant import setup
from homeassistant.components import turn_touch
from homeassistant.components.sensor.turn_touch import TurnTouchBatterySensor
from tests.common import get_test_home_assistant, mock_registry


VALID_CONFIG = {
    'turn_touch': {
        'devices': [
            {
                'mac': 'aa:bb:cc:dd:ee:ff',
                'debounce': True,
            },
        ],
    }
}


class LoopBreakerException(Exception):
    """Mock exception used to break infinite listening loops."""

    pass


class TestTurnTouch(unittest.TestCase):
    """Test cases for the Turn Touch component."""

    def setUp(self):
        """Prepare for testing.

        Sets up patched functions (mocks). Performs component setup.
        """
        def connect_side_effect(self, addr, typ=ADDR_TYPE_PUBLIC, iface=None):
            """Mock side effect for TurnTouch._connect()."""
            self.addr = addr
            self.addrType = typ
            self.iface = iface
        self.connect_patch = patch('bluepy.btle.Peripheral._connect',
                                   side_effect=connect_side_effect,
                                   autospec=True)
        self.patched_connect = self.connect_patch.start()

        self.disconnect_patch = patch('bluepy.btle.Peripheral.disconnect')
        self.patched_disconnect = self.disconnect_patch.start()

        self.listen_patch = patch('turntouch.TurnTouch.listen_forever',
                                  side_effect=LoopBreakerException)
        self.patched_listen = self.listen_patch.start()

        self.battery_patch = patch('turntouch.TurnTouch.battery',
                                   new_callable=PropertyMock)
        self.patched_battery = self.battery_patch.start()

        self.name_patch = patch('turntouch.TurnTouch.name',
                                new_callable=PropertyMock)
        self.patched_name = self.name_patch.start()

        self.hass = get_test_home_assistant()
        mock_registry(self.hass)

        assert setup.setup_component(
            self.hass, turn_touch.DOMAIN, VALID_CONFIG)
        test_mac = VALID_CONFIG['turn_touch']['devices'][0]['mac']
        # pylint: disable=attribute-defined-outside-init
        self.device = self.hass.data[turn_touch.DATA_KEY]['devices'][test_mac]

    def tearDown(self):
        """Clean up after our tests."""
        if turn_touch.DATA_KEY in self.hass.data:
            self.hass.data[turn_touch.DATA_KEY]['devices'].clear()
        # Wait for the listening thread to die, otherwise we unpatch
        # Peripheral.disconnect too soon and btle errors happen.
        self.hass.stop()
        self.name_patch.stop()
        self.battery_patch.stop()
        self.listen_patch.stop()
        self.disconnect_patch.stop()
        self.connect_patch.stop()

    @pytest.fixture(autouse=True)
    def inject_fixtures(self, caplog):
        """Get the caplog fixture."""
        self._caplog = caplog  # pylint: disable=attribute-defined-outside-init

    def test_setup(self):
        """Test successful setup of the component."""
        # Actual setup happens in self.setUp. Just validate it here.
        assert self.patched_connect.called
        assert self.patched_listen.called

    def test_connect(self):
        """Test the TurnTouchRemote._connect() function.

        Ensures that connect() with existing device calls disconnect().
        """
        # pylint: disable=protected-access
        self.patched_disconnect.side_effect = LoopBreakerException
        with self.assertRaises(LoopBreakerException):
            self.device._connect()

    @pytest.mark.timeout(3)
    def test_events(self):
        """Test event handling."""
        events = []

        @callback
        def record_event(event):
            """Add recorded event to list."""
            events.append(event)
        self.hass.bus.listen(turn_touch.EVENT_NAME, record_event)

        # Fire a "North" button press event.
        # pylint: disable=protected-access
        self.device._device.handler.action_any(TurnTouch.ACTIONS[0xFE00])

        # wait for the event. pytest timeout will abort in 3 seconds.
        while not events:
            pass

        assert len(events) == 1
        assert events[0].data['press_type'] == 'action_north'

    def test_logging(self):
        """Test error handling (ie. logging)."""
        # Test logging - connect failed
        with patch('turntouch.TurnTouch.__init__',
                   side_effect=TurnTouchException):
            with patch('time.sleep', side_effect=LoopBreakerException):
                with self.assertRaises(LoopBreakerException):
                    self.device._connect()  # pylint: disable=protected-access
                assert 'Connecting failed' in self._caplog.text

        # Test logging - listening for events failed
        with patch('turntouch.TurnTouch.listen_forever',
                   side_effect=TurnTouchException):
            with patch.object(turn_touch.TurnTouchRemote, '_connect',
                              side_effect=LoopBreakerException):
                with self.assertRaises(LoopBreakerException):
                    self.device._listen()  # pylint: disable=protected-access
                assert 'Listening for events failed' in self._caplog.text

        with patch.object(turn_touch.TurnTouchRemote, '_connect',
                          side_effect=LoopBreakerException):
            # Test logging - battery read failed
            self.patched_battery.side_effect = TurnTouchException
            with self.assertRaises(LoopBreakerException):
                self.device.get_battery()
            assert 'battery failed' in self._caplog.text

            # Test logging - name read failed
            self.patched_name.side_effect = TurnTouchException
            with self.assertRaises(LoopBreakerException):
                self.device.get_name()
            assert 'name failed' in self._caplog.text

    def test_sensor(self):
        """Test the battery sensor."""
        sensor = TurnTouchBatterySensor(self.device)
        self.patched_battery.return_value = 42
        sensor.update()
        assert sensor.state == 42
