"""Common vera code."""
import logging
from typing import DefaultDict, List, NamedTuple, Set

import pyvera as pv

from homeassistant.components.scene import DOMAIN as SCENE_DOMAIN

_LOGGER = logging.getLogger(__name__)


class ControllerData(NamedTuple):
    """Controller data."""

    controller: pv.VeraController
    devices: DefaultDict[str, List[pv.VeraDevice]]
    scenes: List[pv.VeraScene]


def get_configured_platforms(controller_data: ControllerData) -> Set[str]:
    """Get configured platforms for a controller."""
    platforms = []
    for platform in controller_data.devices:
        platforms.append(platform)

    if controller_data.scenes:
        platforms.append(SCENE_DOMAIN)

    return set(platforms)
