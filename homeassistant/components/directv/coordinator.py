"""Provides the DirecTV DataUpdateCoordinator."""
from datetime import timedelta
import logging

from directv import DIRECTV, DIRECTVError

from homeassistant.const import CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class DirecTVDataUpdateCoordinator(DataUpdateCoordinator[Device]):
    """Class to manage fetching DirecTV data."""

    def __init__(self, hass: HomeAssistantType, *, config: dict, options: dict):
        """Initialize global DirecTV data updater."""
        self.dtv = DIRECTV(config[CONF_HOST], session=async_get_clientsession(hass))

        
