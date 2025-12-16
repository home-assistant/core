from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

import aiohttp


class InvalidAuth(Exception):
    """Invalid authentication."""


class RotarexApi:
    def __init__(self, session: aiohttp.ClientSession) -> None:
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
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }

        hashed_password = self.hash_message(password)

        payload = {
            'grant_type': "password",
            "username": email,
            "password": hashed_password,
        }

        async with self._session.post(
            "https://wavedev.rotarex.com/token",
            data=payload,
            headers=headers,
            timeout=15,
        ) as resp:
            if resp.status != 200:
                body = await resp.text()
                raise InvalidAuth(f"Login failed with status {resp.status}: {body}")

            token_data = await resp.json()

        self.access_token = token_data["access_token"]
        self.expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=int(token_data["expires_in"])
        )

    @staticmethod
    def hash_message(message: str) -> str:
        """Hashes a message using SHA-256."""
        bytes_message = message.encode('utf-8')
        digest = hashlib.sha256(bytes_message).hexdigest()

        return digest

    def token_expired(self) -> bool:
        if not self.expires_at:
            return True
        return datetime.now(timezone.utc) >= self.expires_at

    async def fetch_tanks(self) -> list[dict[str, Any]]:
        """Fetches a list of tanks and their details."""
        if not self.access_token or self.token_expired():
            if self._email and self._password:
                await self.login(self._email, self._password)
            else:
                raise InvalidAuth("Missing or expired token and no credentials to re-login.")

        headers = {
            "Authorization": f"Bearer {self.access_token}",
        }

        async with self._session.get(
            "https://wavedev.rotarex.com/api/Tanks",
            headers=headers,
            timeout=15,
        ) as resp:
            if resp.status == 401:
                # Token might have just expired, try one re-login
                if self._email and self._password:
                    await self.login(self._email, self._password)
                    headers["Authorization"] = f"Bearer {self.access_token}"
                    async with self._session.get(
                        "https://wavedev.rotarex.com/api/Tanks", headers=headers, timeout=15
                    ) as retry_resp:
                        retry_resp.raise_for_status()
                        return await retry_resp.json()
                else:
                    raise InvalidAuth("Token expired or invalid")

            resp.raise_for_status()
            return await resp.json()
