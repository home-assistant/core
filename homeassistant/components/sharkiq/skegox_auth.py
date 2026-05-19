# Auth0 authentication manager for the Skegox API.
# Handles Auth0 password grant and refresh_token grant — no browser required.
# Tokens are persisted via the Home Assistant config entry data.

from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_AUTH0_ACCESS_TOKEN,
    CONF_AUTH0_EXPIRY,
    CONF_AUTH0_ID_TOKEN,
    CONF_AUTH0_REFRESH_TOKEN,
    CONF_AYLA_ACCESS_TOKEN,
    CONF_AYLA_REFRESH_TOKEN,
    CONF_AYLA_TOKEN_EXPIRY,
    CONF_HOUSEHOLD_ID,
    CONF_USER_ID,
    SHARKIQ_REGION_EUROPE,
    SHARKIQ_REGION_ELSEWHERE,
)

# Region-specific Auth0 and Skegox configuration
# Sources: shark2mqtt const.py (verified working as of 2026-04) MIT License
# https://github.com/CamSoper/shark2mqtt

# Region-specific API endpoints and credentials.
@dataclass(frozen=True)
class RegionConfig:
    auth0_url: str
    auth0_token_url: str
    auth0_client_id: str
    ayla_login_url: str
    ayla_device_url: str
    ayla_app_id: str
    ayla_app_secret: str
    skegox_base: str
    skegox_api_key: str


REGION_CONFIGS: dict[str, RegionConfig] = {
    SHARKIQ_REGION_ELSEWHERE: RegionConfig(
        auth0_url="https://login.sharkninja.com",
        auth0_token_url="https://login.sharkninja.com/oauth/token",
        auth0_client_id="wsguxrqm77mq4LtrTrwg8ZJUxmSrexGi",
        ayla_login_url="https://user-sharkue1.aylanetworks.com",
        ayla_device_url="https://ads-sharkue1.aylanetworks.com",
        ayla_app_id="ios_shark_prod-3A-id",
        ayla_app_secret="ios_shark_prod-74tFWGNg34LQCmR0m45SsThqrqs",
        skegox_base="https://stakra.slatra.thor.skegox.com",
        skegox_api_key="QQdbSrgicK2PxvACI1a2P5AN2xgO78Lw1VvnYczb",
    ),
    SHARKIQ_REGION_EUROPE: RegionConfig(
        auth0_url="https://logineu.sharkninja.com",
        auth0_token_url="https://logineu.sharkninja.com/oauth/token",
        auth0_client_id="rKDx9O18dBrY3eoJMTkRiBZHDvd9Mx1I",
        ayla_login_url="https://user-field-eu.aylanetworks.com",
        ayla_device_url="https://ads-eu.aylanetworks.com",
        ayla_app_id="android_shark_prod-lg-id",
        ayla_app_secret="android_shark_prod-xuf9mlHOo0p3Ty5bboFROSyRBlE",
        skegox_base="https://stakra.rannsaka.thor.skegox.com",
        skegox_api_key="T5m8d45crZDV9I5aCEZr4n2gSqJW64r2RNXqqhh1",
    ),
}

AUTH0_SCOPES = "openid email profile offline_access"

# Refresh Ayla tokens 5 minutes before expiry
AYLA_REFRESH_BUFFER = timedelta(minutes=5)

_LOGGER = logging.getLogger(__name__)

# 
class SkegoxAuthError(Exception):
    """Authentication failure with the Skegox/Auth0 API."""

# 
class SkegoxAuthRequiresVerificationError(SkegoxAuthError):
    """Auth0 requires additional verification (MFA, CAPTCHA, etc.)."""

# 
class SkegoxAuthLockedError(SkegoxAuthError):
    """Account locked or rate-limited — do not retry."""

