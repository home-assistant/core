"""TrueNAS API."""

import asyncio
import contextlib
import contextvars
from collections.abc import Iterator
from logging import DEBUG, ERROR, Filter, LogRecord, getLogger
from typing import Any, override

from aiotruenas import TrueNASClient
from aiotruenas.client import _SubscriptionTerminator
from aiotruenas.exceptions import (
    TrueNASAuthenticationError,
    TrueNASCallError,
    TrueNASCallTimeoutError,
    TrueNASCertificateVerificationError,
    TrueNASConnectionClosedError,
    TrueNASConnectionRefusedError,
    TrueNASEndpointNotFoundError,
    TrueNASError,
    TrueNASHandshakeTimeoutError,
    TrueNASHostUnknownError,
    TrueNASHttpSchemeError,
    TrueNASMalformedResponseError,
    TrueNASProxyInterceptedError,
    TrueNASUnsupportedTlsVersionError,
    TrueNASWebSocketUnsupportedError,
)

from .const import (
    ERR_API_NOT_FOUND,
    ERR_CERT_VERIFY_FAILED,
    ERR_CONNECTION_REFUSED,
    ERR_HANDSHAKE_TIMEOUT,
    ERR_HTTP_USED,
    ERR_INVALID_KEY,
    ERR_LOST_LOGIN,
    ERR_LOST_QUERY,
    ERR_MALFORMED_RESULT,
    ERR_PROXY_INTERCEPTED,
    ERR_TIMEOUT,
    ERR_TLS_NOT_SUPPORTED,
    ERR_UNKNOWN,
    ERR_UNKNOWN_HOSTNAME,
    ERR_WS_NOT_SUPPORTED,
    ERROR_API_FORMAT,
)

_LOGGER = getLogger(__name__)

# Maximum number of characters of an API payload to include in debug logs.
# Full payloads can be huge (e.g. pool.query with topology or app.query), so
# they are summarized and truncated to keep debug logs readable.
_LOG_PAYLOAD_LIMIT = 5000

# Set for the duration of a quiet connect() so the filter below can drop
# aiotruenas's own "verify_ssl=False" warning for that call only. A plain
# module-level flag would leak across concurrent connects (e.g. a real,
# non-quiet connection racing a zeroconf probe); a ContextVar stays scoped to
# the current asyncio task instead.
_quiet_insecure_tls_warning: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "_quiet_insecure_tls_warning", default=False
)

# Message aiotruenas.client logs at WARNING from its own TrueNASClient
# whenever verify_ssl=False, unconditionally -- including for every zeroconf
# probe candidate, most of which are unrelated devices on the network
# (reported as a second follow-up on issue #46). It is genuinely useful for a
# user's real, configured connection, so it is only filtered out while
# _quiet_insecure_tls_warning is set, i.e. during probing.
_INSECURE_TLS_WARNING_PREFIX = "TrueNASClient configured with verify_ssl=False"


class _QuietInsecureTlsWarningFilter(Filter):
    """Drop aiotruenas's insecure-TLS warning while probing quietly."""

    @override
    def filter(self, record: LogRecord) -> bool:
        return not (
            _quiet_insecure_tls_warning.get()
            and record.getMessage().startswith(_INSECURE_TLS_WARNING_PREFIX)
        )


getLogger("aiotruenas.client").addFilter(_QuietInsecureTlsWarningFilter())


@contextlib.contextmanager
def _quiet_insecure_tls_warnings(active: bool) -> Iterator[None]:
    """Drop aiotruenas's insecure-TLS warning for the duration of the block.

    No-op unless ``active``, so a real (non-probing) connect still sees the
    warning.
    """
    if not active:
        yield
        return

    token = _quiet_insecure_tls_warning.set(True)
    try:
        yield
    finally:
        _quiet_insecure_tls_warning.reset(token)


