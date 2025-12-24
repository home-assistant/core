"""Coordinator for solarman integration."""

from __future__ import annotations

import logging
from typing import Any

from solarman_opendata.solarman import Solarman

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_FW, CONF_FW_VERSION, DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

type SolarmanConfigEntry = ConfigEntry[SolarmanDeviceUpdateCoordinator]


class SolarmanDeviceUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator for managing Solarman device data updates and control operations."""

    config_entry: SolarmanConfigEntry
    fw_version: str = ""

    def __init__(
        self, hass: HomeAssistant, config_entry: SolarmanConfigEntry, client: Solarman
    ) -> None:
        """Initialize the Solarman device coordinator."""

        super().__init__(
            hass,
            logger=_LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )

        # Initialize the API client for communicating with the Solarman device.
        self.api = client

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch and update device data.

        This is automatically called by the DataUpdateCoordinator framework
        according to the defined update_interval.
        """
        data: dict[str, Any] = {}
        try:
            config_data = await self.api.get_config()

            device_info = config_data.get(CONF_DEVICE, config_data)
            fw_version = device_info.get(CONF_FW)

            if self.fw_version != fw_version:
                self.update_sw_version(fw_version=fw_version)
                self.fw_version = fw_version

            data = await self.api.fetch_data()
        except ConnectionError as e:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
            ) from e

        return data

    @callback
    def update_sw_version(self, fw_version: str) -> None:
        """Update device registry with new firmware version, if it changed at runtime."""
        device_registry = dr.async_get(self.hass)
        if (
            device_entry := device_registry.async_get_device(
                identifiers={(DOMAIN, self.config_entry.data["sn"])}
            )
        ):
            device_registry.async_update_device(
                device_id=device_entry.id, sw_version=fw_version
            )

            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={**self.config_entry.data, CONF_FW_VERSION: fw_version},
            )

