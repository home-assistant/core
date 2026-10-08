"""Netatmo web session authentication for siren control."""

import logging
from collections.abc import Mapping
from urllib.parse import unquote

import aiohttp

from .const import NETATMO_LOGIN_URL, NETATMO_SETSTATE_URL

_LOGGER = logging.getLogger(__name__)

NETATMO_LOGIN_PAGE_URL = "https://auth.netatmo.com/en-us/access/login"


def _extract_token_from_headers(headers: Mapping[str, str]) -> str | None:
    """Extract netatmocomaccess_token from Set-Cookie response headers."""
    for header_name, header_value in headers.items():
        if header_name.lower() != "set-cookie":
            continue
        if "netatmocomaccess_token=" not in header_value:
            continue
        for part in header_value.split(";"):
            part = part.strip()
            if part.startswith("netatmocomaccess_token="):
                return unquote(part.split("=", 1)[1])
    return None


class NetatmoWebSessionAuth:
    """Manage a Netatmo web session token for siren control."""

    def __init__(
        self,
        websession: aiohttp.ClientSession,
        token: str | None = None,
        email: str | None = None,
        password: str | None = None,
    ) -> None:
        """Initialize the web session auth."""
        self._websession = websession
        self._token = token
        self._email = email
        self._password = password

    @property
    def token(self) -> str | None:
        """Return the current session token."""
        return self._token

    @classmethod
    async def async_login(
        cls,
        websession: aiohttp.ClientSession,
        email: str,
        password: str,
    ) -> NetatmoWebSessionAuth:
        """Login and return a NetatmoWebSessionAuth instance with the session token."""

        # Step 1: GET the login page to obtain CSRF cookie
        login_page_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        async with websession.get(
            NETATMO_LOGIN_PAGE_URL,
            headers=login_page_headers,
            allow_redirects=True,
        ) as resp:
            _LOGGER.debug("Netatmo login page: %s", resp.status)

        # Step 2: POST login with credentials + CSRF token from cookie jar
        xsrf_token = None
        for cookie in websession.cookie_jar:
            if cookie.key == "XSRF-TOKEN":
                xsrf_token = unquote(cookie.value)
                break

        data = {
            "email": email,
            "password": password,
            "stay_logged": "on",
            "website": "",
        }

        post_headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": NETATMO_LOGIN_PAGE_URL,
            "Origin": "https://auth.netatmo.com",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "X-XSRF-TOKEN": xsrf_token or "",
        }

        async with websession.post(
            NETATMO_LOGIN_URL,
            data=data,
            headers=post_headers,
            allow_redirects=True,
        ) as resp:
            # Extract access token from cookie jar
            token = None
            for cookie in websession.cookie_jar:
                if cookie.key == "netatmocomaccess_token":
                    token = unquote(cookie.value)
                    break

            # Also check Set-Cookie headers as fallback
            if not token:
                token = _extract_token_from_headers(resp.headers)

            if not token:
                _LOGGER.error(
                    "Netatmo login failed - no access token. Status: %s", resp.status
                )
                raise aiohttp.ClientError("Login failed - no access token received")

            _LOGGER.debug("Netatmo web session token obtained successfully")
            return cls(websession, token=token, email=email, password=password)

    async def _async_relogin(self) -> bool:
        """Re-login to get a fresh token. Returns True if successful."""
        if not self._email or not self._password:
            _LOGGER.error("Cannot re-login: no credentials stored")
            return False

        _LOGGER.debug("Netatmo siren token expired, re-logging in")
        try:
            async with aiohttp.ClientSession(
                cookie_jar=aiohttp.CookieJar()
            ) as login_session:
                fresh = await NetatmoWebSessionAuth.async_login(
                    login_session, self._email, self._password
                )
            self._token = fresh.token
            _LOGGER.debug("Netatmo siren re-login successful")
        except aiohttp.ClientError as err:
            _LOGGER.error("Netatmo siren re-login failed: %s", err)
            return False
        else:
            return True

    async def async_set_siren_state(
        self,
        home_id: str,
        module_id: str,
        state: str,
    ) -> bool:
        """Set siren state using web session token, with automatic re-login on expiry."""
        if not self._token:
            if not await self._async_relogin():
                return False

        payload: dict[str, Any] = {
            "home": {
                "id": home_id,
                "modules": [
                    {
                        "id": module_id,
                        "siren_status": state,
                    }
                ],
            }
        }

        async with self._websession.post(
            NETATMO_SETSTATE_URL,
            json=payload,
            headers={"Authorization": f"Bearer {self._token}"},
        ) as resp:
            data = await resp.json()
            if data.get("status") == "ok":
                return True

            error = data.get("error", {})
            _LOGGER.debug("Siren setstate response: %s", error)

            # Token expired ΓÇö re-login once and retry
            if error.get("code") in (2, 3, 13):
                self._token = None
                if await self._async_relogin():
                    # Retry with new token
                    async with self._websession.post(
                        NETATMO_SETSTATE_URL,
                        json=payload,
                        headers={"Authorization": f"Bearer {self._token}"},
                    ) as retry_resp:
                        retry_data = await retry_resp.json()
                        if retry_data.get("status") == "ok":
                            return True
                        _LOGGER.error(
                            "Siren setstate failed after re-login: %s",
                            retry_data.get("error", retry_data),
                        )
                        return False

            _LOGGER.error("Siren setstate failed: %s", error)
            return False

    async def async_siren_on(self, home_id: str, module_id: str) -> bool:
        """Trigger siren."""
        return await self.async_set_siren_state(home_id, module_id, "sound")

    async def async_siren_off(self, home_id: str, module_id: str) -> bool:
        """Stop siren."""
        return await self.async_set_siren_state(home_id, module_id, "no_sound")
