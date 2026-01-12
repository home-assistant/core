"""Test stubs for rotarex_dimes_srg_api dependency."""

from datetime import datetime, timedelta
import hashlib
import sys
import types
from typing import Any

mod = types.ModuleType("rotarex_dimes_srg_api")


class InvalidAuth(Exception):
    """Auth error placeholder for tests."""


class RotarexApi:
    """Stub for Rotarex API used by config_flow imports."""

    def __init__(self, session: Any) -> None:
        """Initialize the RotarexApi stub with a session.

        Args:
            session (Any): The session object to be used for API interactions.
        """
        self._session = session
        self.access_token: str | None = None
        self.expires_at: datetime | None = None
        self._email: str | None = None
        self._password: str | None = None

    def set_credentials(self, email: str, password: str) -> None:
        """Store credentials for re-authentication."""
        self._email = email
        self._password = password

    async def login(self, email: str, password: str) -> None:
        """Simulate user login."""
        if email != "test@example.com" or password != "test_password":
            raise InvalidAuth("Invalid email or password")
        self.access_token = "test_access_token"
        self.expires_at = datetime.now(datetime.UTC) + timedelta(hours=1)

    @staticmethod
    def hash_message(message: str) -> str:
        """Hashes a message using SHA-256."""

        return hashlib.sha256(message.encode("utf-8")).hexdigest()

    def token_expired(self) -> bool:
        """Check if the token is expired."""
        if not self.expires_at:
            return True
        return datetime.now(datetime.UTC) >= self.expires_at

    async def fetch_tanks(self) -> list[dict[str, Any]]:
        """Simulate fetching tanks from the Rotarex API."""
        if not self.access_token or self.token_expired():
            if self._email and self._password:
                await self.login(self._email, self._password)
            else:
                raise InvalidAuth(
                    "Missing or expired token and no credentials to re-login."
                )

        return [{"id": "tank1", "name": "Tank 1"}, {"id": "tank2", "name": "Tank 2"}]


mod.InvalidAuth = InvalidAuth
mod.RotarexApi = RotarexApi

# Inject stub into sys.modules so imports succeed during tests
sys.modules["rotarex_dimes_srg_api"] = mod
