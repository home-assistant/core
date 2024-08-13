"""Handle Yale connection setup and authentication."""

from pathlib import Path
from typing import Any

from aiohttp import ClientSession
from yalexs.manager.gateway import Gateway

from homeassistant.const import CONF_USERNAME
from homeassistant.helpers import config_entry_oauth2_flow

from .const import (
    CONF_ACCESS_TOKEN_CACHE_FILE,
    CONF_BRAND,
    CONF_INSTALL_ID,
    CONF_LOGIN_METHOD,
    DEFAULT_BRAND,
)


class YaleGateway(Gateway):
    """Handle the connection to Yale."""

    def __init__(
        self,
        config_path: Path,
        aiohttp_session: ClientSession,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Init the connection."""
        super().__init__(config_path, aiohttp_session)
        self._oauth_session = oauth_session

    async def async_get_access_token(self) -> str:
        """Get access token."""
        if not self._oauth_session.valid_token:
            await self._oauth_session.async_ensure_token_valid()
        return self._oauth_session.token["access_token"]

    def config_entry(self) -> dict[str, Any]:
        """Config entry."""
        assert self._config is not None
        return {
            CONF_BRAND: self._config.get(CONF_BRAND, DEFAULT_BRAND),
            CONF_LOGIN_METHOD: self._config[CONF_LOGIN_METHOD],
            CONF_USERNAME: self._config[CONF_USERNAME],
            CONF_INSTALL_ID: self._config.get(CONF_INSTALL_ID),
            CONF_ACCESS_TOKEN_CACHE_FILE: self._access_token_cache_file,
        }
