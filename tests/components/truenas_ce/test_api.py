"""Unit tests for homeassistant/components/truenas_ce/api.py.

Unlike config_flow.py/coordinator.py, TrueNASAPI has no Home Assistant
dependency at all -- it only wraps ``aiotruenas.TrueNASClient`` -- so it can
be imported and instantiated directly as a real package module. The
underlying ``aiotruenas`` client is replaced with a Mock/AsyncMock so no
network I/O happens.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from aiotruenas.exceptions import (
    TrueNASAuthenticationError,
    TrueNASCallError,
    TrueNASCallTimeoutError,
    TrueNASCertificateVerificationError,
    TrueNASConnectionClosedError,
    TrueNASConnectionRefusedError,
    TrueNASError,
    TrueNASHostUnknownError,
    TrueNASMalformedResponseError,
)
import pytest

from homeassistant.components.truenas_ce import api as api_module
from homeassistant.components.truenas_ce.api import (
    TrueNASAPI,
    _classify_exception,
    _summarize_payload,
)
from homeassistant.components.truenas_ce.const import (
    ERR_CERT_VERIFY_FAILED,
    ERR_CONNECTION_REFUSED,
    ERR_INVALID_KEY,
    ERR_LOST_LOGIN,
    ERR_LOST_QUERY,
    ERR_MALFORMED_RESULT,
    ERR_TIMEOUT,
    ERR_UNKNOWN,
    ERR_UNKNOWN_HOSTNAME,
    ERROR_API_FORMAT,
)


@pytest.fixture
def api() -> TrueNASAPI:
    """Build a TrueNASAPI whose underlying aiotruenas client is a mock.

    The mock starts disconnected, matching the falsy state a fresh,
    never-logged-in aiotruenas client would report. Its async methods are
    AsyncMocks so tests only attach return values/side effects as needed.
    """
    mock_client = MagicMock()
    mock_client.connected = False
    mock_client.connect = AsyncMock()
    mock_client.call = AsyncMock()
    mock_client.close = AsyncMock()
    with patch.object(api_module, "TrueNASClient", return_value=mock_client):
        return TrueNASAPI("truenas.local", "api-key")


@pytest.fixture
def connected_api(api: TrueNASAPI) -> TrueNASAPI:
    """The mocked TrueNASAPI in an already-connected state."""
    api._client.connected = True
    return api


@pytest.fixture
async def closed_api(api: TrueNASAPI) -> TrueNASAPI:
    """The mocked TrueNASAPI after close() -- permanently closed."""
    await api.close()
    return api


# ---------------------------
#   _summarize_payload
# ---------------------------
def test_summarize_payload_lists_shape() -> None:
    """A list payload's summary starts with its item count."""
    assert _summarize_payload([1, 2, 3]).startswith("list[3]")


def test_summarize_payload_empty_list_shape() -> None:
    """An empty list payload's summary reports zero items."""
    assert _summarize_payload([]).startswith("list[0]")


def test_summarize_payload_dict_shape() -> None:
    """A dict payload's summary starts with its key count."""
    assert _summarize_payload({"a": 1, "b": 2}).startswith("dict[2 keys]")


def test_summarize_payload_empty_dict_shape() -> None:
    """An empty dict payload's summary reports zero keys."""
    assert _summarize_payload({}).startswith("dict[0 keys]")


def test_summarize_payload_other_type_shape() -> None:
    """A scalar payload's summary starts with its type name."""
    assert _summarize_payload("hello").startswith("str ")


def test_summarize_payload_none_shape() -> None:
    """A None payload summarizes as NoneType None."""
    assert _summarize_payload(None) == "NoneType None"


def test_summarize_payload_truncates_long_text() -> None:
    """A payload summary longer than the limit is truncated."""
    result = _summarize_payload(list(range(1000)), limit=20)
    assert "truncated" in result
    assert result.index("truncated") < len(result)


