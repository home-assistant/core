"""Coordinator for Hyundai / Kia Connect integration."""
from datetime import timedelta
import logging
from typing import Set

from hyundai_kia_connect_api import (
    Token,
    VehicleManager,
    get_implementation_by_region_brand,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_PIN,
    CONF_REGION,
    CONF_TOKEN,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_BRAND, DOMAIN

_LOGGER = logging.getLogger(__name__)


class HyundaiKiaConnectDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize."""
        self.platforms: Set[str] = set()
        token = Token(config_entry.data[CONF_TOKEN])
        api = get_implementation_by_region_brand(
            region=config_entry.data.get(CONF_REGION),
            brand=config_entry.data.get(CONF_BRAND),
            username=config_entry.data.get(CONF_USERNAME),
            password=config_entry.data.get(CONF_PASSWORD),
            pin=config_entry.data.get(CONF_PIN),
        )

        self.vehicle_manager = VehicleManager()
        self.vehicle_id = self.vehicle_manager.add(token, api).id

        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=timedelta(seconds=60)
        )

    async def _async_update_data(self):
        """Update data via library."""
        return await self.async_update()

    async def async_update(self):
        """Update vehicle data via library."""
        await self.async_check_and_refresh_token()
        await self.hass.async_add_executor_job(
            self.vehicle_manager.update_vehicle, self.vehicle_id
        )
        return self.vehicle_manager.get_vehicle(self.vehicle_id)

    async def async_force_update(self):
        """Force update vehicle data via library."""
        await self.async_check_and_refresh_token()
        await self.hass.async_add_executor_job(
            self.vehicle_manager.force_update_vehicle, self.vehicle_id
        )

    async def async_check_and_refresh_token(self):
        """Refresh token if needed via library."""
        if await self.hass.async_add_executor_job(
            self.vehicle_manager.check_and_refresh_token, self.vehicle_id
        ):
            data = self.config_entry.data.copy()
            data[CONF_TOKEN] = vars(self.vehicle_manager.get_token(self.vehicle_id))
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=data, options=self.config_entry.options
            )
