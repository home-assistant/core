"""Models for the cloud integration."""

import dataclasses
from datetime import datetime

from hass_nabucasa import AutoLoginController


@dataclasses.dataclass
class PendingAutoLogin:
    """A registration waiting for its email confirmation to log in."""

    email: str
    expires_at: datetime
    controller: AutoLoginController


@dataclasses.dataclass
class CloudLoginState:
    """State shared between a login and the handler reacting to it."""

    pending_auto_login: PendingAutoLogin | None = None
    new_cloud_pipeline_id: str | None = None
