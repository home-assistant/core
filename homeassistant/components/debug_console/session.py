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

# Objects kept alive for the frontend to inspect, oldest are let go first.
MAX_TRACKED_OBJECTS = 10000


@dataclass(slots=True)
class ConsoleSession:
    """State of a console session, kept per user and session ID."""

    session_id: str
    namespace: dict[str, Any]
    # Prefixes object IDs, so an ID from an earlier session, such as one from
    # before a restart, never finds an object of this one.
    instance_id: str = field(default_factory=lambda: secrets.token_hex(4))
    objects: dict[str, Any] = field(default_factory=dict)
    # The ID of each tracked object by its identity, to track it only once.
    # Identities stay valid, as tracking keeps the objects alive.
    object_ids_by_identity: dict[int, str] = field(default_factory=dict)
    object_ids: Iterator[int] = field(default_factory=partial(count, 1))
    connections: set[ActiveConnection] = field(default_factory=set)
    executions: set[asyncio.Task[Any]] = field(default_factory=set)
    cancel_expiry: CALLBACK_TYPE | None = None

    def track(self, value: Any) -> str:
        """Keep a reference to an object, so the frontend can inspect it later."""
        if (object_id := self.object_ids_by_identity.get(id(value))) is not None:
            return object_id

        object_id = f"{self.instance_id}-{next(self.object_ids)}"
        self.objects[object_id] = value
        self.object_ids_by_identity[id(value)] = object_id

        if len(self.objects) > MAX_TRACKED_OBJECTS:
            oldest_id = next(iter(self.objects))
            oldest = self.objects.pop(oldest_id)
            del self.object_ids_by_identity[id(oldest)]
        return object_id

    def release_objects(self) -> None:
        """Let go of all objects kept alive for inspection."""
        self.objects.clear()
        self.object_ids_by_identity.clear()

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
        for connection in self.connections:
            connection.subscriptions.pop(self.subscription_key, None)
        self.connections.clear()
        self.release_objects()

        if not self.executions:
            self.namespace.clear()
            return

        # Cancelled code still runs its cleanup, which may need its names.
        stopping = set(self.executions)

        def _release_namespace(execution: asyncio.Task[Any]) -> None:
            stopping.discard(execution)
            if not stopping:
                self.namespace.clear()

        for execution in stopping:
            execution.add_done_callback(_release_namespace)
            execution.cancel()


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
