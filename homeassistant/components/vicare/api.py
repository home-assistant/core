"""API for Viessmann ViCare bound to Home Assistant OAuth."""

from asyncio import run_coroutine_threadsafe
import logging
from typing import Any

from PyViCare.PyViCareAbstractOAuthManager import AbstractViCareOAuthManager
import requests

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

_LOGGER = logging.getLogger(__name__)
_DEFAULT_TIMEOUT = 31


class _TimeoutSession(requests.Session):
    """requests.Session that applies a default timeout when callers omit one."""

    def request(  # type: ignore[override]
        self, method: str, url: str, **kwargs: Any
    ) -> requests.Response:
        """Forward to Session.request with a default timeout."""
        kwargs.setdefault("timeout", _DEFAULT_TIMEOUT)
        return super().request(method, url, **kwargs)


class ConfigEntryAuth(AbstractViCareOAuthManager):
    """Provide Viessmann ViCare authentication tied to an OAuth2 based config entry."""

    def __init__(
        self,
        hass: HomeAssistant,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Initialize Viessmann ViCare Auth."""
        self._hass = hass
        self._ha_session = oauth_session
        # Header mutation in renewToken() races with concurrent reads from
        # PyViCare's executor calls; self-healing via PyViCare's EXPIRED TOKEN
        # retry, so no lock.
        session = _TimeoutSession()
        session.headers["Authorization"] = self._bearer_header()
        super().__init__(session)

    def renewToken(self) -> None:
        """Refresh OAuth2 token via HA and update the bearer header."""
        _LOGGER.debug("Renewing OAuth2 token")
        run_coroutine_threadsafe(
            self._ha_session.async_ensure_token_valid(), self._hass.loop
        ).result()
        self.oauth_session.headers["Authorization"] = self._bearer_header()
        _LOGGER.debug("OAuth2 token renewed successfully")

    def _bearer_header(self) -> str:
        token: dict[str, Any] = self._ha_session.token
        return f"Bearer {token['access_token']}"
