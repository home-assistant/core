"""The elkm1 integration models."""

from dataclasses import dataclass
from typing import Any

from elkm1_lib import Elk

from homeassistant.config_entries import ConfigEntry

type ElkM1ConfigEntry = ConfigEntry[ELKM1Data]


@dataclass(slots=True)
class ELKM1Data:
    """Data for the elkm1 integration."""

    elk: Elk
    prefix: str
    mac: str | None
    auto_configure: bool
    config: dict[str, Any]
    keypads: dict[str, Any]
