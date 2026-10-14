"""Sessions of the Debug console, one per user and browser tab."""

import asyncio
import builtins
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime
from functools import partial
from itertools import count
import secrets
from typing import Any

from homeassistant.components.websocket_api import ActiveConnection
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later

from .const import DATA_CONSOLE_SESSIONS, DOMAIN, SESSION_TIMEOUT
from .execution import console_print

# Connections release their session on close, by riding along on the cleanup
# of the connection subscriptions.
CONSOLE_SUBSCRIPTION_KEY = DOMAIN


@dataclass(slots=True)
class ConsoleSession:
    """State of a console session, kept per user and session ID."""

    session_id: str
    namespace: dict[str, Any]
    # Prefixes object IDs, so an ID from an earlier session, such as one from
    # before a restart, never finds an object of this one.
    instance_id: str = field(default_factory=lambda: secrets.token_hex(4))
    objects: dict[str, Any] = field(default_factory=dict)
    object_ids: Iterator[int] = field(default_factory=partial(count, 1))
    connections: set[ActiveConnection] = field(default_factory=set)
    executions: set[asyncio.Task[Any]] = field(default_factory=set)
    cancel_expiry: CALLBACK_TYPE | None = None

    def track(self, value: Any) -> str:
        """Keep a reference to an object, so the frontend can inspect it later."""
        object_id = f"{self.instance_id}-{next(self.object_ids)}"
        self.objects[object_id] = value
        return object_id

    @property
    def subscription_key(self) -> tuple[str, str]:
        """Return the key of the session in the subscriptions of a connection."""
        return (CONSOLE_SUBSCRIPTION_KEY, self.session_id)

    @callback
    def async_close(self) -> None:
        """Stop the session and let go of everything it holds."""
        if self.cancel_expiry is not None:
            self.cancel_expiry()
            self.cancel_expiry = None
        for execution in self.executions:
            execution.cancel()
        for connection in self.connections:
            connection.subscriptions.pop(self.subscription_key, None)
        self.connections.clear()
        self.objects.clear()
        self.namespace.clear()


@callback
def async_get_session(
    hass: HomeAssistant, connection: ActiveConnection, session_id: str
) -> ConsoleSession:
    """Return a console session of the user, creating it when needed."""
    sessions = hass.data.setdefault(DATA_CONSOLE_SESSIONS, {})
    key = (connection.user.id, session_id)
    if (session := sessions.get(key)) is None:
        session = sessions[key] = ConsoleSession(
            session_id=session_id,
            namespace={
                "__builtins__": builtins,
                "__name__": "__console__",
                "hass": hass,
            },
        )
        session.namespace["print"] = partial(console_print, session)

    if session.cancel_expiry is not None:
        session.cancel_expiry()
        session.cancel_expiry = None

    if connection not in session.connections:
        session.connections.add(connection)
        connection.subscriptions[session.subscription_key] = partial(
            _async_release_session, hass, key, session, connection
        )
    return session


@callback
def async_drop_sessions(hass: HomeAssistant) -> None:
    """Drop all sessions, releasing everything they keep alive."""
    for session in hass.data.pop(DATA_CONSOLE_SESSIONS, {}).values():
        session.async_close()


@callback
def _async_release_session(
    hass: HomeAssistant,
    key: tuple[str, str],
    session: ConsoleSession,
    connection: ActiveConnection,
) -> None:
    """Release a session, expiring it a while after its last connection closed."""
    sessions = hass.data.get(DATA_CONSOLE_SESSIONS, {})
    if sessions.get(key) is not session:
        # Dropped when the console got disabled, maybe replaced since.
        return

    session.connections.discard(connection)
    if session.connections:
        return

    @callback
    def _async_expire(_now: datetime) -> None:
        session.cancel_expiry = None
        if sessions.get(key) is session:
            del sessions[key]
        session.async_close()

    if session.cancel_expiry is not None:
        session.cancel_expiry()
    session.cancel_expiry = async_call_later(hass, SESSION_TIMEOUT, _async_expire)
