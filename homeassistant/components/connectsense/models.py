from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry

if TYPE_CHECKING:
    from rebooterpro_async import RebooterProClient
    from .coordinator import ConnectSenseCoordinator


@dataclass
class ConnectSenseRuntimeData:
    store: dict[str, Any]
    coordinator: "ConnectSenseCoordinator"
    client: "RebooterProClient"


type ConnectSenseConfigEntry = ConfigEntry[ConnectSenseRuntimeData]