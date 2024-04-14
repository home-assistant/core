"""HTTP specific constants."""

from enum import StrEnum
from typing import Final

from homeassistant.helpers.http import KEY_AUTHENTICATED, KEY_HASS  # noqa: F401

KEY_HASS_USER: Final = "hass_user"
KEY_HASS_REFRESH_TOKEN_ID: Final = "hass_refresh_token_id"


class StrictConnectionMode(StrEnum):
    """Enum for strict connection mode."""

    DISABLED = "disabled"
    STATIC_PAGE = "static_page"
    DROP_CONNECTION = "drop_connection"
