"""Constants for the Control4 integration."""

from dataclasses import dataclass, field
from typing import Any

from pyControl4.account import C4Account
from pyControl4.director import C4Director
from pyControl4.websocket import C4Websocket

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE

DOMAIN = "control4"


@dataclass
class Control4RuntimeData:
    """Runtime data for a Control4 config entry.

    account/director/websocket are always present once the entry has finished
    setup; the rest are set once during async_setup_entry. cancel_token_refresh_callback
    starts unset because it's only assigned after the first refresh is scheduled.
    """

    account: C4Account
    director: C4Director
    websocket: C4Websocket
    controller_unique_id: str = ""
    director_sw_version: str = ""
    director_model: str = ""
    director_all_items: list[dict[str, Any]] = field(default_factory=list)
    ui_configuration: dict[str, Any] | None = None
    cancel_token_refresh_callback: CALLBACK_TYPE | None = None


type Control4ConfigEntry = ConfigEntry[Control4RuntimeData]

CONF_CONTROLLER_UNIQUE_ID = "controller_unique_id"

CONTROL4_ENTITY_TYPE = 7

RETRY_BACKOFF_MAX_SEC = 30
SCHEDULE_REFRESH_ADVANCE_SEC = 300

DEFAULT_SCAN_INTERVAL = 5
