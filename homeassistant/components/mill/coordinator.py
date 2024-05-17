"""Coordinator for the mill component."""

from __future__ import annotations

from datetime import timedelta
import logging

from mill import Mill
from mill_local import Mill as MillLocal

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class MillDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Mill data."""

    def __init__(
        self,
        hass: HomeAssistant,
        update_interval: timedelta | None = None,
        *,
        mill_data_connection: Mill | MillLocal,
    ) -> None:
        """Initialize global Mill data updater."""
        self.mill_data_connection = mill_data_connection

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_method=mill_data_connection.fetch_heater_and_sensor_data,
            update_interval=update_interval,
        )
