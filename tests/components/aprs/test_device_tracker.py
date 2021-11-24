"""Test APRS device tracker."""
from unittest.mock import Mock, patch

import aprslib

import homeassistant.components.aprs.device_tracker as device_tracker
from homeassistant.const import EVENT_HOMEASSISTANT_START

from tests.common import get_test_home_assistant

DEFAULT_PORT = 14580

TEST_CALLSIGN = "testcall"
TEST_COORDS_NULL_ISLAND = (0, 0)
TEST_FILTER = "testfilter"
TEST_HOST = "testhost"
TEST_PASSWORD = "testpass"


def test_make_filter():
    """Test filter."""
    callsigns = ["CALLSIGN1", "callsign2"]
    res = device_tracker.make_filter(callsigns)
    assert res == "b/CALLSIGN1 b/CALLSIGN2"


def test_gps_accuracy_0():
    """Test GPS accuracy level 0."""
    acc = device_tracker.gps_accuracy(TEST_COORDS_NULL_ISLAND, 0)
    assert acc == 0


def test_gps_accuracy_1():
    """Test GPS accuracy level 1."""
    acc = device_tracker.gps_accuracy(TEST_COORDS_NULL_ISLAND, 1)
    assert acc == 186


def test_gps_accuracy_2():
    """Test GPS accuracy level 2."""
    acc = device_tracker.gps_accuracy(TEST_COORDS_NULL_ISLAND, 2)
    assert acc == 1855


def test_gps_accuracy_3():
    """Test GPS accuracy level 3."""
    acc = device_tracker.gps_accuracy(TEST_COORDS_NULL_ISLAND, 3)
    assert acc == 18553


def test_gps_accuracy_4():
    """Test GPS accuracy level 4."""
    acc = device_tracker.gps_accuracy(TEST_COORDS_NULL_ISLAND, 4)
    assert acc == 111319


def test_gps_accuracy_invalid_int():
    """Test GPS accuracy with invalid input."""
    level = 5

    try:
        device_tracker.gps_accuracy(TEST_COORDS_NULL_ISLAND, level)
        assert False, "No exception."
    except ValueError:
        pass


def test_gps_accuracy_invalid_string():
    """Test GPS accuracy with invalid input."""
    level = "not an int"

    try:
        device_tracker.gps_accuracy(TEST_COORDS_NULL_ISLAND, level)
        assert False, "No exception."
    except ValueError:
        pass


def test_gps_accuracy_invalid_float():
    """Test GPS accuracy with invalid input."""
    level = 1.2

    try:
        device_tracker.gps_accuracy(TEST_COORDS_NULL_ISLAND, level)
        assert False, "No exception."
    except ValueError:
        pass


def test_aprs_listener():
    """Test listener thread."""
    with patch("aprslib.IS") as mock_ais:
        callsign = TEST_CALLSIGN
        password = TEST_PASSWORD
        host = TEST_HOST
        server_filter = TEST_FILTER
        port = DEFAULT_PORT
        see = Mock()

        listener = device_tracker.AprsListenerThread(
            callsign, password, host, server_filter, see
        )
        listener.run()

        assert listener.callsign == callsign
        assert listener.host == host
        assert listener.server_filter == server_filter
        assert listener.see == see
        assert listener.start_event.is_set()
        assert listener.start_success
        assert listener.start_message == "Connected to testhost with callsign testcall."
        mock_ais.assert_called_with(callsign, passwd=password, host=host, port=port)


def test_aprs_listener_start_fail():
    """Test listener thread start failure."""
    with patch(
        "aprslib.IS.connect", side_effect=aprslib.ConnectionError("Unable to connect.")
    ):
        callsign = TEST_CALLSIGN
        password = TEST_PASSWORD
        host = TEST_HOST
        server_filter = TEST_FILTER
        see = Mock()

        listener = device_tracker.AprsListenerThread(
            callsign, password, host, server_filter, see
        )
        listener.run()

        assert listener.callsign == callsign
        assert listener.host == host
        assert listener.server_filter == server_filter
        assert listener.see == see
        assert listener.start_event.is_set()
        assert not listener.start_success
        assert listener.start_message == "Unable to connect."


def test_aprs_listener_stop():
    """Test listener thread stop."""
    with patch("aprslib.IS"):
        callsign = TEST_CALLSIGN
        password = TEST_PASSWORD
        host = TEST_HOST
        server_filter = TEST_FILTER
        see = Mock()

        listener = device_tracker.AprsListenerThread(
            callsign, password, host, server_filter, see
        )
        listener.ais.close = Mock()
        listener.run()
        listener.stop()

        assert listener.callsign == callsign
        assert listener.host == host
        assert listener.server_filter == server_filter
        assert listener.see == see
        assert listener.start_event.is_set()
        assert listener.start_message == "Connected to testhost with callsign testcall."
        assert listener.start_success
        listener.ais.close.assert_called_with()


