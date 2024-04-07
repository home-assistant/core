"""Test APRS device tracker."""

from collections.abc import Generator
from unittest.mock import MagicMock, Mock, patch

import aprslib
from aprslib import IS
import pytest

from homeassistant.components.aprs import device_tracker
from homeassistant.core import HomeAssistant

DEFAULT_PORT = 14580

TEST_CALLSIGN = "testcall"
TEST_COORDS_NULL_ISLAND = (0, 0)
TEST_FILTER = "testfilter"
TEST_HOST = "testhost"
TEST_PASSWORD = "testpass"


@pytest.fixture(name="mock_ais")
def mock_ais() -> Generator[MagicMock, None, None]:
    """Mock aprslib."""
    with patch("aprslib.IS") as mock_ais:
        yield mock_ais


def test_make_filter() -> None:
    """Test filter."""
    callsigns = ["CALLSIGN1", "callsign2"]
    res = device_tracker.make_filter(callsigns)
    assert res == "b/CALLSIGN1 b/CALLSIGN2"


def test_gps_accuracy_0() -> None:
    """Test GPS accuracy level 0."""
    acc = device_tracker.gps_accuracy(TEST_COORDS_NULL_ISLAND, 0)
    assert acc == 0


def test_gps_accuracy_1() -> None:
    """Test GPS accuracy level 1."""
    acc = device_tracker.gps_accuracy(TEST_COORDS_NULL_ISLAND, 1)
    assert acc == 186


def test_gps_accuracy_2() -> None:
    """Test GPS accuracy level 2."""
    acc = device_tracker.gps_accuracy(TEST_COORDS_NULL_ISLAND, 2)
    assert acc == 1855


def test_gps_accuracy_3() -> None:
    """Test GPS accuracy level 3."""
    acc = device_tracker.gps_accuracy(TEST_COORDS_NULL_ISLAND, 3)
    assert acc == 18553


def test_gps_accuracy_4() -> None:
    """Test GPS accuracy level 4."""
    acc = device_tracker.gps_accuracy(TEST_COORDS_NULL_ISLAND, 4)
    assert acc == 111319


def test_gps_accuracy_invalid_int() -> None:
    """Test GPS accuracy with invalid input."""
    level = 5

    try:
        device_tracker.gps_accuracy(TEST_COORDS_NULL_ISLAND, level)
        pytest.fail("No exception.")
    except ValueError:
        pass


def test_gps_accuracy_invalid_string() -> None:
    """Test GPS accuracy with invalid input."""
    level = "not an int"

    try:
        device_tracker.gps_accuracy(TEST_COORDS_NULL_ISLAND, level)
        pytest.fail("No exception.")
    except ValueError:
        pass


def test_gps_accuracy_invalid_float() -> None:
    """Test GPS accuracy with invalid input."""
    level = 1.2

    try:
        device_tracker.gps_accuracy(TEST_COORDS_NULL_ISLAND, level)
        pytest.fail("No exception.")
    except ValueError:
        pass


def test_aprs_listener(mock_ais: MagicMock) -> None:
    """Test listener thread."""
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


def test_aprs_listener_start_fail() -> None:
    """Test listener thread start failure."""
    with patch.object(
        IS, "connect", side_effect=aprslib.ConnectionError("Unable to connect.")
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


def test_aprs_listener_stop(mock_ais: MagicMock) -> None:
    """Test listener thread stop."""
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


def test_aprs_listener_rx_msg(mock_ais: MagicMock) -> None:
    """Test rx_msg."""
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


def test_aprs_listener_rx_msg_ambiguity(mock_ais: MagicMock) -> None:
    """Test rx_msg with posambiguity."""
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


def test_aprs_listener_rx_msg_ambiguity_invalid(mock_ais: MagicMock) -> None:
    """Test rx_msg with invalid posambiguity."""
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


def test_aprs_listener_rx_msg_no_position(mock_ais: MagicMock) -> None:
    """Test rx_msg with non-position report."""
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


async def test_setup_scanner(hass: HomeAssistant) -> None:
    """Test setup_scanner."""
    with patch(
        "homeassistant.components.aprs.device_tracker.AprsListenerThread"
    ) as listener:
        config = {
            "username": TEST_CALLSIGN,
            "password": TEST_PASSWORD,
            "host": TEST_HOST,
            "callsigns": ["XX0FOO*", "YY0BAR-1"],
            "timeout": device_tracker.DEFAULT_TIMEOUT,
        }

        see = Mock()
        res = await hass.async_add_executor_job(
            device_tracker.setup_scanner, hass, config, see
        )

        assert res
        listener.assert_called_with(
            TEST_CALLSIGN, TEST_PASSWORD, TEST_HOST, "b/XX0FOO* b/YY0BAR-1", see
        )


async def test_setup_scanner_timeout(hass: HomeAssistant) -> None:
    """Test setup_scanner failure from timeout."""
    with patch.object(IS, "connect", side_effect=TimeoutError):
        config = {
            "username": TEST_CALLSIGN,
            "password": TEST_PASSWORD,
            "host": "localhost",
            "timeout": 0.01,
            "callsigns": ["XX0FOO*", "YY0BAR-1"],
        }

        see = Mock()
        assert not await hass.async_add_executor_job(
            device_tracker.setup_scanner, hass, config, see
        )