# Holds all authentication tokens for a session.
@dataclass
class AuthTokens:
    auth0_id_token: str | None = None
    auth0_refresh_token: str | None = None
    auth0_access_token: str | None = None
    auth0_expiry: datetime | None = None
    ayla_access_token: str | None = None
    ayla_refresh_token: str | None = None
    ayla_expiry: datetime | None = None
    household_id: str | None = None
    user_id: str | None = None

    # Serialize tokens to a dict for Home Assistant config entry storage.
    def to_dict(self) -> dict[str, Any]:
        return {
            CONF_AUTH0_ID_TOKEN: self.auth0_id_token,
            CONF_AUTH0_REFRESH_TOKEN: self.auth0_refresh_token,
            CONF_AUTH0_ACCESS_TOKEN: self.auth0_access_token,
            CONF_AUTH0_EXPIRY: self.auth0_expiry.isoformat() if self.auth0_expiry else None,
            CONF_AYLA_ACCESS_TOKEN: self.ayla_access_token,
            CONF_AYLA_REFRESH_TOKEN: self.ayla_refresh_token,
            CONF_AYLA_TOKEN_EXPIRY: self.ayla_expiry.isoformat() if self.ayla_expiry else None,
            CONF_HOUSEHOLD_ID: self.household_id,
            CONF_USER_ID: self.user_id,
        }

    # Deserialize tokens from Home Assistant config entry data.
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AuthTokens:
        tokens = cls()
        tokens.auth0_id_token = data.get(CONF_AUTH0_ID_TOKEN)
        tokens.auth0_refresh_token = data.get(CONF_AUTH0_REFRESH_TOKEN)
        tokens.auth0_access_token = data.get(CONF_AUTH0_ACCESS_TOKEN)
        if expiry_str := data.get(CONF_AUTH0_EXPIRY):
            try:
                tokens.auth0_expiry = datetime.fromisoformat(expiry_str)
            except (ValueError, TypeError):
                pass
        tokens.ayla_access_token = data.get(CONF_AYLA_ACCESS_TOKEN)
        tokens.ayla_refresh_token = data.get(CONF_AYLA_REFRESH_TOKEN)
        if expiry_str := data.get(CONF_AYLA_TOKEN_EXPIRY):
            try:
                tokens.ayla_expiry = datetime.fromisoformat(expiry_str)
            except (ValueError, TypeError):
                pass
        tokens.household_id = data.get(CONF_HOUSEHOLD_ID)
        tokens.user_id = data.get(CONF_USER_ID)
        return tokens

    # Check if the Auth0 id_token is still valid.
    @property
    def auth0_token_valid(self) -> bool:
        if not self.auth0_id_token or not self.auth0_expiry:
            return False
        return datetime.now(timezone.utc) < self.auth0_expiry

    # Check if the Ayla access token is expiring soon.
    @property
    def ayla_token_expiring_soon(self) -> bool:
        if not self.ayla_access_token or not self.ayla_expiry:
            return True
        return datetime.now(timezone.utc) >= self.ayla_expiry - AYLA_REFRESH_BUFFER

