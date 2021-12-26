"""Helpers to help coordinate updated."""
from __future__ import annotations

from datetime import timedelta
import logging

from pymfy.api.error import QuotaViolationException, SetupNotFoundException
from pymfy.api.model import Device
from pymfy.api.somfy_api import SomfyApi

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


class SomfyDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Somfy data."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        *,
        name: str,
        client: SomfyApi,
        update_interval: timedelta | None = None,
    ) -> None:
        """Initialize global data updater."""
        super().__init__(
            hass,
            logger,
            name=name,
            update_interval=update_interval,
        )
        self.data = {}
        self.client = client
        self.site_device = {}
        self.last_site_index = -1

    async def _async_update_data(self) -> dict[str, Device]:
        """Fetch Somfy data.

        Somfy only allow one call per minute to /site. There is one exception: 2 calls are allowed after site retrieval.
        """
        if not self.site_device:
            sites = await self.hass.async_add_executor_job(self.client.get_sites)
            if not sites:
                return {}
            self.site_device = {site.id: [] for site in sites}

        site_id = self._site_id
        try:
            devices = await self.hass.async_add_executor_job(
                self.client.get_devices, site_id
            )
            self.site_device[site_id] = devices
        except SetupNotFoundException:
            del self.site_device[site_id]
            return await self._async_update_data()
        except QuotaViolationException:
            self.logger.warning("Quota violation")

        return {dev.id: dev for devices in self.site_device.values() for dev in devices}

    @property
    def _site_id(self):
        """Return the next site id to retrieve.

        This tweak is required as Somfy does not allow to call the /site entrypoint more than once per minute.
        """
        self.last_site_index = (self.last_site_index + 1) % len(self.site_device)
        return list(self.site_device.keys())[self.last_site_index]
