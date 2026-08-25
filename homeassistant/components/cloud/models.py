"""Models for the cloud integration."""

import dataclasses

from hass_nabucasa import AutoLoginController


@dataclasses.dataclass
class PendingAutoLogin:
    """A registration waiting for its email confirmation to log in."""

    email: str
    controller: AutoLoginController
