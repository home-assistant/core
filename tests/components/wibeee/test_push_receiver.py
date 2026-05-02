"""Tests for Wibeee push receiver."""

from __future__ import annotations

from typing import Any

import pytest

from homeassistant.components.wibeee.push_receiver import (
    PushReceiver,
    WibeeeReceiverAvgView,
    WibeeeReceiverLeapView,
    WibeeeReceiverView,
    _dispatch_push_data,
    _handle_push_request,
    parse_push_data,
)

# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def push_receiver() -> PushReceiver:
    """Create a PushReceiver instance."""
    return PushReceiver()


@pytest.fixture
def registered_receiver(
    push_receiver: PushReceiver,
) -> tuple[PushReceiver, list[dict[str, Any]]]:
    """Create a PushReceiver with a registered device."""
    calls: list[dict[str, Any]] = []

    def listener(data: dict[str, Any]) -> None:
        calls.append(data)

    push_receiver.register_device("001ec0112232", "192.168.1.100", listener)
    return push_receiver, calls


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


class MockRequest:
    """Mock Request for testing."""

    def __init__(self, query: dict[str, str], remote: str = "192.168.1.100") -> None:
        """Initialize mock request."""
        self._query = query
        self.remote = remote

    @property
    def query(self) -> dict[str, str]:
        """Return query dict."""
        return self._query


# ---------------------------------------------------------------------------
# Tests: parse_push_data
# ---------------------------------------------------------------------------


def test_parse_push_data_basic() -> None:
    """Test basic parsing of push data."""
    query = {
        "v1": "230.5",
        "a1": "277",
        "vt": "230.5",  # total
    }

    result = parse_push_data(query)

    assert "fase1" in result
    assert "fase4" in result  # total

    assert result["fase1"]["vrms"] == "230.5"
    assert result["fase1"]["p_activa"] == "277"
    assert result["fase4"]["vrms"] == "230.5"


def test_parse_push_data_three_phase() -> None:
    """Test parsing of three-phase push data."""
    query = {
        "v1": "230.0",
        "v2": "231.0",
        "v3": "229.0",
        "vt": "230.0",
    }

    result = parse_push_data(query)

    assert "fase1" in result
    assert "fase2" in result
    assert "fase3" in result
    assert "fase4" in result


def test_parse_push_data_empty() -> None:
    """Test parsing with empty query."""
    result = parse_push_data({})

    assert result == {}


# ---------------------------------------------------------------------------
# Tests: _dispatch_push_data
# ---------------------------------------------------------------------------


def test_dispatch_push_data_valid(
    registered_receiver: tuple[PushReceiver, list[dict[str, Any]]],
) -> None:
    """Test dispatch with valid registered device."""
    receiver, calls = registered_receiver

    query = {
        "mac": "001ec0112232",
        "v1": "230.5",
    }

    result = _dispatch_push_data(receiver, query)

    assert "device 001ec0112232" in result
    assert len(calls) == 1


def test_dispatch_unknown_mac(push_receiver: PushReceiver) -> None:
    """Test dispatch with unknown MAC."""
    query = {
        "mac": "deadbeef",
        "v1": "230.5",
    }

    result = _dispatch_push_data(push_receiver, query)

    assert "unregistered device" in result


def test_dispatch_missing_mac(push_receiver: PushReceiver) -> None:
    """Test dispatch with missing MAC."""
    result = _dispatch_push_data(push_receiver, {})

    assert result == "no MAC in push data"


# ---------------------------------------------------------------------------
# Tests: _handle_push_request
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_push_request_ok(
    registered_receiver: tuple[PushReceiver, list[dict[str, Any]]],
) -> None:
    """Test HTTP handler with valid request."""
    receiver, calls = registered_receiver

    request = MockRequest(
        {
            "mac": "001ec0112232",
            "v1": "230.5",
        }
    )

    resp = await _handle_push_request(receiver, request, "<<<WBAVG ")

    assert resp.status == 200
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_handle_push_request_missing_mac(push_receiver: PushReceiver) -> None:
    """Test HTTP handler with missing MAC."""
    request = MockRequest({})

    resp = await _handle_push_request(push_receiver, request, "<<<WBAVG ")

    assert resp.status == 400


@pytest.mark.asyncio
async def test_handle_push_request_unknown_mac(push_receiver: PushReceiver) -> None:
    """Test HTTP handler with unknown MAC."""
    request = MockRequest(
        {
            "mac": "deadbeef",
        }
    )

    resp = await _handle_push_request(push_receiver, request, "<<<WBAVG ")

    assert resp.status == 403


