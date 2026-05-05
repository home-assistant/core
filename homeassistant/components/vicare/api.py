"""API for Viessmann ViCare bound to Home Assistant OAuth."""

from __future__ import annotations

from asyncio import run_coroutine_threadsafe
import logging
from typing import Any

from PyViCare.PyViCareAbstractOAuthManager import AbstractViCareOAuthManager
import requests

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

_LOGGER = logging.getLogger(__name__)


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
        session = requests.Session()
        session.headers["Authorization"] = self._bearer_header()
        super().__init__(session)  # type: ignore[arg-type]

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
