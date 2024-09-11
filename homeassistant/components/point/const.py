"""Define constants for the Point component."""

import asyncio
from dataclasses import dataclass, field
from datetime import timedelta

from . import MinutPointClient

DOMAIN = "point"

SCAN_INTERVAL = timedelta(minutes=1)

CONF_WEBHOOK_URL = "webhook_url"
CONF_REFRESH_TOKEN = "refresh_token"
EVENT_RECEIVED = "point_webhook_received"
SIGNAL_UPDATE_ENTITY = "point_update"
SIGNAL_WEBHOOK = "point_webhook"

POINT_DISCOVERY_NEW = "point_new_{}_{}"

OAUTH2_AUTHORIZE = "https://api.minut.com/v8/oauth/authorize"
OAUTH2_TOKEN = "https://api.minut.com/v8/oauth/token"


@dataclass
class PointData:
    """Point Data."""

    client: MinutPointClient
    entry_lock: asyncio.Lock = asyncio.Lock()
    entries: set[str | None] = field(default_factory=set)
