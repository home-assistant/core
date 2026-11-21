"""Constants for the Control4 integration."""

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from pyControl4.account import C4Account
from pyControl4.director import C4Director
from pyControl4.websocket import C4Websocket

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE

if TYPE_CHECKING:
    from .coordinator import Control4DataUpdateCoordinator

DOMAIN = "control4"


@dataclass
class Control4RuntimeData:
    """Runtime data for a Control4 config entry; fields past account/director/websocket are set once during async_setup_entry."""

    account: C4Account
    director: C4Director
    websocket: C4Websocket
    controller_unique_id: str = ""
    director_sw_version: str = ""
    director_model: str = ""
    director_all_items: list[dict[str, Any]] = field(default_factory=list)
    ui_configuration: dict[str, Any] | None = None
    cancel_token_refresh_callback: CALLBACK_TYPE | None = None
    cancel_periodic_resync_callback: CALLBACK_TYPE | None = None
    token_refresh_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    resync_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    room_coordinator: Control4DataUpdateCoordinator = field(init=False)


type Control4ConfigEntry = ConfigEntry[Control4RuntimeData]

CONF_CONTROLLER_UNIQUE_ID = "controller_unique_id"

CONTROL4_ENTITY_TYPE = 7

RETRY_BACKOFF_MAX_SEC = 30
SCHEDULE_REFRESH_ADVANCE_SEC = 300

WEBSOCKET_RESYNC_INTERVAL_SEC = 60

CONTROL4_POWER_STATE = "POWER_STATE"
CONTROL4_VOLUME_STATE = "CURRENT_VOLUME"
CONTROL4_MUTED_STATE = "IS_MUTED"
CONTROL4_CURRENT_VIDEO_DEVICE = "CURRENT_VIDEO_DEVICE"
CONTROL4_PLAYING = "PLAYING"
CONTROL4_PAUSED = "PAUSED"
CONTROL4_STOPPED = "STOPPED"
CONTROL4_MEDIA_INFO = "CURRENT MEDIA INFO"

ROOM_VARIABLES = {
    CONTROL4_POWER_STATE,
    CONTROL4_VOLUME_STATE,
    CONTROL4_MUTED_STATE,
    CONTROL4_CURRENT_VIDEO_DEVICE,
    CONTROL4_MEDIA_INFO,
    CONTROL4_PLAYING,
    CONTROL4_PAUSED,
    CONTROL4_STOPPED,
}
