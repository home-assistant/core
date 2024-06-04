"""HTTP specific constants."""

from typing import Final

from homeassistant.helpers.http import KEY_AUTHENTICATED, KEY_HASS  # noqa: F401

DOMAIN: Final = "http"

KEY_HASS_USER: Final = "hass_user"
KEY_HASS_REFRESH_TOKEN_ID: Final = "hass_refresh_token_id"
