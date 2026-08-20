"""Models for the cloud integration."""

from collections.abc import Callable
import dataclasses
from datetime import datetime


@dataclasses.dataclass
class PendingAutoLogin:
    """A registration waiting for its email confirmation to log in."""

    email: str
    expires_at: datetime
    cancel: Callable[[], None]


@dataclasses.dataclass
class CloudLoginState:
    """State shared between a login and the handler reacting to it."""

    pending_auto_login: PendingAutoLogin | None = None
    new_cloud_pipeline_id: str | None = None
