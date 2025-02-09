"""Coordinator for the Modern Forms integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from aiomodernforms import ModernFormsDevice, ModernFormsError
from aiomodernforms.models import Device as ModernFormsDeviceState

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

SCAN_INTERVAL = timedelta(seconds=5)
_LOGGER = logging.getLogger(__name__)


class ModernFormsDataUpdateCoordinator(DataUpdateCoordinator[ModernFormsDeviceState]):
    """Class to manage fetching Modern Forms data from single endpoint."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize global Modern Forms data updater."""
        self.modern_forms = ModernFormsDevice(
            config_entry.data[CONF_HOST], session=async_get_clientsession(hass)
        )

        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> ModernFormsDevice:
        """Fetch data from Modern Forms."""
        try:
            return await self.modern_forms.update(
                full_update=not self.last_update_success
            )
        except ModernFormsError as error:
            raise UpdateFailed(f"Invalid response from API: {error}") from error
