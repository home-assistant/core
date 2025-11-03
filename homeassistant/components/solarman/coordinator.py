"""Coordinator for solarman integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any, cast

from solarman_opendata.solarman import Solarman
from solarman_opendata.utils import get_config

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

type SolarmanConfigEntry = ConfigEntry[SolarmanDeviceUpdateCoordinator]


class SolarmanDeviceUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator for managing Solarman device data updates and control operations."""

    config_entry: SolarmanConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the Solarman device coordinator."""
        super().__init__(
            hass,
            logger=_LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=config_entry.data.get("scan_interval", DEFAULT_SCAN_INTERVAL)
            ),
        )

        # Initialize the API client for communicating with the Solarman device.
        self.api = Solarman(
            async_get_clientsession(hass),
            config_entry.data["host"],
            config_entry.data["port"],
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch and update device data.

        This is automatically called by the DataUpdateCoordinator framework
        according to the defined update_interval.
        """
        try:
            config_data = await get_config(
                async_get_clientsession(self.hass), self.config_entry.data["host"]
            )

            device_info = config_data.get("device", config_data)
            fw_version = device_info.get("fw")

            if self.config_entry.data["fw_version"] != fw_version:
                device_registry = dr.async_get(self.hass)
                device_entry = device_registry.async_get_device(
                    identifiers={(DOMAIN, self.config_entry.data["sn"])}
                )

                if device_entry:
                    device_registry.async_update_device(
                        device_id=device_entry.id, sw_version=fw_version
                    )

                    self.hass.config_entries.async_update_entry(
                        self.config_entry,
                        data={**self.config_entry.data, "fw_version": fw_version},
                    )

            # Fetch latest data from the physical device
            data = await self.api.fetch_data()

            # Update the coordinator's data store
            self.data = data
        except ConnectionError as e:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
            ) from e
        else:
            return cast(dict[str, Any], data)
