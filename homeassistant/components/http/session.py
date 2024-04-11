"""Session http module."""

from functools import lru_cache
import logging

from aiohttp.web import Request, StreamResponse
from aiohttp_session import Session, SessionData
from aiohttp_session.cookie_storage import EncryptedCookieStorage
from cryptography.fernet import InvalidToken

from homeassistant.auth.const import REFRESH_TOKEN_EXPIRATION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.json import json_dumps
from homeassistant.helpers.network import is_cloud_connection
from homeassistant.util.json import JSON_DECODE_EXCEPTIONS, json_loads

from .ban import process_wrong_login

_LOGGER = logging.getLogger(__name__)

COOKIE_NAME = "SC"
PREFIXED_COOKIE_NAME = f"__Host-{COOKIE_NAME}"
SESSION_CACHE_SIZE = 16


def _get_cookie_name(is_secure: bool) -> str:
    """Return the cookie name."""
    return PREFIXED_COOKIE_NAME if is_secure else COOKIE_NAME


class HomeAssistantCookieStorage(EncryptedCookieStorage):
    """Home Assistant cookie storage.

    Own class is required:
        - to set the secure flag based on the connection type
        - to use a LRU cache for session decryption
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the cookie storage."""
        super().__init__(
            hass.auth.session.key,
            cookie_name=PREFIXED_COOKIE_NAME,
            max_age=int(REFRESH_TOKEN_EXPIRATION),
            httponly=True,
            samesite="Lax",
            secure=True,
            encoder=json_dumps,
            decoder=json_loads,
        )
        self._hass = hass

    def _secure_connection(self, request: Request) -> bool:
        """Return if the connection is secure (https)."""
        return is_cloud_connection(self._hass) or request.secure

    def load_cookie(self, request: Request) -> str | None:
        """Load cookie."""
        is_secure = self._secure_connection(request)
        cookie_name = _get_cookie_name(is_secure)
        return request.cookies.get(cookie_name)

    @lru_cache(maxsize=SESSION_CACHE_SIZE)
    def _decrypt_cookie(self, cookie: str) -> Session | None:
        """Decrypt and validate cookie."""
        try:
            data = SessionData(  # type: ignore[misc]
                self._decoder(
                    self._fernet.decrypt(
                        cookie.encode("utf-8"), ttl=self.max_age
                    ).decode("utf-8")
                )
            )
        except (InvalidToken, TypeError, ValueError, *JSON_DECODE_EXCEPTIONS):
            _LOGGER.warning("Cannot decrypt/parse cookie value")
            return None

        session = Session(None, data=data, new=data is None, max_age=self.max_age)

        # Validate session if not empty
        if (
            not session.empty
            and not self._hass.auth.session.async_validate_strict_connection_session(
                session
            )
        ):
            # Invalidate session as it is not valid
            session.invalidate()

        return session

    async def new_session(self) -> Session:
        """Create a new session and mark it as changed."""
        session = Session(None, data=None, new=True, max_age=self.max_age)
        session.changed()
        return session

    async def load_session(self, request: Request) -> Session:
        """Load session."""
        # Split parent function to use lru_cache
        if (cookie := self.load_cookie(request)) is None:
            return await self.new_session()

        if (session := self._decrypt_cookie(cookie)) is None:
            # Decrypting/parsing failed, log wrong login and create a new session
            await process_wrong_login(request)
            session = await self.new_session()

        return session

    async def save_session(
        self, request: Request, response: StreamResponse, session: Session
    ) -> None:
        """Save session."""

        is_secure = self._secure_connection(request)
        cookie_name = _get_cookie_name(is_secure)

        if session.empty:
            response.del_cookie(cookie_name)
        else:
            params = self.cookie_params.copy()
            params["secure"] = is_secure
            params["max_age"] = session.max_age

            cookie_data = self._encoder(self._get_session_data(session)).encode("utf-8")
            response.set_cookie(
                cookie_name,
                self._fernet.encrypt(cookie_data).decode("utf-8"),
                **params,
            )
            # Add Cache-Control header to not cache the cookie as it
            # is used for session management
            self._add_cache_control_header(response)

    @staticmethod
    def _add_cache_control_header(response: StreamResponse) -> None:
        """Add/set cache control header to no-cache="Set-Cookie"."""
        # Structure of the Cache-Control header defined in
        # https://datatracker.ietf.org/doc/html/rfc2068#section-14.9
        if header := response.headers.get("Cache-Control"):
            directives = []
            for directive in header.split(","):
                directive = directive.strip()
                directive_lowered = directive.lower()
                if directive_lowered.startswith("no-cache"):
                    if "set-cookie" in directive_lowered or directive.find("=") == -1:
                        # Set-Cookie is already in the no-cache directive or
                        # the whole request should not be cached -> Nothing to do
                        return

                    # Add Set-Cookie to the no-cache
                    # [:-1] to remove the " at the end of the directive
                    directive = f"{directive[:-1]}, Set-Cookie"

                directives.append(directive)
            header = ", ".join(directives)
        else:
            header = 'no-cache="Set-Cookie"'
        response.headers["Cache-Control"] = header
