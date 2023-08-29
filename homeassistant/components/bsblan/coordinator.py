"""DataUpdateCoordinator for the BSB-Lan integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from random import randint

from bsblan import BSBLAN, BSBLANConnectionError
from bsblan.models import State

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class BSBLanUpdateCoordinator(DataUpdateCoordinator[State]):
    """The BSB-Lan update coordinator."""

    config_entry: ConfigEntry
    client: BSBLAN

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        client: BSBLAN,
    ) -> None:
        """Initialize the BSB-Lan coordinator."""

        self.config_entry = config_entry
        self.client = client

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{config_entry.data[CONF_HOST]}",
            # use the default scan interval and add a random number of seconds to avoid timeouts when
            # the BSB-Lan device is already/still busy retrieving data, e.g. for MQTT or internal logging.
            update_interval=SCAN_INTERVAL + timedelta(seconds=randint(1, 8)),
        )

    async def _async_update_data(self) -> State:
        """Get state from BSB-Lan device."""

        try:
            return await self.client.state()
        except BSBLANConnectionError as err:
            raise UpdateFailed(
                f"Error while establishing connection with BSB-Lan device at {self.config_entry.data[CONF_HOST]}"
            ) from err
