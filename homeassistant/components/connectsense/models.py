from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.config_entries import ConfigEntry


@dataclass
class ConnectSenseRuntimeData:
    store: dict[str, Any]


type ConnectSenseConfigEntry = ConfigEntry[ConnectSenseRuntimeData]
