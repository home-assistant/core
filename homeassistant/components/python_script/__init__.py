"""Component to allow running Python scripts."""

import logging
import os

import probatio

from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, FOLDER
from .services import setup_services

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = probatio.Schema(
    {DOMAIN: probatio.Schema(dict)}, extra=probatio.ALLOW_EXTRA
)


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Initialize the Python script component."""
    path = hass.config.path(FOLDER)

    if not os.path.isdir(path):
        _LOGGER.warning("Folder %s not found in configuration folder", FOLDER)
        return False

    setup_services(hass)

    return True