@pytest.mark.asyncio
async def test_handle_push_request_unauthorized_ip(
    registered_receiver: tuple[PushReceiver, list[dict[str, Any]]],
) -> None:
    """Test HTTP handler with unauthorized source IP."""
    receiver, calls = registered_receiver

    request = MockRequest(
        {
            "mac": "001ec0112232",
            "v1": "230.5",
        },
        remote="192.168.1.200",  # Different from registered IP
    )

    resp = await _handle_push_request(receiver, request, "<<<WBAVG ")

    assert resp.status == 403
    assert len(calls) == 0


# ---------------------------------------------------------------------------
# Tests: PushReceiver
# ---------------------------------------------------------------------------


def test_push_receiver_register() -> None:
    """Test registering a device."""
    receiver = PushReceiver()
    calls: list[dict[str, Any]] = []

    def listener(data: dict[str, Any]) -> None:
        calls.append(data)

    receiver.register_device("001ec0112232", "192.168.1.100", listener)

    assert receiver.device_count == 1
    assert receiver.get_listener("001ec0112232") is not None
    assert receiver.validate_ip("001ec0112232", "192.168.1.100") is True
    assert receiver.validate_ip("001ec0112232", "192.168.1.200") is False


def test_push_receiver_unregister() -> None:
    """Test unregistering a device."""
    receiver = PushReceiver()
    calls: list[dict[str, Any]] = []

    def listener(data: dict[str, Any]) -> None:
        calls.append(data)

    receiver.register_device("001ec0112232", "192.168.1.100", listener)
    receiver.unregister_device("001ec0112232")

    assert receiver.device_count == 0
    assert receiver.get_listener("001ec0112232") is None


def test_push_receiver_multiple_devices() -> None:
    """Test registering multiple devices."""
    receiver = PushReceiver()
    calls1: list[dict[str, Any]] = []
    calls2: list[dict[str, Any]] = []

    def listener1(data: dict[str, Any]) -> None:
        calls1.append(data)

    def listener2(data: dict[str, Any]) -> None:
        calls2.append(data)

    receiver.register_device("001ec0112232", "192.168.1.100", listener1)
    receiver.register_device("001ec0112233", "192.168.1.101", listener2)

    assert receiver.device_count == 2


# ---------------------------------------------------------------------------
# Tests: PushReceiver.validate_ip edge cases
# ---------------------------------------------------------------------------


def test_validate_ip_remote_none() -> None:
    """Test validate_ip rejects when remote_ip is None."""
    receiver = PushReceiver()
    receiver.register_device("001ec0112232", "192.168.1.100", lambda d: None)

    assert receiver.validate_ip("001ec0112232", None) is False


def test_dispatch_no_recognized_sensors(
    registered_receiver: tuple[PushReceiver, list[dict[str, Any]]],
) -> None:
    """Test dispatch returns no-sensors message when query has only mac."""
    receiver, calls = registered_receiver

    # Query with mac but no recognized sensor params
    query = {"mac": "001ec0112232", "junk": "xyz"}
    result = _dispatch_push_data(receiver, query)

    assert "no recognized sensors" in result
    assert calls == []


def test_parse_push_data_skips_short_params() -> None:
    """Test parse_push_data ignores params shorter than 2 chars."""
    # Single-char params can't have prefix+suffix → must be skipped.
    query = {"x": "1", "v1": "230.0"}

    result = parse_push_data(query)

    # Only v1 should be parsed; the short "x" must not crash or appear.
    assert "fase1" in result
    assert result["fase1"]["vrms"] == "230.0"


# ---------------------------------------------------------------------------
# Tests: View classes (thin wrappers around _handle_push_request)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_receiver_avg_view_get(
    registered_receiver: tuple[PushReceiver, list[dict[str, Any]]],
) -> None:
    """Test WibeeeReceiverAvgView.get delegates to _handle_push_request."""
    receiver, _calls = registered_receiver
    view = WibeeeReceiverAvgView(receiver)
    request = MockRequest({"mac": "001ec0112232", "v1": "230.0"})

    resp = await view.get(request)

    assert resp.status == 200


@pytest.mark.asyncio
async def test_receiver_view_get(
    registered_receiver: tuple[PushReceiver, list[dict[str, Any]]],
) -> None:
    """Test WibeeeReceiverView.get delegates to _handle_push_request."""
    receiver, _calls = registered_receiver
    view = WibeeeReceiverView(receiver)
    request = MockRequest({"mac": "001ec0112232", "v1": "230.0"})

    resp = await view.get(request)

    assert resp.status == 200


@pytest.mark.asyncio
async def test_receiver_leap_view_get(
    registered_receiver: tuple[PushReceiver, list[dict[str, Any]]],
) -> None:
    """Test WibeeeReceiverLeapView.get delegates to _handle_push_request."""
    receiver, _calls = registered_receiver
    view = WibeeeReceiverLeapView(receiver)
    request = MockRequest({"mac": "001ec0112232", "v1": "230.0"})

    resp = await view.get(request)

    assert resp.status == 200
