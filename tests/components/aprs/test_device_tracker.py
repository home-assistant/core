"""Test APRS device tracker."""
import unittest
from unittest.mock import Mock, patch

import aprslib

import homeassistant.components.aprs.device_tracker as device_tracker
from homeassistant.const import EVENT_HOMEASSISTANT_START
from homeassistant.exceptions import PlatformNotReady

from tests.common import get_test_home_assistant

DEFAULT_PORT = 14580

TEST_CALLSIGN = 'testcall'
TEST_COORDS_NULL_ISLAND = (0, 0)
TEST_FILTER = 'testfilter'
TEST_HOST = 'testhost'
TEST_PASSWORD = 'testpass'


class TestAprsDeviceTracker(unittest.TestCase):
    """Test Case for APRS device tracker."""

    def test_make_filter(self):
        """Test filter."""
        callsigns = [
            'CALLSIGN1',
            'callsign2'
        ]
        res = device_tracker.make_filter(callsigns)
        self.assertEqual(res, "b/CALLSIGN1 b/CALLSIGN2")

    def test_gps_accuracy_0(self):
        """Test GPS accuracy level 0."""
        acc = device_tracker.gps_accuracy(TEST_COORDS_NULL_ISLAND, 0)
        self.assertEqual(acc, 0)

    def test_gps_accuracy_1(self):
        """Test GPS accuracy level 1."""
        acc = device_tracker.gps_accuracy(TEST_COORDS_NULL_ISLAND, 1)
        self.assertEqual(acc, 186)

    def test_gps_accuracy_2(self):
        """Test GPS accuracy level 2."""
        acc = device_tracker.gps_accuracy(TEST_COORDS_NULL_ISLAND, 2)
        self.assertEqual(acc, 1855)

    def test_gps_accuracy_3(self):
        """Test GPS accuracy level 3."""
        acc = device_tracker.gps_accuracy(TEST_COORDS_NULL_ISLAND, 3)
        self.assertEqual(acc, 18553)

    def test_gps_accuracy_4(self):
        """Test GPS accuracy level 4."""
        acc = device_tracker.gps_accuracy(TEST_COORDS_NULL_ISLAND, 4)
        self.assertEqual(acc, 111319)

    def test_gps_accuracy_invalid_int(self):
        """Test GPS accuracy with invalid input."""
        level = 5
        try:
            device_tracker.gps_accuracy(TEST_COORDS_NULL_ISLAND, level)
            self.fail("No exception.")
        except ValueError:
            pass

    def test_gps_accuracy_invalid_string(self):
        """Test GPS accuracy with invalid input."""
        level = "not an int"
        try:
            device_tracker.gps_accuracy(TEST_COORDS_NULL_ISLAND, level)
            self.fail("No exception.")
        except ValueError:
            pass

    def test_gps_accuracy_invalid_float(self):
        """Test GPS accuracy with invalid input."""
        level = 1.2
        try:
            device_tracker.gps_accuracy(TEST_COORDS_NULL_ISLAND, level)
            self.fail("No exception.")
        except ValueError:
            pass

    def test_aprs_listener(self):
        """Test listener thread."""
        with patch('aprslib.IS') as mock_ais:
            callsign = TEST_CALLSIGN
            password = TEST_PASSWORD
            host = TEST_HOST
            server_filter = TEST_FILTER
            port = DEFAULT_PORT
            see = Mock()

            listener = device_tracker.AprsListenerThread(
                callsign, password, host, server_filter, see)
            listener.run()

            self.assertEqual(listener.callsign, callsign)
            self.assertEqual(listener.host, host)
            self.assertEqual(listener.server_filter, server_filter)
            self.assertEqual(listener.see, see)
            self.assertTrue(listener.start_event.is_set())
            self.assertTrue(listener.start_success)
            self.assertEqual("Connected to testhost with callsign testcall.",
                             listener.start_message)
            mock_ais.assert_called_with(
                callsign, passwd=password, host=host, port=port)

    def test_aprs_listener_start_fail(self):
        """Test listener thread start failure."""
        with patch('aprslib.IS.connect',
                   side_effect=aprslib.ConnectionError("Unable to connect.")):
            callsign = TEST_CALLSIGN
            password = TEST_PASSWORD
            host = TEST_HOST
            server_filter = TEST_FILTER
            see = Mock()

            listener = device_tracker.AprsListenerThread(
                callsign, password, host, server_filter, see)
            listener.run()

            self.assertEqual(listener.callsign, callsign)
            self.assertEqual(listener.host, host)
            self.assertEqual(listener.server_filter, server_filter)
            self.assertEqual(listener.see, see)
            self.assertTrue(listener.start_event.is_set())
            self.assertFalse(listener.start_success)
            self.assertEqual("Unable to connect.",
                             listener.start_message)

    def test_aprs_listener_stop(self):
        """Test listener thread stop."""
        with patch('aprslib.IS'):
            callsign = TEST_CALLSIGN
            password = TEST_PASSWORD
            host = TEST_HOST
            server_filter = TEST_FILTER
            see = Mock()

            listener = device_tracker.AprsListenerThread(
                callsign, password, host, server_filter, see)
            listener.ais.close = Mock()
            listener.run()
            listener.stop()

            self.assertEqual(listener.callsign, callsign)
            self.assertEqual(listener.host, host)
            self.assertEqual(listener.server_filter, server_filter)
            self.assertEqual(listener.see, see)
            self.assertTrue(listener.start_event.is_set())
            self.assertEqual("Connected to testhost with callsign testcall.",
                             listener.start_message)
            self.assertTrue(listener.start_success)
            listener.ais.close.assert_called_with()

    def test_aprs_listener_rx_msg(self):
        """Test rx_msg."""
        with patch('aprslib.IS'):
            callsign = TEST_CALLSIGN
            password = TEST_PASSWORD
            host = TEST_HOST
            server_filter = TEST_FILTER
            see = Mock()

            sample_msg = {
                device_tracker.ATTR_FORMAT: "uncompressed",
                device_tracker.ATTR_FROM: "ZZ0FOOBAR-1",
                device_tracker.ATTR_LATITUDE: 0.0,
                device_tracker.ATTR_LONGITUDE: 0.0,
                device_tracker.ATTR_ALTITUDE: 0
            }

            listener = device_tracker.AprsListenerThread(
                callsign, password, host, server_filter, see)
            listener.run()
            listener.rx_msg(sample_msg)

            self.assertEqual(listener.callsign, callsign)
            self.assertEqual(listener.host, host)
            self.assertEqual(listener.server_filter, server_filter)
            self.assertEqual(listener.see, see)
            self.assertTrue(listener.start_event.is_set())
            self.assertTrue(listener.start_success)
            self.assertEqual("Connected to testhost with callsign testcall.",
                             listener.start_message)
            see.assert_called_with(
                dev_id=device_tracker.slugify("ZZ0FOOBAR-1"),
                gps=(0.0, 0.0),
                attributes={"altitude": 0})

    def test_aprs_listener_rx_msg_ambiguity(self):
        """Test rx_msg with posambiguity."""
        with patch('aprslib.IS'):
            callsign = TEST_CALLSIGN
            password = TEST_PASSWORD
            host = TEST_HOST
            server_filter = TEST_FILTER
            see = Mock()

            sample_msg = {
                device_tracker.ATTR_FORMAT: "uncompressed",
                device_tracker.ATTR_FROM: "ZZ0FOOBAR-1",
                device_tracker.ATTR_LATITUDE: 0.0,
                device_tracker.ATTR_LONGITUDE: 0.0,
                device_tracker.ATTR_POS_AMBIGUITY: 1
            }

            listener = device_tracker.AprsListenerThread(
                callsign, password, host, server_filter, see)
            listener.run()
            listener.rx_msg(sample_msg)

            self.assertEqual(listener.callsign, callsign)
            self.assertEqual(listener.host, host)
            self.assertEqual(listener.server_filter, server_filter)
            self.assertEqual(listener.see, see)
            self.assertTrue(listener.start_event.is_set())
            self.assertTrue(listener.start_success)
            self.assertEqual("Connected to testhost with callsign testcall.",
                             listener.start_message)
            see.assert_called_with(
                dev_id=device_tracker.slugify("ZZ0FOOBAR-1"),
                gps=(0.0, 0.0),
                attributes={device_tracker.ATTR_GPS_ACCURACY: 186})

    def test_aprs_listener_rx_msg_ambiguity_invalid(self):
        """Test rx_msg with invalid posambiguity."""
        with patch('aprslib.IS'):
            callsign = TEST_CALLSIGN
            password = TEST_PASSWORD
            host = TEST_HOST
            server_filter = TEST_FILTER
            see = Mock()

            sample_msg = {
                device_tracker.ATTR_FORMAT: "uncompressed",
                device_tracker.ATTR_FROM: "ZZ0FOOBAR-1",
                device_tracker.ATTR_LATITUDE: 0.0,
                device_tracker.ATTR_LONGITUDE: 0.0,
                device_tracker.ATTR_POS_AMBIGUITY: 5
            }

            listener = device_tracker.AprsListenerThread(
                callsign, password, host, server_filter, see)
            listener.run()
            listener.rx_msg(sample_msg)

            self.assertEqual(listener.callsign, callsign)
            self.assertEqual(listener.host, host)
            self.assertEqual(listener.server_filter, server_filter)
            self.assertEqual(listener.see, see)
            self.assertTrue(listener.start_event.is_set())
            self.assertTrue(listener.start_success)
            self.assertEqual("Connected to testhost with callsign testcall.",
                             listener.start_message)
            see.assert_called_with(
                dev_id=device_tracker.slugify("ZZ0FOOBAR-1"),
                gps=(0.0, 0.0),
                attributes={})

    def test_aprs_listener_rx_msg_no_position(self):
        """Test rx_msg with non-position report."""
        with patch('aprslib.IS'):
            callsign = TEST_CALLSIGN
            password = TEST_PASSWORD
            host = TEST_HOST
            server_filter = TEST_FILTER
            see = Mock()

            sample_msg = {
                device_tracker.ATTR_FORMAT: "invalid"
            }

            listener = device_tracker.AprsListenerThread(
                callsign, password, host, server_filter, see)
            listener.run()
            listener.rx_msg(sample_msg)

            self.assertEqual(listener.callsign, callsign)
            self.assertEqual(listener.host, host)
            self.assertEqual(listener.server_filter, server_filter)
            self.assertEqual(listener.see, see)
            self.assertTrue(listener.start_event.is_set())
            self.assertTrue(listener.start_success)
            self.assertEqual("Connected to testhost with callsign testcall.",
                             listener.start_message)
            see.assert_not_called()

    def test_setup_scanner(self):
        """Test setup_scanner."""
        with patch('homeassistant.components.'
                   'aprs.device_tracker.AprsListenerThread') as listener:
            hass = get_test_home_assistant()
            hass.start()

            config = {
                'username': TEST_CALLSIGN,
                'password': TEST_PASSWORD,
                'host': TEST_HOST,
                'callsigns': [
                    'XX0FOO*',
                    'YY0BAR-1']
            }

            see = Mock()
            res = device_tracker.setup_scanner(hass, config, see)
            hass.bus.fire(EVENT_HOMEASSISTANT_START)
            hass.stop()

            self.assertTrue(res)
            listener.assert_called_with(
                TEST_CALLSIGN, TEST_PASSWORD, TEST_HOST,
                'b/XX0FOO* b/YY0BAR-1', see)

    def test_setup_scanner_timeout(self):
        """Test setup_scanner failure from timeout."""
        hass = get_test_home_assistant()
        hass.start()

        config = {
            'username': TEST_CALLSIGN,
            'password': TEST_PASSWORD,
            'host': "localhost",
            'timeout': 0.01,
            'callsigns': [
                'XX0FOO*',
                'YY0BAR-1']
        }

        see = Mock()
        try:
            self.assertRaises(PlatformNotReady,
                              device_tracker.setup_scanner, hass, config, see)
        finally:
            hass.stop()
