"""The tests for the Graphite component."""
import socket
from unittest import mock
from unittest.mock import patch

import pytest

from homeassistant.components import graphite
from homeassistant.const import (
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
    EVENT_STATE_CHANGED,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
import homeassistant.core as ha
from homeassistant.setup import async_setup_component


@pytest.fixture(autouse=True)
def mock_batch_timeout(hass):
    """Mock the event bus listener and the batch timeout for tests."""
    hass.bus.listen = mock.MagicMock()
    hass.bus.listen_once = mock.MagicMock()


@pytest.fixture(name="mock_socket")
def mock_socket_fixture():
    """Mock the socket."""
    with patch("socket.socket") as mock_socket:
        yield mock_socket


@pytest.fixture(name="mock_graphite")
def mock_graphite_fixture():
    """Mock graphite."""
    with patch("homeassistant.components.graphite.GraphiteFeeder") as mock_graphite:
        yield mock_graphite


@pytest.fixture(name="mock_time")
def mock_time_fixture():
    """Mock time."""
    with patch("time.time") as mock_time:
        yield mock_time


async def test_setup(hass: HomeAssistant, mock_socket) -> None:
    """Test setup."""
    assert await async_setup_component(hass, graphite.DOMAIN, {"graphite": {}})
    await hass.async_block_till_done()
    assert mock_socket.call_count == 1
    assert mock_socket.call_args == mock.call(socket.AF_INET, socket.SOCK_STREAM)


async def test_full_config(hass: HomeAssistant, mock_graphite, mock_socket):
    """Test setup with full configuration."""
    config = {"graphite": {"host": "foo", "port": 123, "prefix": "me"}}

    assert await async_setup_component(hass, graphite.DOMAIN, config)
    await hass.async_block_till_done()
    assert mock_graphite.call_count == 1
    assert mock_graphite.call_args == mock.call(hass, "foo", 123, "tcp", "me")
    assert mock_socket.call_count == 1
    assert mock_socket.call_args == mock.call(socket.AF_INET, socket.SOCK_STREAM)


async def test_full_udp_config(hass: HomeAssistant, mock_graphite, mock_socket):
    """Test setup with full configuration and UDP protocol."""
    config = {
        "graphite": {"host": "foo", "port": 123, "protocol": "udp", "prefix": "me"}
    }

    assert await async_setup_component(hass, graphite.DOMAIN, config)
    await hass.async_block_till_done()
    assert mock_graphite.call_count == 1
    assert mock_graphite.call_args == mock.call(hass, "foo", 123, "udp", "me")
    assert mock_socket.call_count == 0


async def test_config_port(hass: HomeAssistant, mock_graphite, mock_socket):
    """Test setup with invalid port."""
    config = {"graphite": {"host": "foo", "port": 2003}}

    assert await async_setup_component(hass, graphite.DOMAIN, config)
    await hass.async_block_till_done()
    assert mock_graphite.called
    assert mock_socket.call_count == 1
    assert mock_socket.call_args == mock.call(socket.AF_INET, socket.SOCK_STREAM)


def test_subscribe(hass: HomeAssistant):
    """Test the subscription."""
    gf = graphite.GraphiteFeeder(hass, "foo", 123, "tcp", "ha")
    hass.bus.listen_once.has_calls(
        [
            mock.call(EVENT_HOMEASSISTANT_START, gf.start_listen),
            mock.call(EVENT_HOMEASSISTANT_STOP, gf.shutdown),
        ]
    )

    assert hass.bus.listen.call_count == 1
    assert hass.bus.listen.call_args == mock.call(
        EVENT_STATE_CHANGED, gf.event_listener
    )


def test_startup(hass: HomeAssistant):
    """Test the start."""
    gf = graphite.GraphiteFeeder(hass, "foo", 123, "tcp", "ha")
    with mock.patch.object(gf, "start") as mock_start:
        gf.start_listen("event")
        assert mock_start.call_count == 1
        assert mock_start.call_args == mock.call()


def test_shutdown(hass: HomeAssistant):
    """Test the shutdown."""
    gf = graphite.GraphiteFeeder(hass, "foo", 123, "tcp", "ha")
    with mock.patch.object(gf, "_queue") as mock_queue:
        gf.shutdown("event")
        assert mock_queue.put.call_count == 1
        assert mock_queue.put.call_args == mock.call(gf._quit_object)


def test_event_listener(hass: HomeAssistant):
    """Test the event listener."""
    gf = graphite.GraphiteFeeder(hass, "foo", 123, "tcp", "ha")
    with mock.patch.object(gf, "_queue") as mock_queue:
        gf.event_listener("foo")
        assert mock_queue.put.call_count == 1
        assert mock_queue.put.call_args == mock.call("foo")


def test_report_attributes(hass: HomeAssistant, mock_time):
    """Test the reporting with attributes."""
    gf = graphite.GraphiteFeeder(hass, "foo", 123, "tcp", "ha")
    mock_time.return_value = 12345
    attrs = {"foo": 1, "bar": 2.0, "baz": True, "bat": "NaN"}

    expected = [
        "ha.entity.state 0.000000 12345",
        "ha.entity.foo 1.000000 12345",
        "ha.entity.bar 2.000000 12345",
        "ha.entity.baz 1.000000 12345",
    ]

    state = mock.MagicMock(state=0, attributes=attrs)
    with mock.patch.object(gf, "_send_to_graphite") as mock_send:
        gf._report_attributes("entity", state)
        actual = mock_send.call_args_list[0][0][0].split("\n")
        assert sorted(expected) == sorted(actual)


def test_report_with_string_state(hass: HomeAssistant, mock_time):
    """Test the reporting with strings."""
    gf = graphite.GraphiteFeeder(hass, "foo", 123, "tcp", "ha")
    mock_time.return_value = 12345
    expected = ["ha.entity.foo 1.000000 12345", "ha.entity.state 1.000000 12345"]

    state = mock.MagicMock(state="above_horizon", attributes={"foo": 1.0})
    with mock.patch.object(gf, "_send_to_graphite") as mock_send:
        gf._report_attributes("entity", state)
        actual = mock_send.call_args_list[0][0][0].split("\n")
        assert sorted(expected) == sorted(actual)


def test_report_with_binary_state(hass: HomeAssistant, mock_time):
    """Test the reporting with binary state."""
    gf = graphite.GraphiteFeeder(hass, "foo", 123, "tcp", "ha")
    mock_time.return_value = 12345
    state = ha.State("domain.entity", STATE_ON, {"foo": 1.0})
    with mock.patch.object(gf, "_send_to_graphite") as mock_send:
        gf._report_attributes("entity", state)
        expected = [
            "ha.entity.foo 1.000000 12345",
            "ha.entity.state 1.000000 12345",
        ]
        actual = mock_send.call_args_list[0][0][0].split("\n")
        assert sorted(expected) == sorted(actual)

    state.state = STATE_OFF
    with mock.patch.object(gf, "_send_to_graphite") as mock_send:
        gf._report_attributes("entity", state)
        expected = [
            "ha.entity.foo 1.000000 12345",
            "ha.entity.state 0.000000 12345",
        ]
        actual = mock_send.call_args_list[0][0][0].split("\n")
        assert sorted(expected) == sorted(actual)


def test_send_to_graphite_errors(hass: HomeAssistant, mock_time):
    """Test the sending with errors."""
    gf = graphite.GraphiteFeeder(hass, "foo", 123, "tcp", "ha")
    mock_time.return_value = 12345
    state = ha.State("domain.entity", STATE_ON, {"foo": 1.0})
    with mock.patch.object(gf, "_send_to_graphite") as mock_send:
        mock_send.side_effect = socket.error
        gf._report_attributes("entity", state)
        mock_send.side_effect = socket.gaierror
        gf._report_attributes("entity", state)


def test_send_to_graphite(hass: HomeAssistant, mock_socket):
    """Test the sending of data."""
    gf = graphite.GraphiteFeeder(hass, "foo", 123, "tcp", "ha")
    gf._send_to_graphite("foo")
    assert mock_socket.call_count == 1
    assert mock_socket.call_args == mock.call(socket.AF_INET, socket.SOCK_STREAM)
    sock = mock_socket.return_value
    assert sock.connect.call_count == 1
    assert sock.connect.call_args == mock.call(("foo", 123))
    assert sock.sendall.call_count == 1
    assert sock.sendall.call_args == mock.call(b"foo")
    assert sock.send.call_count == 1
    assert sock.send.call_args == mock.call(b"\n")
    assert sock.close.call_count == 1
    assert sock.close.call_args == mock.call()


def test_run_stops(hass: HomeAssistant):
    """Test the stops."""
    gf = graphite.GraphiteFeeder(hass, "foo", 123, "tcp", "ha")
    with mock.patch.object(gf, "_queue") as mock_queue:
        mock_queue.get.return_value = gf._quit_object
        assert gf.run() is None
        assert mock_queue.get.call_count == 1
        assert mock_queue.get.call_args == mock.call()
        assert mock_queue.task_done.call_count == 1
        assert mock_queue.task_done.call_args == mock.call()


def test_run(hass: HomeAssistant):
    """Test the running."""
    gf = graphite.GraphiteFeeder(hass, "foo", 123, "tcp", "ha")
    runs = []
    event = mock.MagicMock(
        event_type=EVENT_STATE_CHANGED,
        data={"entity_id": "entity", "new_state": mock.MagicMock()},
    )

    def fake_get():
        if len(runs) >= 2:
            return gf._quit_object
        if runs:
            runs.append(1)
            return mock.MagicMock(event_type="somethingelse", data={"new_event": None})
        runs.append(1)
        return event

    with mock.patch.object(gf, "_queue") as mock_queue, mock.patch.object(
        gf, "_report_attributes"
    ) as mock_r:
        mock_queue.get.side_effect = fake_get
        gf.run()
        # Twice for two events, once for the stop
        assert mock_queue.task_done.call_count == 3
        assert mock_r.call_count == 1
        assert mock_r.call_args == mock.call("entity", event.data["new_state"])