def test_summarize_payload_does_not_truncate_short_text() -> None:
    """A payload summary within the limit is not truncated."""
    result = _summarize_payload([1, 2], limit=500)
    assert "truncated" not in result


# ---------------------------
#   _classify_exception
# ---------------------------
def test_classify_exception_connection_closed_during_call() -> None:
    """A connection closed during a call classifies as a lost query."""
    exc = TrueNASConnectionClosedError("closed", phase="call")
    assert _classify_exception(exc, during_call=True) == ERR_LOST_QUERY


def test_classify_exception_connection_closed_not_during_call() -> None:
    """A connection closed outside a call classifies as a lost login."""
    exc = TrueNASConnectionClosedError("closed", phase="login")
    assert _classify_exception(exc, during_call=False) == ERR_LOST_LOGIN


def test_classify_exception_maps_known_types() -> None:
    """Each known TrueNASError subclass maps to its corresponding ERR_* code."""
    assert (
        _classify_exception(TrueNASCertificateVerificationError(), during_call=False)
        == ERR_CERT_VERIFY_FAILED
    )
    assert (
        _classify_exception(TrueNASHostUnknownError("bad host"), during_call=False)
        == ERR_UNKNOWN_HOSTNAME
    )
    assert (
        _classify_exception(TrueNASConnectionRefusedError("refused"), during_call=False)
        == ERR_CONNECTION_REFUSED
    )
    assert (
        _classify_exception(TrueNASCallTimeoutError("timeout"), during_call=True)
        == ERR_TIMEOUT
    )
    assert (
        _classify_exception(TrueNASAuthenticationError(), during_call=False)
        == ERR_INVALID_KEY
    )
    assert (
        _classify_exception(TrueNASMalformedResponseError("bad"), during_call=True)
        == ERR_MALFORMED_RESULT
    )


def test_classify_exception_falls_back_to_unknown() -> None:
    """An unrecognized TrueNASCallError falls back to ERR_UNKNOWN."""
    exc = TrueNASCallError("boom")
    assert _classify_exception(exc, during_call=True) == ERR_UNKNOWN


# ---------------------------
#   TrueNASAPI.__init__
# ---------------------------
def test_init_defaults_to_wss(api: TrueNASAPI) -> None:
    """The default WebSocket scheme is wss."""
    assert api.scheme == "wss"


def test_init_accepts_ws_scheme() -> None:
    """An explicit ws scheme is accepted and normalized to lowercase."""
    with patch.object(api_module, "TrueNASClient", return_value=MagicMock()):
        api = TrueNASAPI("truenas.local", "key", scheme="WS")
    assert api.scheme == "ws"


def test_init_rejects_invalid_scheme() -> None:
    """An invalid scheme raises a ValueError."""
    with pytest.raises(ValueError, match="Invalid WebSocket scheme"):
        TrueNASAPI("truenas.local", "key", scheme="http")


# ---------------------------
#   connect
# ---------------------------
async def test_connect_fails_when_permanently_closed(closed_api: TrueNASAPI) -> None:
    """A permanently closed API refuses to reconnect."""
    assert await closed_api.connect() is False
    assert closed_api.error == ERR_UNKNOWN
    closed_api._client.connect.assert_not_awaited()


async def test_connect_returns_true_when_already_connected(
    connected_api: TrueNASAPI,
) -> None:
    """An already-connected API reports connected without reconnecting."""
    assert await connected_api.connect() is True
    connected_api._client.connect.assert_not_awaited()


async def test_connect_success_clears_error(api: TrueNASAPI) -> None:
    """A successful connect clears any stale error."""
    api._error = "stale error"
    assert await api.connect() is True
    assert api.error == ""


async def test_connect_maps_exception_and_returns_false(api: TrueNASAPI) -> None:
    """A connect failure maps the raised exception to its error code and returns False."""
    api._client.connect.side_effect = TrueNASHostUnknownError("nope")
    assert await api.connect() is False
    assert api.error == ERR_UNKNOWN_HOSTNAME