# aiotruenas exception -> ERR_* mapping (see const.py). Order matters: more
# specific subclasses must be checked before their base classes, so this is
# consulted via isinstance() in declaration order rather than a plain dict
# keyed by exact type.
_EXCEPTION_ERR_MAP: tuple[tuple[type[TrueNASError], str], ...] = (
    (TrueNASCertificateVerificationError, ERR_CERT_VERIFY_FAILED),
    (TrueNASHttpSchemeError, ERR_HTTP_USED),
    (TrueNASUnsupportedTlsVersionError, ERR_TLS_NOT_SUPPORTED),
    (TrueNASWebSocketUnsupportedError, ERR_WS_NOT_SUPPORTED),
    (TrueNASHostUnknownError, ERR_UNKNOWN_HOSTNAME),
    (TrueNASConnectionRefusedError, ERR_CONNECTION_REFUSED),
    (TrueNASProxyInterceptedError, ERR_PROXY_INTERCEPTED),
    (TrueNASEndpointNotFoundError, ERR_API_NOT_FOUND),
    (TrueNASHandshakeTimeoutError, ERR_HANDSHAKE_TIMEOUT),
    (TrueNASCallTimeoutError, ERR_TIMEOUT),
    (TrueNASAuthenticationError, ERR_INVALID_KEY),
    (TrueNASMalformedResponseError, ERR_MALFORMED_RESULT),
)


def _summarize_payload(data: Any, limit: int = _LOG_PAYLOAD_LIMIT) -> str:
    """Return a compact, length-bounded description of an API payload."""
    if isinstance(data, list):
        shape = f"list[{len(data)}]"
    elif isinstance(data, dict):
        shape = f"dict[{len(data)} keys]"
    else:
        shape = type(data).__name__

    text = repr(data)
    if len(text) > limit:
        text = f"{text[:limit]}... (truncated, {len(text)} chars total)"
    return f"{shape} {text}"


def _classify_exception(exc: TrueNASError, *, during_call: bool) -> str:
    """Map an aiotruenas exception to one of this integration's ERR_* codes."""
    if isinstance(exc, TrueNASConnectionClosedError):
        return ERR_LOST_QUERY if during_call else ERR_LOST_LOGIN

    return next(
        (
            err_code
            for exc_type, err_code in _EXCEPTION_ERR_MAP
            if isinstance(exc, exc_type)
        ),
        ERR_UNKNOWN,
    )


def _log_call_error(host: str, exc: TrueNASCallError) -> None:
    """Log a TrueNAS call error, quietly for expected permission errors.

    A read-only-scoped API key gets an ``EACCES`` response from admin-only
    methods (e.g. ``smb.status``). That is a permanent, expected condition
    for that key -- not an integration bug -- so logging it at ERROR with a
    full traceback on every call would flood the log for no benefit; log it
    at debug instead.
    """
    permission_denied = exc.errname == "EACCES"
    _LOGGER.log(
        DEBUG if permission_denied else ERROR,
        ERROR_API_FORMAT,
        host,
        exc,
        exc_info=None if permission_denied else exc,
    )


