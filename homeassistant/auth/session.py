"""Session auth module."""
from collections.abc import Callable
import dataclasses
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
import secrets
from typing import Any, TypedDict

from aiohttp.web import Request
from aiohttp_session import get_session, new_session
from cryptography.fernet import Fernet

from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .models import RefreshToken

_LOGGER = logging.getLogger(__name__)

ABSOLUTE_TIMEOUT = timedelta(hours=4)
IDLE_TIMEOUT = timedelta(minutes=15)
IDLE_TIMEOUT_SECONDS = IDLE_TIMEOUT.total_seconds()
TEMP_TIMEOUT = timedelta(minutes=5)
TRANSITION_TIMEOUT = timedelta(seconds=10)

SESSION_ID = "id"
STORAGE_VERSION = 1
STORAGE_KEY = "auth.session"


@dataclass
class UnauthorizedTempSessionData:
    """Session data for accessing unauthorized resources for a short period of time."""

    absolute_expiry: datetime = dt_util.utcnow() + TEMP_TIMEOUT


@dataclass
class UnauthorizedRefreshTokenSessionData:
    """Session data for accessing unauthorized resources using a reference to a valid refresh token."""

    refresh_token_id: str


@dataclass
class AuthorizedSessionData:
    """Session data for accessing authorized resources."""

    refresh_token_id: str
    absolute_expiry: datetime = dt_util.utcnow() + ABSOLUTE_TIMEOUT
    idle_expiry: datetime = dt_util.utcnow() + IDLE_TIMEOUT


class StoreData(TypedDict):
    """Data to store."""

    authorized_sessions: dict[str, dict[str, Any]]
    unauthorized_sessions: dict[str, dict[str, Any]]
    key: str


def _validate_authorized_session_data(
    now: datetime, data: AuthorizedSessionData
) -> bool:
    """Validate an authorized session data."""
    if now <= data.absolute_expiry and now <= data.idle_expiry:
        return True
    return False