async def test_connect_failure_logs_error_by_default(
    api: TrueNASAPI,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A connect failure logs an ERROR with traceback by default."""
    api._client.connect.side_effect = TrueNASConnectionRefusedError("refused")
    with caplog.at_level("DEBUG", logger=api_module.__name__):
        assert await api.connect() is False
    error_records = [record for record in caplog.records if record.levelname == "ERROR"]
    assert error_records
    assert all(record.exc_info is not None for record in error_records)


async def test_connect_quiet_logs_debug_not_error(
    api: TrueNASAPI,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Zeroconf discovery probes many non-TrueNAS devices (issue #46 follow-up).

    A failed probe connection must stay quiet -- DEBUG, no traceback --
    instead of flooding the log with an ERROR per candidate.
    """
    api._client.connect.side_effect = TrueNASConnectionRefusedError("refused")
    with caplog.at_level("DEBUG", logger=api_module.__name__):
        assert await api.connect(quiet=True) is False
    assert api.error == ERR_CONNECTION_REFUSED
    assert not any(record.levelname == "ERROR" for record in caplog.records)
    connect_debug_records = [
        record
        for record in caplog.records
        if record.levelname == "DEBUG"
        and "Error while communicating with host" in record.getMessage()
    ]
    assert len(connect_debug_records) == 1
    assert connect_debug_records[0].exc_info is None


async def test_connect_forwards_quiet_to_client(api: TrueNASAPI) -> None:
    """``quiet`` is forwarded to aiotruenas's own ``connect()``.

    aiotruenas >=1.2.0 owns TLS-warning suppression itself (downgrading its
    "verify_ssl=False" warning to DEBUG when ``quiet=True``, see its own
    ``test_client.py``); this integration only needs to pass the flag
    through.
    """
    assert await api.connect(quiet=True) is True
    api._client.connect.assert_awaited_once_with(quiet=True)


async def test_connect_defaults_to_non_quiet_client_connect(api: TrueNASAPI) -> None:
    """A real (non-probing) connect does not request quiet mode."""
    assert await api.connect() is True
    api._client.connect.assert_awaited_once_with(quiet=False)


# ---------------------------
#   disconnect / close
# ---------------------------
async def test_disconnect_closes_client_but_stays_reconnectable(
    api: TrueNASAPI,
) -> None:
    """disconnect() closes the client but leaves the API able to reconnect."""
    await api.disconnect()
    api._client.close.assert_awaited_once()
    assert await api.connect() is True


async def test_close_prevents_reconnecting(api: TrueNASAPI) -> None:
    """close() closes the client and permanently prevents reconnecting."""
    await api.close()
    api._client.close.assert_awaited_once()
    assert await api.connect() is False
    assert api.error == ERR_UNKNOWN


# ---------------------------
#   connected
# ---------------------------
def test_connected_reflects_client_state(api: TrueNASAPI) -> None:
    """connected() reflects the underlying client's connected state."""
    api._client.connected = True
    assert api.connected() is True
    api._client.connected = False
    assert api.connected() is False


# ---------------------------
#   connection_test
# ---------------------------
async def test_connection_test_fails_when_permanently_closed(
    closed_api: TrueNASAPI,
) -> None:
    """connection_test fails on a permanently closed API."""
    ok, error = await closed_api.connection_test()
    assert ok is False
    assert error == ERR_UNKNOWN


async def test_connection_test_fails_when_connect_raises(api: TrueNASAPI) -> None:
    """connection_test fails when connect() raises."""
    api._client.connect.side_effect = TrueNASConnectionRefusedError("refused")
    ok, error = await api.connection_test()
    assert ok is False
    assert error == ERR_CONNECTION_REFUSED


async def test_connection_test_fails_when_query_returns_none(
    connected_api: TrueNASAPI,
) -> None:
    """connection_test fails when the query returns no result."""
    connected_api._client.call.return_value = None
    ok, error = await connected_api.connection_test()
    assert ok is False
    assert error == ERR_MALFORMED_RESULT


async def test_connection_test_connects_before_querying(api: TrueNASAPI) -> None:
    """From a disconnected state, connection_test connects, then queries."""

    def _mark_connected(*, quiet: bool = False) -> None:
        api._client.connected = True

    api._client.connect.side_effect = _mark_connected
    api._client.call.return_value = {"version": "25.04", "hostname": "truenas.local"}
    ok, error = await api.connection_test()
    assert ok is True
    assert error == ""
    api._client.connect.assert_awaited_once()
    api._client.call.assert_awaited_once_with("system.info", None)


async def test_connection_test_succeeds(connected_api: TrueNASAPI) -> None:
    """connection_test succeeds and clears the error when the query returns data."""
    connected_api._client.call.return_value = {
        "version": "25.04",
        "hostname": "truenas.local",
    }
    ok, error = await connected_api.connection_test()
    assert ok is True
    assert error == ""


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({"version": "25.04"}, id="hostname_missing"),
        pytest.param({"version": "25.04", "hostname": 1}, id="hostname_not_a_string"),
    ],
)
async def test_connection_test_fails_on_malformed_hostname(
    connected_api: TrueNASAPI, payload: dict[str, Any]
) -> None:
    """A truthy-but-malformed system.info payload must not pass as success."""
    connected_api._client.call.return_value = payload
    ok, error = await connected_api.connection_test()
    assert ok is False
    assert error == ERR_MALFORMED_RESULT