# ---------------------------
#   TrueNASAPI
# ---------------------------
class TrueNASAPI:
    """Thin async adapter around aiotruenas.TrueNASClient.

    Preserves the public shape of the previous sync/thread-based
    implementation (``connect``/``connected``/``query``/``connection_test``/
    ``disconnect``/``close``/``error``/``scheme``) so callers only need to add
    ``await``; error handling still returns ``None`` on failure and records an
    ``ERR_*`` code (see const.py) instead of raising, matching the rest of the
    integration's defensive style.
    """

    def __init__(
        self,
        host: str,
        api_key: str,
        verify_ssl: bool = True,
        scheme: str = "wss",
    ) -> None:
        """Initialize the TrueNAS API.

        Parameters
        ----------
        host:
            Bare TrueNAS hostname or IP address without scheme or path
            (for example, ``"truenas.local"`` or ``"192.168.1.10"``).
            Values containing a URL scheme (``"://"``) or path (``"/"``)
            are rejected to prevent malformed WebSocket URLs.
        api_key:
            API key used to authenticate with the TrueNAS API.
        verify_ssl:
            Whether to verify the SSL certificate when using ``wss``.
        scheme:
            WebSocket scheme, either ``"ws"`` or ``"wss"`` (default).
        """
        scheme = scheme.lower()
        if scheme not in ("ws", "wss"):
            raise ValueError(
                f"Invalid WebSocket scheme '{scheme}'. Expected 'ws' or 'wss'."
            )

        self._host = host
        self._scheme = scheme
        self._error = ""
        self._closed = False
        self._client = TrueNASClient(
            host,
            api_key,
            verify_ssl=verify_ssl,
            use_tls=(scheme == "wss"),
        )

    # ---------------------------
    #   connect
    # ---------------------------
    async def connect(self, *, quiet: bool = False) -> bool:
        """Connect and log in. Return connected boolean.

        Parameters
        ----------
        quiet:
            Log a connection failure at debug instead of error, and drop
            aiotruenas's own "verify_ssl=False" warning too. Used by zeroconf
            discovery, which probes many non-TrueNAS devices on the network
            and expects most connection attempts to fail -- logging those at
            error with a full traceback (or the insecure-TLS warning, which
            fires before the failure is even known) would flood the log for
            no benefit.
        """
        if self._closed:
            self._error = ERR_UNKNOWN
            _LOGGER.error(
                "TrueNAS %s: cannot connect, API was permanently closed", self._host
            )
            return False

        if self._client.connected:
            return True

        try:
            with _quiet_insecure_tls_warnings(quiet):
                await self._client.connect()
        except TrueNASError as exc:
            self._error = _classify_exception(exc, during_call=False)
            _LOGGER.log(
                DEBUG if quiet else ERROR,
                "Error while communicating with host %s: %s",
                self._host,
                exc,
                exc_info=None if quiet else exc,
            )
            return False

        self._error = ""
        return True

    # ---------------------------
    #   disconnect / close
    # ---------------------------
    async def disconnect(self) -> None:
        """Close the WebSocket connection (reconnectable)."""
        await self._client.close()

    async def close(self) -> None:
        """Permanently close the API."""
        self._closed = True
        await self._client.close()

    # ---------------------------
    #   connected
    # ---------------------------
    def connected(self) -> bool:
        """Return connected boolean."""
        return self._client is not None and self._client.connected

    # ---------------------------
    #   connection_test
    # ---------------------------
    async def connection_test(self) -> tuple[bool, str]:
        """Test connection."""
        if not await self.connect():
            return self.connected(), self._error

        result = await self.query("system.info")
        if result is None:
            self._error = self._error or ERR_MALFORMED_RESULT
            return False, self._error

        return True, ""

    # ---------------------------
    #   query
    # ---------------------------
    async def query(
        self,
        service: str,
        params: dict[str, Any] | list[Any] | None = None,
    ) -> Any:
        """Retrieve data from TrueNAS."""
        if not self.connected() and not await self.connect():
            return None

        self._error = ""
        _LOGGER.debug("TrueNAS %s query: %s, %s", self._host, service, params)

        try:
            data = await self._client.call(service, params)
        except TrueNASCallError as exc:
            self._error = exc.reason or str(exc) or ERR_UNKNOWN
            _log_call_error(self._host, exc)
            return None
        except TrueNASError as exc:
            self._error = _classify_exception(exc, during_call=True)
            _LOGGER.warning(
                'TrueNAS %s unable to fetch data "%s" (%s)',
                self._host,
                service,
                exc,
            )
            return None

        if _LOGGER.isEnabledFor(DEBUG):
            _LOGGER.debug(
                "TrueNAS %s query (%s) response: %s",
                self._host,
                service,
                _summarize_payload(data),
            )

        return data

    # ---------------------------
    #   subscribe_events
    # ---------------------------
    async def subscribe_events(
        self, event: str
    ) -> (
        tuple[str, asyncio.Queue[dict[str, Any] | _SubscriptionTerminator]]
        | tuple[None, None]
    ):
        """Subscribe to an event and return (subscription_id, queue)."""
        if not self.connected() and not await self.connect():
            self._error = self._error or ERR_CONNECTION_REFUSED
            _LOGGER.warning(
                "TrueNAS %s subscribe_events: connection failed for %s",
                self._host,
                event,
            )
            return None, None

        self._error = ""
        _LOGGER.debug("TrueNAS %s subscribe_events: %s", self._host, event)

        try:
            return await self._client.subscribe(event)
        except TrueNASCallError as exc:
            self._error = exc.reason or str(exc) or ERR_UNKNOWN
            _log_call_error(self._host, exc)
            return None, None
        except TrueNASError as exc:
            self._error = _classify_exception(exc, during_call=True)
            _LOGGER.warning(
                'TrueNAS %s unable to subscribe to events "%s" (%s)',
                self._host,
                event,
                exc,
            )
            return None, None

    # ---------------------------
    #   unsubscribe_events
    # ---------------------------
    async def unsubscribe_events(self, subscription_id: str) -> None:
        """Unsubscribe from a TrueNAS event."""
        if not self.connected():
            _LOGGER.debug(
                "TrueNAS %s unsubscribe_events: client not connected,"
                " skipping unsubscribe for %s",
                self._host,
                subscription_id,
            )
            return

        _LOGGER.debug("TrueNAS %s unsubscribe_events: %s", self._host, subscription_id)

        try:
            await self._client.unsubscribe(subscription_id)
        except TrueNASCallError as exc:
            _LOGGER.debug(
                "TrueNAS %s failed to unsubscribe %s: %s",
                self._host,
                subscription_id,
                exc,
            )
            _LOGGER.exception(ERROR_API_FORMAT, self._host, exc)
        except TrueNASError as exc:
            self._error = _classify_exception(exc, during_call=True)
            _LOGGER.warning(
                "TrueNAS %s unable to unsubscribe_events %s (%s)",
                self._host,
                subscription_id,
                exc,
            )

    async def get_subscription_events(
        self, subscription_id: str, event_timeout: float | None = None
    ) -> list[dict[str, Any]]:
        """Read events from a subscription queue."""
        if not self.connected() and not await self.connect():
            self._error = self._error or ERR_CONNECTION_REFUSED
            _LOGGER.warning(
                "TrueNAS %s get_subscription_events: connection failed for %s",
                self._host,
                subscription_id,
            )
            return []

        self._error = ""
        _LOGGER.debug(
            "TrueNAS %s get_subscription_events: %s", self._host, subscription_id
        )

        try:
            events = await self._client.get_subscription_events(
                subscription_id, event_timeout=event_timeout
            )
            if events:
                _LOGGER.debug(
                    "TrueNAS %s get_subscription_events drained %d events: %s",
                    self._host,
                    len(events),
                    _summarize_payload(events),
                )
            return events
        except TrueNASCallError as exc:
            self._error = exc.reason or str(exc) or ERR_UNKNOWN
            _log_call_error(self._host, exc)
            return []
        except TrueNASError as exc:
            self._error = _classify_exception(exc, during_call=True)
            _LOGGER.warning(
                "TrueNAS %s unable to read subscription events %s (%s)",
                self._host,
                subscription_id,
                exc,
            )
            return []

    async def is_subscribed(self, subscription_id: str) -> bool:
        """Check if a subscription is currently active in the client."""
        if not self.connected():
            return False
        return await self._client.is_subscribed(subscription_id)

    @property
    def error(self) -> str:
        """Return error."""
        return self._error

    @property
    def scheme(self) -> str:
        """Return the scheme used for the WebSocket."""
        return self._scheme
