"""Constants for the VRChat integration."""

from enum import StrEnum
from typing import Final

from homeassistant.const import __version__

DOMAIN = "vrchat"

CONF_2FA_CODE: Final = "2fa_code"
CONF_EMAIL_2FA_CODE: Final = "email_2fa_code"

USER_AGENT: Final = (
    f"HomeAssistant/{__version__} https://github.com/home-assistant/core"
)

VRCHAT_USER_PAGE_BASE_URL: Final = "https://vrchat.com/home/user/"


class VRChatUserState(StrEnum):
    """VRChat user state enum."""

    JOIN_ME = "join_me"
    ACTIVE = "active"
    ASK_ME = "ask_me"
    BUSY = "busy"
    OFFLINE = "offline"
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