# ---------------------------
#   query
# ---------------------------
async def test_query_returns_none_when_connect_fails(closed_api: TrueNASAPI) -> None:
    """query() returns None when the connection cannot be established."""
    assert await closed_api.query("system.info") is None


async def test_query_returns_data_on_success(connected_api: TrueNASAPI) -> None:
    """query() returns the raw call result on success."""
    connected_api._client.call.return_value = {"ok": True}
    assert await connected_api.query("system.info") == {"ok": True}


async def test_query_call_error_uses_reason(connected_api: TrueNASAPI) -> None:
    """query() uses the TrueNASCallError's reason as the error message."""
    connected_api._client.call.side_effect = TrueNASCallError(
        "boom", reason="invalid params"
    )
    assert await connected_api.query("system.info") is None
    assert connected_api.error == "invalid params"


async def test_query_call_error_falls_back_to_str_then_unknown(
    connected_api: TrueNASAPI,
) -> None:
    """query() falls back to the exception's string form when no reason is set."""
    connected_api._client.call.side_effect = TrueNASCallError("boom")
    assert await connected_api.query("system.info") is None
    assert connected_api.error == "boom"


async def test_query_other_truenas_error_classifies_during_call(
    connected_api: TrueNASAPI,
) -> None:
    """query() classifies a non-TrueNASCallError exception via _classify_exception."""
    connected_api._client.call.side_effect = TrueNASCallTimeoutError("timeout")
    assert await connected_api.query("system.info") is None
    assert connected_api.error == ERR_TIMEOUT


async def test_query_propagates_non_truenas_exceptions(
    connected_api: TrueNASAPI,
) -> None:
    """Non-TrueNASError exceptions are deliberately not swallowed by query().

    The aiotruenas client only raises TrueNASError subclasses; anything else
    indicates a bug and must surface to the caller (the coordinator wraps
    each poll job defensively), so query() lets it propagate instead of
    mapping it to an ERR_* code.
    """
    connected_api._client.call.side_effect = RuntimeError("unexpected bug")
    with pytest.raises(RuntimeError, match="unexpected bug"):
        await connected_api.query("system.info")


