"""Home Assistant adapter for the Beatbot cloud API client."""

import logging
from typing import Any

from beatbot_cloud import (
    BeatbotAuthenticationError,
    BeatbotClient,
    BeatbotConnectionError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

BeatbotAuthError = BeatbotAuthenticationError
__all__ = ["BeatbotAuthError", "BeatbotConnectionError"]
_LOGGER = logging.getLogger(__name__)


class BeatbotAPI(BeatbotClient):
    """Beatbot client backed by Home Assistant's OAuth2 session."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Initialize the region-aware client."""
        self._hass = hass
        self._entry = entry
        self._session = session
        if not isinstance(region := entry.data.get("region"), str):
            raise TypeError("Beatbot config entry has no region")
        super().__init__(region, self._async_request)

    async def _async_request(self, method: str, url: str, **kwargs: Any):
        """Forward a request through Home Assistant's refreshing OAuth session."""
        return await self._session.async_request(method, url, **kwargs)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json_body: Any | None = None,
    ) -> Any:
        """Log OAuth reauthentication failures with config-entry context."""
        try:
            return await super()._request(
                method, path, params=params, json_body=json_body
            )
        except BeatbotAuthenticationError:
            _LOGGER.warning(
                "Beatbot OAuth token refresh rejected (entry_id=%s); "
                "user reauthentication is required",
                self._entry.entry_id,
            )
            raise