def test_aprs_listener_rx_msg():
    """Test rx_msg."""
    with patch("aprslib.IS"):
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
            device_tracker.ATTR_ALTITUDE: 0,
        }

        listener = device_tracker.AprsListenerThread(
            callsign, password, host, server_filter, see
        )
        listener.run()
        listener.rx_msg(sample_msg)

        assert listener.callsign == callsign
        assert listener.host == host
        assert listener.server_filter == server_filter
        assert listener.see == see
        assert listener.start_event.is_set()
        assert listener.start_success
        assert listener.start_message == "Connected to testhost with callsign testcall."
        see.assert_called_with(
            dev_id=device_tracker.slugify("ZZ0FOOBAR-1"),
            gps=(0.0, 0.0),
            attributes={"altitude": 0},
        )


def test_aprs_listener_rx_msg_ambiguity():
    """Test rx_msg with posambiguity."""
    with patch("aprslib.IS"):
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
            device_tracker.ATTR_POS_AMBIGUITY: 1,
        }

        listener = device_tracker.AprsListenerThread(
            callsign, password, host, server_filter, see
        )
        listener.run()
        listener.rx_msg(sample_msg)

        assert listener.callsign == callsign
        assert listener.host == host
        assert listener.server_filter == server_filter
        assert listener.see == see
        assert listener.start_event.is_set()
        assert listener.start_success
        assert listener.start_message == "Connected to testhost with callsign testcall."
        see.assert_called_with(
            dev_id=device_tracker.slugify("ZZ0FOOBAR-1"),
            gps=(0.0, 0.0),
            attributes={device_tracker.ATTR_GPS_ACCURACY: 186},
        )


def test_aprs_listener_rx_msg_ambiguity_invalid():
    """Test rx_msg with invalid posambiguity."""
    with patch("aprslib.IS"):
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
            device_tracker.ATTR_POS_AMBIGUITY: 5,
        }

        listener = device_tracker.AprsListenerThread(
            callsign, password, host, server_filter, see
        )
        listener.run()
        listener.rx_msg(sample_msg)

        assert listener.callsign == callsign
        assert listener.host == host
        assert listener.server_filter == server_filter
        assert listener.see == see
        assert listener.start_event.is_set()
        assert listener.start_success
        assert listener.start_message == "Connected to testhost with callsign testcall."
        see.assert_called_with(
            dev_id=device_tracker.slugify("ZZ0FOOBAR-1"), gps=(0.0, 0.0), attributes={}
        )


def test_aprs_listener_rx_msg_no_position():
    """Test rx_msg with non-position report."""
    with patch("aprslib.IS"):
        callsign = TEST_CALLSIGN
        password = TEST_PASSWORD
        host = TEST_HOST
        server_filter = TEST_FILTER
        see = Mock()

        sample_msg = {device_tracker.ATTR_FORMAT: "invalid"}

        listener = device_tracker.AprsListenerThread(
            callsign, password, host, server_filter, see
        )
        listener.run()
        listener.rx_msg(sample_msg)

        assert listener.callsign == callsign
        assert listener.host == host
        assert listener.server_filter == server_filter
        assert listener.see == see
        assert listener.start_event.is_set()
        assert listener.start_success
        assert listener.start_message == "Connected to testhost with callsign testcall."
        see.assert_not_called()


def test_setup_scanner():
    """Test setup_scanner."""
    with patch(
        "homeassistant.components.aprs.device_tracker.AprsListenerThread"
    ) as listener:
        hass = get_test_home_assistant()
        hass.start()

        config = {
            "username": TEST_CALLSIGN,
            "password": TEST_PASSWORD,
            "host": TEST_HOST,
            "callsigns": ["XX0FOO*", "YY0BAR-1"],
        }

        see = Mock()
        res = device_tracker.setup_scanner(hass, config, see)
        hass.bus.fire(EVENT_HOMEASSISTANT_START)
        hass.stop()

        assert res
        listener.assert_called_with(
            TEST_CALLSIGN, TEST_PASSWORD, TEST_HOST, "b/XX0FOO* b/YY0BAR-1", see
        )


def test_setup_scanner_timeout():
    """Test setup_scanner failure from timeout."""
    with patch("aprslib.IS.connect", side_effect=TimeoutError):
        hass = get_test_home_assistant()
        hass.start()

        config = {
            "username": TEST_CALLSIGN,
            "password": TEST_PASSWORD,
            "host": "localhost",
            "timeout": 0.01,
            "callsigns": ["XX0FOO*", "YY0BAR-1"],
        }

        see = Mock()
        assert not device_tracker.setup_scanner(hass, config, see)
        hass.stop()