class SessionManager:
    """Session manager."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the strict connection manager."""
        self._hass = hass
        self._unauthorized_sessions: dict[
            str, UnauthorizedTempSessionData | UnauthorizedRefreshTokenSessionData
        ] = {}
        self._authorized_sessions: dict[str, AuthorizedSessionData] = {}
        self._store = Store[StoreData](
            hass, STORAGE_VERSION, STORAGE_KEY, private=True, atomic_writes=True
        )
        self._key: str = None  # type: ignore[assignment]
        self._refresh_token_revoce_callbacks: dict[str, CALLBACK_TYPE] = {}

    @property
    def key(self) -> str:
        """Return the encryption key."""
        return self._key

    async def async_validate_session(
        self,
        request: Request,
        set_refresh_token_on_request: Callable[[RefreshToken], None],
    ) -> None | bool:
        """Check if a request has a valid session and if that session authenticated the user.

        Return values:
        - None -> No session or a invalid one was provided
        - False -> A session was provided to access unauthenticated resources
        - True -> A session was provided to access authenticated resources
        """
        result = await self._async_validate_session(
            request, set_refresh_token_on_request
        )
        if result is None:
            # Delete session by creating an empty session
            await new_session(request)
        return result

    async def _async_validate_session(
        self,
        request: Request,
        set_refresh_token_on_request: Callable[[RefreshToken], None],
    ) -> None | bool:
        session = await get_session(request)
        if session.new or not (session_id := session.get(SESSION_ID)):
            return None

        refresh_token_id = None
        now = dt_util.utcnow()
        auth_session_data = None
        data: None | UnauthorizedTempSessionData | UnauthorizedRefreshTokenSessionData | AuthorizedSessionData

        if data := self._authorized_sessions.get(session_id):
            if _validate_authorized_session_data(now, data):
                refresh_token_id = data.refresh_token_id
                auth_session_data = data
            else:
                self._authorized_sessions.pop(session_id)

        if not auth_session_data and (
            data := self._unauthorized_sessions.get(session_id)
        ):
            if (
                isinstance(data, UnauthorizedTempSessionData)
                and now <= data.absolute_expiry
            ):
                return False
            if isinstance(data, UnauthorizedRefreshTokenSessionData):
                refresh_token_id = data.refresh_token_id

        if refresh_token_id and (
            refresh := self._hass.auth.async_get_refresh_token(refresh_token_id)
        ):
            if auth_session_data:
                set_refresh_token_on_request(refresh)

                # Update idle expiry
                auth_session_data.idle_expiry = now + IDLE_TIMEOUT
                self._async_schedule_save(IDLE_TIMEOUT_SECONDS)

                # If the session is close to expiring, create a new session
                if (
                    auth_session_data.idle_expiry > auth_session_data.absolute_expiry
                    and now + TRANSITION_TIMEOUT < auth_session_data.absolute_expiry
                ):
                    await self.async_create_session(request, refresh)
                return True
            return False

        self._authorized_sessions.pop(session_id, None)
        self._unauthorized_sessions.pop(session_id, None)
        self._async_schedule_save()
        await new_session(request)
        return None  # todo raise instead for ban?

    @callback
    def _async_invalidate_auth_sessions(self, refresh_token: RefreshToken) -> None:
        """Invalidate all sessions for a refresh token."""
        refresh_token_id = refresh_token.id
        for session_id, data in self._authorized_sessions.items():
            if data.refresh_token_id == refresh_token_id:
                self._authorized_sessions.pop(session_id)
                self._unauthorized_sessions.pop(session_id, None)
        self._async_schedule_save()

    @callback
    def _async_register_revoke_token_callback(self, refresh_token_id: str) -> None:
        """Register a callback to revoke all sessions for a refresh token."""
        if refresh_token_id in self._refresh_token_revoce_callbacks:
            return

        @callback
        def async_invalidate_auth_sessions() -> None:
            """Invalidate all sessions for a refresh token."""
            for session_id, data in self._authorized_sessions.items():
                if data.refresh_token_id == refresh_token_id:
                    self._authorized_sessions.pop(session_id)
                    self._unauthorized_sessions.pop(session_id, None)
            self._async_schedule_save()

        self._refresh_token_revoce_callbacks[
            refresh_token_id
        ] = self._hass.auth.async_register_revoke_token_callback(
            refresh_token_id, async_invalidate_auth_sessions
        )

    async def async_create_session(
        self,
        request: Request,
        refresh_token: RefreshToken,
    ) -> None:
        """Create new session for given refresh token."""
        if not self._hass.auth.async_get_refresh_token(refresh_token.id):
            return

        now_plus_transition = dt_util.utcnow() + TRANSITION_TIMEOUT
        for session_id, data in self._authorized_sessions.items():
            if data.refresh_token_id == refresh_token.id:
                if now_plus_transition < data.absolute_expiry:
                    data.absolute_expiry = now_plus_transition
                self._unauthorized_sessions.pop(session_id, None)

        self._async_register_revoke_token_callback(refresh_token.id)
        session_id = await self._async_create_new_session(request)
        self._authorized_sessions[session_id] = AuthorizedSessionData(
            refresh_token_id=refresh_token.id
        )
        self._unauthorized_sessions[session_id] = UnauthorizedRefreshTokenSessionData(
            refresh_token_id=refresh_token.id
        )
        self._async_schedule_save()

    async def async_create_temp_unauthorized_session(self, request: Request) -> None:
        """Create a temporary unauthorized session."""
        session_id = await self._async_create_new_session(
            request, max_age=int(TEMP_TIMEOUT.total_seconds())
        )
        self._unauthorized_sessions[session_id] = UnauthorizedTempSessionData()

    async def _async_create_new_session(
        self,
        request: Request,
        *,
        max_age: int | None = None,
    ) -> str:
        session_id = secrets.token_hex(64)

        session = await new_session(request)
        session[SESSION_ID] = session_id
        if max_age is not None:
            session.max_age = max_age
        return session_id

    @callback
    def _async_schedule_save(self, delay: float = 1) -> None:
        """Save sessions."""
        self._store.async_delay_save(self._data_to_save, delay)

    @callback
    def _data_to_save(self) -> StoreData:
        """Return the data to store."""
        now = dt_util.utcnow()
        authorized_sessions = {
            session_id: dataclasses.asdict(data)
            for session_id, data in self._authorized_sessions.items()
            if _validate_authorized_session_data(now, data)
        }
        unauthorized_sessions = {
            session_id: dataclasses.asdict(data)
            for session_id, data in self._unauthorized_sessions.items()
            if isinstance(data, UnauthorizedRefreshTokenSessionData)
        }
        return StoreData(
            authorized_sessions=authorized_sessions,
            unauthorized_sessions=unauthorized_sessions,
            key=self._key,
        )

    async def async_load(self) -> None:
        """Load sessions."""
        data = await self._store.async_load()
        if data is None or not isinstance(data, dict):
            self._set_defaults()
            return

        self._key = data["key"]
        self._unauthorized_sessions = {
            session_id: UnauthorizedRefreshTokenSessionData(
                refresh_token_id=session_data["refresh_token_id"]
            )
            for session_id, session_data in data["unauthorized_sessions"].items()
        }
        for session_id, session_data in data["authorized_sessions"].items():
            self._authorized_sessions[session_id] = AuthorizedSessionData(
                refresh_token_id=session_data["refresh_token_id"],
                absolute_expiry=session_data["absolute_expiry"],
                idle_expiry=session_data["idle_expiry"],
            )
            self._async_register_revoke_token_callback(session_data["refresh_token_id"])

    @callback
    def _set_defaults(self) -> None:
        """Set default values."""
        self._authorized_sessions = {}
        self._unauthorized_sessions = {}
        self._key = generate_key()
        self._async_schedule_save(0)


def generate_key() -> str:
    """Generate a random key."""
    return Fernet.generate_key().decode()
