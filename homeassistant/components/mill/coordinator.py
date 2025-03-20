"""Coordinator for the mill component."""

from __future__ import annotations

from datetime import timedelta
import logging

from mill import Mill
from mill_local import Mill as MillLocal

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class MillDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Mill data."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        mill_data_connection: Mill | MillLocal,
        update_interval: timedelta,
    ) -> None:
        """Initialize global Mill data updater."""
        self.mill_data_connection = mill_data_connection

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_method=mill_data_connection.fetch_heater_and_sensor_data,
            update_interval=update_interval,
        )
