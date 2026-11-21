"""Hassio Discovery data."""

from dataclasses import dataclass
from typing import Any

from homeassistant.data_entry_flow import BaseServiceInfo


@dataclass(slots=True)
class HassioServiceInfo(BaseServiceInfo):
    """Prepared info from hassio entries."""

    config: dict[str, Any]
    name: str
    slug: str
    uuid: str
    panel_admin: bool = True
    """If the app's panel is limited to admin users, or its access is unknown."""
