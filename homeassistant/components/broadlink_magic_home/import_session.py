"""One-time Magic Home family import sessions."""

import asyncio
from dataclasses import dataclass, field
import secrets
import time

from broadlink_magic import Family

from homeassistant.core import HomeAssistant
from homeassistant.util.hass_dict import HassKey

from .const import IMPORT_TIMEOUT


@dataclass(slots=True)
class ImportSession:
    """An in-memory, one-time family import session."""

    project_id: str
    flow_id: str | None = None
    created_at: float = field(init=False)
    event: asyncio.Event = field(default_factory=asyncio.Event)
    families: list[Family] | None = None
    error: str | None = None
    consumed: bool = False

    def __post_init__(self) -> None:
        """Record when the import session was created."""
        self.created_at = time.monotonic()

    @property
    def remaining(self) -> float:
        """Return the seconds left before the import session expires."""
        return max(0.0, IMPORT_TIMEOUT - (time.monotonic() - self.created_at))

    @property
    def expired(self) -> bool:
        """Return whether the import session has expired."""
        return self.remaining == 0

    def complete(self, families: list[Family]) -> bool:
        """Complete this session once."""
        if self.consumed or self.expired:
            return False
        self.families = families
        self.consumed = True
        self.event.set()
        return True


class ImportSessionManager:
    """Store active import sessions without persisting imported payloads."""

    def __init__(self) -> None:
        """Initialize the import session manager."""
        self._sessions: dict[str, ImportSession] = {}

    def create(self, flow_id: str | None = None) -> ImportSession:
        """Create a cryptographically random import session."""
        session = ImportSession(secrets.token_urlsafe(24), flow_id=flow_id)
        self._sessions[session.project_id] = session
        return session

    @property
    def active_sessions(self) -> tuple[ImportSession, ...]:
        """Return active sessions."""
        return tuple(self._sessions.values())

    def get(self, project_id: str) -> ImportSession | None:
        """Get a non-expired import session."""
        session = self._sessions.get(project_id)
        if session is None:
            return None
        if session.expired:
            self.remove(project_id)
            return None
        return session

    def remove(self, project_id: str) -> None:
        """Remove and clear a session."""
        if session := self._sessions.pop(project_id, None):
            session.consumed = True
            session.families = None
            session.error = None
            session.event.set()


DATA_IMPORT_SESSIONS: HassKey[ImportSessionManager] = HassKey(
    "broadlink_magic_import_sessions"
)


def get_import_manager(hass: HomeAssistant) -> ImportSessionManager:
    """Return the shared import session manager."""
    if DATA_IMPORT_SESSIONS not in hass.data:
        hass.data[DATA_IMPORT_SESSIONS] = ImportSessionManager()
    return hass.data[DATA_IMPORT_SESSIONS]
