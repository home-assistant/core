"""Constants for the Russound RNET integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from aiorussound.exceptions import CommandError

DOMAIN = "russound_rnet"

CONF_SOURCES = "sources"
CONF_ZONES = "zones"
CONF_CONTROLLERS = "controllers"

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
    "cas44": RussoundRNETModel("CAS44", 4, 4, 1),
    "caa66": RussoundRNETModel("CAA66", 6, 6, 6),
    "cam6_6": RussoundRNETModel("CAM6.6", 6, 6, 6),
    "cav6_6": RussoundRNETModel("CAV6.6", 6, 6, 6),
    "mca-c3": RussoundRNETModel("MCA-C3", 6, 6, 6),
    "mca-c5": RussoundRNETModel("MCA-C5", 8, 8, 6),
    "aca-e5": RussoundRNETModel("ACA-E5", 6, 8, 8),
}
