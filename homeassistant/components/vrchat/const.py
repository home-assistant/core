"""Constants for the VRChat integration."""

from enum import StrEnum
from typing import Final

from homeassistant.const import __version__

from .utils import svg_file_uri

DOMAIN = "vrchat"

RETRY_DELAY_SECOND: Final = 60
WEBSOCKET_INACTIVE_TIMEOUT_SECOND: Final = 600

CONF_2FA_CODE: Final = "2fa_code"
CONF_EMAIL_2FA_CODE: Final = "email_2fa_code"
CONF_COOKIE_AUTH: Final = "auth"
CONF_COOKIE_2FA: Final = "twoFactorAuth"

USER_AGENT: Final = (
    f"HomeAssistant/{__version__} https://github.com/home-assistant/core"
)

VRCHAT_API_HOST: Final = "api.vrchat.cloud"
VRCHAT_USER_PAGE_BASE_URL: Final = "https://vrchat.com/home/user/"
VRCHAT_WEBSOCKET_URL: Final = "wss://pipeline.vrchat.cloud"


class VRChatWebsocketEventType(StrEnum):
    """VRChat websocket event type enum."""

    FRIEND_DELETE = "friend-delete"
    FRIEND_OFFLINE = "friend-offline"
    FRIEND_ACTIVE = "friend-active"

    USER_UPDATE = "user-update"


class VRChatUserState(StrEnum):
    """VRChat user state enum."""

    JOIN_ME = "join_me"
    ACTIVE = "active"
    ASK_ME = "ask_me"
    BUSY = "busy"
    OFFLINE = "offline"
    # ACTIVE_ON_WEB = "active on web"
    # ACTIVE_ON_MOBILE = "active on mobile"
    ACTIVE_ON_WEB_OR_MOBILE = "active_on_web_or_mobile"


VRCHAT_USER_STATUS_ICON_MAP = {
    VRChatUserState.JOIN_ME: "mdi:account-arrow-left",
    VRChatUserState.ACTIVE: "mdi:account-badge",
    VRChatUserState.ASK_ME: "mdi:account-card",
    VRChatUserState.BUSY: "mdi:account-cancel",
    VRChatUserState.OFFLINE: "mdi:account-outline",
}

VRCHAT_USER_STATUS_OPTIONS: list[str] = [
    status.value for status in VRCHAT_USER_STATUS_ICON_MAP
]

VRCHAT_USER_STATE_OPTIONS: list[str] = [
    *VRCHAT_USER_STATUS_OPTIONS,
    VRChatUserState.ACTIVE_ON_WEB_OR_MOBILE.value,
]

VRCHAT_USER_STATUS_COLOR_MAP = {
    VRChatUserState.JOIN_ME: "#42caff",
    VRChatUserState.ACTIVE: "#51e57e",
    VRChatUserState.ASK_ME: "#e88134",
    VRChatUserState.BUSY: "#5b0b0b",
    VRChatUserState.OFFLINE: "#737f8d",
}

_USER_STATUS_INDICATOR_DIAMETER = 15
_USER_STATUS_INDICATOR_RADIUS = _USER_STATUS_INDICATOR_DIAMETER / 2
_USER_STATUS_INDICATOR_STROKE_WIDTH = 3
_USER_STATUS_INDICATOR_CANVAS_SIZE = 30
_USER_STATUS_INDICATOR_CENTER = _USER_STATUS_INDICATOR_CANVAS_SIZE / 2


def _user_status_indicator_in_game(color: str):
    """Return a user status indicator when in a game."""
    return f'''<svg width="{_USER_STATUS_INDICATOR_CANVAS_SIZE}" height="{_USER_STATUS_INDICATOR_CANVAS_SIZE}" viewBox="0 0 {_USER_STATUS_INDICATOR_CANVAS_SIZE} {_USER_STATUS_INDICATOR_CANVAS_SIZE}" xmlns="http://www.w3.org/2000/svg">
          <circle
            cx="{_USER_STATUS_INDICATOR_CENTER}"
            cy="{_USER_STATUS_INDICATOR_CENTER}"
            r="{_USER_STATUS_INDICATOR_RADIUS}"
            fill="{color}"
            stroke="none"
          />
        </svg>
        '''


def _user_status_indicator_not_in_game(color: str):
    """Return a user status indicator when not in a game."""
    return f'''<svg width="{_USER_STATUS_INDICATOR_CANVAS_SIZE}" height="{_USER_STATUS_INDICATOR_CANVAS_SIZE}" viewBox="0 0 {_USER_STATUS_INDICATOR_CANVAS_SIZE} {_USER_STATUS_INDICATOR_CANVAS_SIZE}" xmlns="http://www.w3.org/2000/svg">
          <circle
            cx="{_USER_STATUS_INDICATOR_CENTER}"
            cy="{_USER_STATUS_INDICATOR_CENTER}"
            r="{_USER_STATUS_INDICATOR_RADIUS - _USER_STATUS_INDICATOR_STROKE_WIDTH / 2}"
            fill="none"
            stroke="{color}"
            stroke-width="{_USER_STATUS_INDICATOR_STROKE_WIDTH}"
          />
        </svg>
        '''


VRCHAT_USER_STATUS_INDICATOR_MAP_IN_GAME = {
    status: svg_file_uri(_user_status_indicator_in_game(color))
    for status, color in VRCHAT_USER_STATUS_COLOR_MAP.items()
}

VRCHAT_USER_STATUS_INDICATOR_MAP_NOT_IN_GAME = {
    status: svg_file_uri(_user_status_indicator_not_in_game(color))
    for status, color in VRCHAT_USER_STATUS_COLOR_MAP.items()
}
