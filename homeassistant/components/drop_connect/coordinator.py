"""DROP device data update coordinator object."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from dropmqttapi.mqttapi import DropAPI

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class DROPDeviceDataUpdateCoordinator(DataUpdateCoordinator):
    """DROP device object."""

    def __init__(self, hass: HomeAssistant, unique_id: str) -> None:
        """Initialize the device."""
        super().__init__(hass, _LOGGER, name=f"{DOMAIN}-{unique_id}")
        if TYPE_CHECKING:
            assert self.config_entry is not None
        self.drop_api = DropAPI()
