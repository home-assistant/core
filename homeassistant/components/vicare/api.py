"""API for Viessmann ViCare bound to Home Assistant OAuth."""

from __future__ import annotations

from asyncio import run_coroutine_threadsafe
import logging
from typing import Any

from PyViCare.PyViCareAbstractOAuthManager import AbstractViCareOAuthManager

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

_LOGGER = logging.getLogger(__name__)


class _SyncResponse:
    """Wrap an aiohttp ClientResponse to provide a sync .json() method.

    PyViCare's AbstractViCareOAuthManager expects requests-style Response
    objects with a synchronous .json() method. This wraps aiohttp's async
    response to satisfy that interface.
    """

    def __init__(self, hass: HomeAssistant, response: Any) -> None:
        """Initialize sync response wrapper."""
        self._hass = hass
        self._response = response

    def json(self) -> dict:
        """Return JSON body synchronously."""
        return run_coroutine_threadsafe(self._response.json(), self._hass.loop).result()


class _SyncSessionAdapter:
    """Adapt HA's async OAuth2Session to the sync interface PyViCare expects.

    AbstractViCareOAuthManager expects an authlib-style OAuth2Session with
    synchronous .get() and .post() methods returning objects with .json().
    This adapter bridges HA's async OAuth2Session to that interface so the
    parent class's get()/post() and all error handling work unmodified.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Initialize sync session adapter."""
        self._hass = hass
        self._session = session

    def get(self, url: str, **kwargs: Any) -> _SyncResponse:
        """Perform sync GET via HA's async OAuth2Session."""
        timeout = kwargs.pop("timeout", 31)
        response = run_coroutine_threadsafe(
            self._session.async_request("GET", url),
            self._hass.loop,
        ).result(timeout=timeout)
        return _SyncResponse(self._hass, response)

    def post(self, url: str, data: Any = None, **kwargs: Any) -> _SyncResponse:
        """Perform sync POST via HA's async OAuth2Session."""
        headers = kwargs.pop("headers", {})
        response = run_coroutine_threadsafe(
            self._session.async_request("POST", url, data=data, headers=headers),
            self._hass.loop,
        ).result(timeout=31)
        return _SyncResponse(self._hass, response)


class ConfigEntryAuth(AbstractViCareOAuthManager):
    """Provide Viessmann ViCare authentication tied to an OAuth2 based config entry.

    Uses an adapter to bridge HA's async OAuth2Session to the sync interface
    expected by PyViCare's AbstractViCareOAuthManager. The parent's get()/post()
    methods with all error handling (rate limit, expired token, server error,
    command error) work without overriding.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Initialize Viessmann ViCare Auth."""
        self._hass = hass
        self._ha_session = oauth_session
        adapter = _SyncSessionAdapter(hass, oauth_session)
        super().__init__(adapter)

    def renewToken(self) -> None:
        """Refresh tokens using Home Assistant's OAuth2 session."""
        run_coroutine_threadsafe(
            self._ha_session.async_ensure_token_valid(), self._hass.loop
        ).result()