async def test_query_logs_summarized_payload_when_debug_enabled(
    connected_api: TrueNASAPI,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """query() logs a summarized payload at DEBUG level."""
    connected_api._client.call.return_value = {"ok": True}
    with caplog.at_level("DEBUG", logger=api_module.__name__):
        assert await connected_api.query("system.info") == {"ok": True}
    assert "dict[1 keys]" in caplog.text


async def test_query_permission_denied_logs_debug_not_error(
    connected_api: TrueNASAPI,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A read-only API key's EACCES on an admin-only method (issue #46) must stay quiet.

    DEBUG, no traceback -- not an ERROR flooding the log every poll cycle.
    """
    connected_api._client.call.side_effect = TrueNASCallError(
        "Not authorized", code=13, errname="EACCES", reason="[EACCES] Not authorized"
    )
    with caplog.at_level("DEBUG", logger=api_module.__name__):
        assert await connected_api.query("smb.status") is None
    assert connected_api.error == "[EACCES] Not authorized"
    assert not any(record.levelname == "ERROR" for record in caplog.records)
    debug_records = [record for record in caplog.records if record.levelname == "DEBUG"]
    assert any("API error" in record.getMessage() for record in debug_records)
    assert all(record.exc_info is None for record in debug_records)


async def test_query_non_permission_call_error_still_logs_error(
    connected_api: TrueNASAPI,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A non-permission TrueNASCallError still logs an ERROR with traceback."""
    exc = TrueNASCallError("boom", code=22, errname="EINVAL", reason="bad params")
    connected_api._client.call.side_effect = exc
    with caplog.at_level("DEBUG", logger=api_module.__name__):
        assert await connected_api.query("system.info") is None
    error_records = [record for record in caplog.records if record.levelname == "ERROR"]
    assert error_records
    assert all(record.exc_info is not None for record in error_records)
    expected_message = ERROR_API_FORMAT % ("truenas.local", "system.info", exc)
    assert any(record.getMessage() == expected_message for record in error_records)


# ---------------------------
#   error / scheme properties
# ---------------------------
def test_error_property_defaults_empty(api: TrueNASAPI) -> None:
    """The error property defaults to an empty string."""
    assert api.error == ""


# ---------------------------
#   subscribe_events / unsubscribe_events
# ---------------------------
async def test_subscribe_events_returns_queue(connected_api: TrueNASAPI) -> None:
    """subscribe_events returns the subscription id and queue on success."""
    mock_queue = MagicMock()
    connected_api._client.subscribe = AsyncMock(return_value=("sub-123", mock_queue))
    sub_id, queue = await connected_api.subscribe_events("app.stats")
    assert sub_id == "sub-123"
    assert queue is mock_queue


async def test_subscribe_events_returns_none_on_failure(
    connected_api: TrueNASAPI,
) -> None:
    """subscribe_events returns None, None and records the error on failure."""
    connected_api._client.subscribe = AsyncMock(
        side_effect=TrueNASCallError("boom", reason="nope")
    )
    sub_id, queue = await connected_api.subscribe_events("app.stats")
    assert sub_id is None
    assert queue is None
    assert connected_api.error == "nope"


async def test_subscribe_events_permission_denied_logs_debug_not_error(
    connected_api: TrueNASAPI,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A permission-denied subscribe failure logs DEBUG, not ERROR."""
    connected_api._client.subscribe = AsyncMock(
        side_effect=TrueNASCallError(
            "Not authorized",
            code=13,
            errname="EACCES",
            reason="[EACCES] Not authorized",
        )
    )
    with caplog.at_level("DEBUG", logger=api_module.__name__):
        sub_id, queue = await connected_api.subscribe_events("app.stats")
    assert sub_id is None
    assert queue is None
    assert not any(record.levelname == "ERROR" for record in caplog.records)


async def test_subscribe_events_non_permission_call_error_still_logs_error(
    connected_api: TrueNASAPI,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A non-permission subscribe failure still logs an ERROR with traceback."""
    exc = TrueNASCallError("boom", code=22, errname="EINVAL", reason="bad params")
    connected_api._client.subscribe = AsyncMock(side_effect=exc)
    with caplog.at_level("DEBUG", logger=api_module.__name__):
        sub_id, queue = await connected_api.subscribe_events("app.stats")
    assert sub_id is None
    assert queue is None
    error_records = [record for record in caplog.records if record.levelname == "ERROR"]
    assert error_records
    assert all(record.exc_info is not None for record in error_records)
    expected_message = ERROR_API_FORMAT % ("truenas.local", "app.stats", exc)
    assert any(record.getMessage() == expected_message for record in error_records)


async def test_unsubscribe_events_calls_client(connected_api: TrueNASAPI) -> None:
    """unsubscribe_events delegates to the underlying client."""
    connected_api._client.unsubscribe = AsyncMock()
    await connected_api.unsubscribe_events("sub-123")
    connected_api._client.unsubscribe.assert_awaited_once_with("sub-123")


async def test_unsubscribe_events_handles_call_error(connected_api: TrueNASAPI) -> None:
    """unsubscribe_events swallows a TrueNASCallError without recording an error."""
    connected_api._client.unsubscribe = AsyncMock(
        side_effect=TrueNASCallError("boom", reason="no such sub")
    )
    await connected_api.unsubscribe_events("sub-123")
    assert connected_api.error == ""


async def test_unsubscribe_events_logs_only_debug_with_subscription_id(
    connected_api: TrueNASAPI,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Unsubscribe failures during expected shutdown/disconnect races stay quiet.

    Only the DEBUG log (which already carries the subscription_id for
    diagnostics) should fire; no redundant ERROR-level duplicate.
    """
    exc = TrueNASCallError("boom", code=22, errname="EINVAL", reason="bad params")
    connected_api._client.unsubscribe = AsyncMock(side_effect=exc)
    with caplog.at_level("DEBUG", logger=api_module.__name__):
        await connected_api.unsubscribe_events("sub-123")
    assert not [record for record in caplog.records if record.levelname == "ERROR"]
    debug_records = [record for record in caplog.records if record.levelname == "DEBUG"]
    assert any("sub-123" in record.getMessage() for record in debug_records)


async def test_unsubscribe_events_handles_generic_error(
    connected_api: TrueNASAPI,
) -> None:
    """unsubscribe_events maps a generic TrueNASError to ERR_UNKNOWN."""
    connected_api._client.unsubscribe = AsyncMock(
        side_effect=TrueNASError("boom"),
    )
    await connected_api.unsubscribe_events("sub-123")
    assert connected_api.error == ERR_UNKNOWN


async def test_get_subscription_events_success(connected_api: TrueNASAPI) -> None:
    """get_subscription_events returns the fetched events on success."""
    events = [
        {"id": 1, "name": "app.stats", "data": {"foo": "bar"}},
        {"id": 2, "name": "app.other", "data": {"baz": "qux"}},
    ]
    connected_api._client.get_subscription_events = AsyncMock(return_value=events)

    result = await connected_api.get_subscription_events("sub-123")

    assert len(result) == 2
    assert result[0]["id"] == 1
    assert result[1]["id"] == 2
    assert connected_api.error == ""


async def test_get_subscription_events_call_error(connected_api: TrueNASAPI) -> None:
    """get_subscription_events returns [] and records the error on TrueNASCallError."""
    connected_api._client.get_subscription_events = AsyncMock(
        side_effect=TrueNASCallError("boom", reason="nope")
    )
    result = await connected_api.get_subscription_events("sub-123")
    assert result == []
    assert connected_api.error == "nope"


async def test_get_subscription_events_permission_denied_logs_debug_not_error(
    connected_api: TrueNASAPI,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A permission-denied fetch failure logs DEBUG, not ERROR."""
    connected_api._client.get_subscription_events = AsyncMock(
        side_effect=TrueNASCallError(
            "Not authorized",
            code=13,
            errname="EACCES",
            reason="[EACCES] Not authorized",
        )
    )
    with caplog.at_level("DEBUG", logger=api_module.__name__):
        result = await connected_api.get_subscription_events("sub-123")
    assert result == []
    assert not any(record.levelname == "ERROR" for record in caplog.records)


async def test_get_subscription_events_non_permission_call_error_still_logs_error(
    connected_api: TrueNASAPI,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A non-permission fetch failure still logs an ERROR with traceback."""
    exc = TrueNASCallError("boom", code=22, errname="EINVAL", reason="bad params")
    connected_api._client.get_subscription_events = AsyncMock(side_effect=exc)
    with caplog.at_level("DEBUG", logger=api_module.__name__):
        result = await connected_api.get_subscription_events("sub-123")
    assert result == []
    error_records = [record for record in caplog.records if record.levelname == "ERROR"]
    assert error_records
    assert all(record.exc_info is not None for record in error_records)
    expected_message = ERROR_API_FORMAT % ("truenas.local", "sub-123", exc)
    assert any(record.getMessage() == expected_message for record in error_records)


async def test_get_subscription_events_generic_error(connected_api: TrueNASAPI) -> None:
    """get_subscription_events maps a generic TrueNASError to ERR_UNKNOWN."""
    connected_api._client.get_subscription_events = AsyncMock(
        side_effect=TrueNASError("boom"),
    )
    result = await connected_api.get_subscription_events("sub-123")
    assert result == []
    assert connected_api.error == ERR_UNKNOWN


async def test_subscribe_events_connect_returns_false(api: TrueNASAPI) -> None:
    """subscribe_events: connection failure when connect() returns False."""
    api._client.connected = False
    api.connect = AsyncMock(return_value=False)

    sub_id, queue = await api.subscribe_events("app.stats")

    assert sub_id is None
    assert queue is None
    assert api.error == ERR_CONNECTION_REFUSED


async def test_get_subscription_events_connect_returns_false(api: TrueNASAPI) -> None:
    """get_subscription_events: connection failure when connect() returns False."""
    api._client.connected = False
    api.connect = AsyncMock(return_value=False)

    result = await api.get_subscription_events("sub-123")

    assert result == []
    assert api.error == ERR_CONNECTION_REFUSED


async def test_is_subscribed_returns_false_when_not_connected(api: TrueNASAPI) -> None:
    """is_subscribed returns False when there is no client."""
    api._client = None
    assert await api.is_subscribed("sub-123") is False


async def test_is_subscribed_delegates_when_connected(
    connected_api: TrueNASAPI,
) -> None:
    """is_subscribed delegates to the underlying client when connected."""
    connected_api._client.is_subscribed = AsyncMock(return_value=True)
    assert await connected_api.is_subscribed("sub-123") is True
    connected_api._client.is_subscribed.assert_called_once_with("sub-123")


async def test_subscribe_events_clears_previous_error_on_success(
    connected_api: TrueNASAPI,
) -> None:
    """A successful subscribe clears any previously recorded error."""
    connected_api._error = "previous error"
    mock_queue = MagicMock()
    connected_api._client.subscribe = AsyncMock(return_value=("sub-123", mock_queue))

    sub_id, queue = await connected_api.subscribe_events("app.stats")

    assert sub_id == "sub-123"
    assert queue is mock_queue
    assert connected_api.error == ""


async def test_get_subscription_events_passes_timeout(
    connected_api: TrueNASAPI,
) -> None:
    """get_subscription_events forwards the event_timeout to the client call."""
    events = [{"id": 1}]
    connected_api._client.get_subscription_events = AsyncMock(return_value=events)

    result = await connected_api.get_subscription_events("sub-123", event_timeout=1.5)

    assert result == events
    connected_api._client.get_subscription_events.assert_awaited_once_with(
        "sub-123", event_timeout=1.5
    )
    assert connected_api.error == ""


async def test_get_subscription_events_truenas_call_error(
    connected_api: TrueNASAPI,
) -> None:
    """get_subscription_events records the stringified TrueNASCallError as the error."""
    error = TrueNASCallError("boom")
    connected_api._client.get_subscription_events = AsyncMock(side_effect=error)

    result = await connected_api.get_subscription_events("sub-123", event_timeout=1.0)

    assert result == []
    assert connected_api.error == str(error)
