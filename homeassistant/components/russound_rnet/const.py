"""Constants for the Russound RNET integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from aiorussound.exceptions import CommandError

DOMAIN = "russound_rnet"

CONF_MODEL = "model"
CONF_SOURCES = "sources"
CONF_BAUDRATE = "baudrate"

TYPE_TCP = "tcp"
TYPE_SERIAL = "serial"

DEFAULT_BAUDRATE = 19200

RNET_EXCEPTIONS = (
    CommandError,
    ConnectionRefusedError,
    TimeoutError,
    asyncio.IncompleteReadError,
    OSError,
)


@dataclass(frozen=True)
class RussoundRNETModel:
    """Russound RNET device model definition."""

    name: str
    max_zones: int
    max_sources: int
    max_controllers: int


RNET_MODELS: dict[str, RussoundRNETModel] = {
    "CAS44": RussoundRNETModel("CAS44", 4, 4, 1),
    "CAA66": RussoundRNETModel("CAA66", 6, 6, 6),
    "CAM6.6": RussoundRNETModel("CAM6.6", 6, 6, 6),
    "CAV6.6": RussoundRNETModel("CAV6.6", 6, 6, 6),
    "MCA-C3": RussoundRNETModel("MCA-C3", 6, 6, 6),
    "MCA-C5": RussoundRNETModel("MCA-C5", 8, 8, 6),
    "ACA-E5": RussoundRNETModel("ACA-E5", 6, 8, 8),
}
