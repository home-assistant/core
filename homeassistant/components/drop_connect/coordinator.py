"""DROP device data update coordinator object."""
from __future__ import annotations

import logging

from dropmqttapi.mqttapi import DropAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class DROPDeviceDataUpdateCoordinator(DataUpdateCoordinator):
    """DROP device object."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, unique_id: str) -> None:
        """Initialize the device."""
        super().__init__(hass, _LOGGER, name=f"{DOMAIN}-{unique_id}")
        self.drop_api = DropAPI()
