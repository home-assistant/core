"""TrueNAS API."""

import asyncio
from logging import DEBUG, ERROR, getLogger
from typing import Any

from aiotruenas import TrueNASClient
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

from homeassistant.components.diagnostics import async_redact_data

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
    TO_REDACT,
)

_LOGGER = getLogger(__name__)

# Debug payloads (e.g. pool.query) can be huge, so they get truncated.
_LOG_PAYLOAD_LIMIT = 5000

# aiotruenas exception -> ERR_* mapping (see const.py). Checked via
# isinstance() in order, so subclasses must precede their base classes.
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
    data = async_redact_data(data, TO_REDACT)
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


def _log_call_error(host: str, context: str, exc: TrueNASCallError) -> None:
    """Log a TrueNAS call error, quietly for expected EACCES permission errors."""
    permission_denied = exc.errname == "EACCES"
    _LOGGER.log(
        DEBUG if permission_denied else ERROR,
        ERROR_API_FORMAT,
        host,
        context,
        exc,
        exc_info=None if permission_denied else exc,
    )


class TrueNASAPI:
    """Thin async adapter around aiotruenas.TrueNASClient.

    Returns ``None`` on error (and records an ``ERR_*`` code) instead of raising.
    """

    def __init__(
        self,
        host: str,
        api_key: str,
        verify_ssl: bool = True,
        scheme: str = "wss",
    ) -> None:
        """Initialize the TrueNAS API.

        ``host`` must be bare (no scheme/path); callers (``helper.sanitize_host``)
        are expected to normalize user input before constructing this class.
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

    async def connect(self, *, quiet: bool = False) -> bool:
        """Connect and log in. Return connected boolean.

        ``quiet``: log failures at debug (used by zeroconf probing, where
        most connection attempts are expected to fail).
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
            await self._client.connect(quiet=quiet)
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

    async def disconnect(self) -> None:
        """Close the WebSocket connection (reconnectable)."""
        await self._client.close()

    async def close(self) -> None:
        """Permanently close the API."""
        self._closed = True
        await self._client.close()

    def connected(self) -> bool:
        """Return connected boolean."""
        return self._client is not None and self._client.connected

    async def connection_test(self) -> tuple[bool, str]:
        """Test connection."""
        if not await self.connect():
            return self.connected(), self._error

        result = await self.query("system.info")
        if not isinstance(result, dict) or not result.get("hostname"):
            self._error = self._error or ERR_MALFORMED_RESULT
            return False, self._error

        return True, ""

    async def query(
        self,
        service: str,
        params: dict[str, Any] | list[Any] | None = None,
    ) -> Any:
        """Retrieve data from TrueNAS."""
        if not self.connected() and not await self.connect():
            return None

        self._error = ""
        if _LOGGER.isEnabledFor(DEBUG):
            _LOGGER.debug(
                "TrueNAS %s query: %s, %s",
                self._host,
                service,
                async_redact_data(params, TO_REDACT),
            )

        try:
            data = await self._client.call(service, params)
        except TrueNASCallError as exc:
            self._error = exc.reason or str(exc) or ERR_UNKNOWN
            _log_call_error(self._host, service, exc)
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

    async def subscribe_events(
        self, event: str
    ) -> tuple[str, asyncio.Queue[Any]] | tuple[None, None]:
        """Subscribe to an event and return (subscription_id, queue).

        Queue yields dict payloads or aiotruenas's private terminator
        sentinel; treat any non-dict item as end-of-subscription. ``Any``
        (not ``object``) stays structurally compatible with that private
        type without importing it.
        """
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
            _log_call_error(self._host, event, exc)
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
        except TrueNASCallError as exc:
            self._error = exc.reason or str(exc) or ERR_UNKNOWN
            _log_call_error(self._host, subscription_id, exc)
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
        else:
            if events:
                _LOGGER.debug(
                    "TrueNAS %s get_subscription_events drained %d events: %s",
                    self._host,
                    len(events),
                    _summarize_payload(events),
                )
            return events

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
