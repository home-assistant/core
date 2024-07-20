"""Handle Yale connection setup and authentication."""

from typing import Any

from yalexs.manager.gateway import Gateway

from homeassistant.const import CONF_USERNAME

from .const import (
    CONF_ACCESS_TOKEN_CACHE_FILE,
    CONF_BRAND,
    CONF_INSTALL_ID,
    CONF_LOGIN_METHOD,
    DEFAULT_BRAND,
)


class YaleGateway(Gateway):
    """Handle the connection to Yale."""

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