# Manages Auth0 authentication lifecycle for the Skegox API.
# Auth cascade (no browser):
#   1. Load cached tokens from config entry
#   2. If id_token is valid, use it
#   3. Try Auth0 refresh_token grant
#   4. Try Auth0 password grant
#   5. Raise SkegoxAuthError (triggers reauth flow in HA)
class SkegoxAuthManager:
    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry | None, username: str, password: str, region: str = SHARKIQ_REGION_ELSEWHERE,) -> None:
        # Manage Auth0 authentication lifecycle for the Skegox API.
        # Auth cascade: load cached tokens → use valid id_token → refresh_token
        # grant → password grant → raise SkegoxAuthError (triggers HA reauth flow).
        # `config_entry` may be None during initial validation before the entry
        # is created; in that case tokens are not persisted.
        self._hass = hass
        self._config_entry = config_entry
        self._username = username
        self._password = password
        self._region_config = REGION_CONFIGS[region]
        self._tokens = AuthTokens.from_dict(config_entry.data) if config_entry else AuthTokens()
        self._session: aiohttp.ClientSession | None = None

    @property
    def region(self) -> RegionConfig:
        return self._region_config

    @property
    def id_token(self) -> str | None:
        return self._tokens.auth0_id_token

    @property
    def ayla_access_token(self) -> str | None:
        return self._tokens.ayla_access_token

    @property
    def ayla_refresh_token(self) -> str | None:
        return self._tokens.ayla_refresh_token

    @property
    def household_id(self) -> str | None:
        return self._tokens.household_id

    @property
    def user_id(self) -> str | None:
        return self._tokens.user_id

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    # Persist tokens to the config entry data.
    def _save_tokens(self) -> None:
        if self._config_entry is None:
            return
        token_data = self._tokens.to_dict()
        new_data = {**self._config_entry.data, **token_data}
        self._hass.config_entries.async_update_entry(
            self._config_entry, data=new_data
        )

    # Return a valid Auth0 id_token, refreshing if needed.
    # Raise SkegoxAuthError if all authentication methods fail.
    async def ensure_authenticated(self, force_refresh: bool = False) -> str:
        # If we have a valid id_token and not forcing refresh, use it
        if not force_refresh and self._tokens.auth0_token_valid:
            _LOGGER.debug("Using cached Auth0 id_token")
            assert self._tokens.auth0_id_token is not None
            return self._tokens.auth0_id_token

        # Try refresh_token grant
        if self._tokens.auth0_refresh_token:
            try:
                await self._refresh_auth0_token()
                _LOGGER.debug("Auth0 token refreshed via refresh_token grant")
                assert self._tokens.auth0_id_token is not None
                return self._tokens.auth0_id_token
            except SkegoxAuthError:
                _LOGGER.warning("Auth0 refresh_token grant failed")

        # Try password grant
        try:
            await self._password_grant_sign_in()
            _LOGGER.debug("Auth0 password grant successful")
            assert self._tokens.auth0_id_token is not None
            return self._tokens.auth0_id_token
        except SkegoxAuthRequiresVerificationError:
            raise
        except SkegoxAuthError:
            _LOGGER.warning("Auth0 password grant failed")

        raise SkegoxAuthError("All authentication methods failed. Please re-authenticate via the Home Assistant integration.")

    # Authenticate via Auth0 password grant (no browser).
    # POST {auth0_token_url} with grant_type=password.
    async def _password_grant_sign_in(self) -> None:
        payload = {
            "grant_type": "password",
            "client_id": self._region_config.auth0_client_id,
            "username": self._username,
            "password": self._password,
            "scope": AUTH0_SCOPES,
        }

        session = await self._get_session()
        async with session.post(
            self._region_config.auth0_token_url,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            data = await resp.json()

            if resp.status == 401:
                error = data.get("error", "unknown")
                desc = data.get("error_description", "")
                if error == "requires_verification":
                    raise SkegoxAuthRequiresVerificationError(f"Auth0 requires additional verification: {desc}. Try completing login in the SharkClean app, then retry.")
                raise SkegoxAuthError(f"Auth0 password grant failed (401): {desc}")

            if resp.status >= 400:
                error = data.get("error", "unknown")
                desc = data.get("error_description", "")
                if resp.status == 429:
                    raise SkegoxAuthLockedError(f"Auth0 rate limited: {error} {desc}")
                raise SkegoxAuthError(f"Auth0 password grant failed ({resp.status}): {error} {desc}")

            if "id_token" not in data:
                raise SkegoxAuthError("Auth0 response missing id_token. The password grant may not be enabled for this account.")

            self._tokens.auth0_id_token = data["id_token"]
            self._tokens.auth0_access_token = data.get("access_token")
            self._tokens.auth0_refresh_token = data.get("refresh_token")
            # Estimate expiry from id_token exp claim (typically 24h for password grant)
            self._tokens.auth0_expiry = self._decode_jwt_expiry(data["id_token"])
            self._save_tokens()

    # Exchange Auth0 refresh_token for a new id_token.
    # POST {auth0_token_url} with grant_type=refresh_token.
    async def _refresh_auth0_token(self) -> None:
        if not self._tokens.auth0_refresh_token:
            raise SkegoxAuthError("No Auth0 refresh token available")

        payload = {
            "grant_type": "refresh_token",
            "client_id": self._region_config.auth0_client_id,
            "refresh_token": self._tokens.auth0_refresh_token,
        }

        session = await self._get_session()
        async with session.post(self._region_config.auth0_token_url, json=payload, timeout=aiohttp.ClientTimeout(total=15),) as resp:
            data = await resp.json()

            if resp.status != 200:
                error = data.get("error", "unknown")
                desc = data.get("error_description", "")
                if resp.status == 429:
                    raise SkegoxAuthLockedError(f"Auth0 rate limited: {error} {desc}")
                raise SkegoxAuthError(f"Auth0 refresh failed ({resp.status}): {error} {desc}")

            self._tokens.auth0_id_token = data["id_token"]
            self._tokens.auth0_access_token = data.get("access_token")
            # Auth0 may rotate the refresh token
            if "refresh_token" in data:
                self._tokens.auth0_refresh_token = data["refresh_token"]
            self._tokens.auth0_expiry = self._decode_jwt_expiry(data["id_token"])
            self._save_tokens()

    # Called after Ayla token_sign_in to persist Ayla tokens.
    def update_ayla_tokens(self, access_token: str, refresh_token: str, expiry: datetime,) -> None:
        self._tokens.ayla_access_token = access_token
        self._tokens.ayla_refresh_token = refresh_token
        self._tokens.ayla_expiry = expiry
        self._save_tokens()

    # Set the discovered household ID.
    def set_household_id(self, household_id: str) -> None:
        self._tokens.household_id = household_id
        self._save_tokens()

    # Set the discovered user ID.
    def set_user_id(self, user_id: str) -> None:
        self._tokens.user_id = user_id
        self._save_tokens()

    #Extract the exp claim from a JWT and return as datetime.
    @staticmethod
    def _decode_jwt_expiry(token: str) -> datetime:
        try:
            parts = token.split(".")
            payload = parts[1] + "=" * (4 - len(parts[1]) % 4)
            claims = json.loads(base64.urlsafe_b64decode(payload))
            exp = claims.get("exp")
            if exp:
                return datetime.fromtimestamp(exp, tz=timezone.utc)
        except Exception:
            _LOGGER.debug("Failed to decode JWT expiry", exc_info=True)
        # Fallback: assume 24 hours from now (typical for password grant)
        # when the JWT cannot be decoded or lacks an exp claim.
        return datetime.now(timezone.utc) + timedelta(hours=24)
