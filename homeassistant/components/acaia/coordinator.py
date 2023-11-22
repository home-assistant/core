"""Coordinator for Acaia integration."""
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MAC, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .acaiaclient import AcaiaClient
from .const import CONF_IS_NEW_STYLE_SCALE

SCAN_INTERVAL = timedelta(seconds=15)

_LOGGER = logging.getLogger(__name__)


class AcaiaApiCoordinator(DataUpdateCoordinator):
    """Class to handle fetching data from the La Marzocco API centrally."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Acaia API coordinator",
            update_interval=SCAN_INTERVAL,
        )
        name = config_entry.data[CONF_NAME]
        mac = config_entry.data[CONF_MAC]
        is_new_style_scale = config_entry.data.get(CONF_IS_NEW_STYLE_SCALE, True)

        self._acaia_client: AcaiaClient = AcaiaClient(
            hass,
            mac=mac,
            name=name,
            is_new_style_scale=is_new_style_scale,
            notify_callback=self.async_update_listeners,
        )

    @property
    def acaia_client(self) -> AcaiaClient:
        """Return the acaia client."""
        return self._acaia_client

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data."""
        try:
            await self.acaia_client.async_update()
        except Exception as ex:
            raise UpdateFailed("Error: %s" % ex) from ex

        return self.acaia_client.data
