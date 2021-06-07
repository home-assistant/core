"""Helpers to help coordinate updated."""
from __future__ import annotations

from datetime import timedelta
import logging

from pymfy.api.model import Device
from pymfy.api.somfy_api import SomfyApi
from requests.exceptions import HTTPError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed


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
        self.site_ids = []
        self.last_site_index = -1

    async def _async_update_data(self) -> dict[str, Device]:
        """Fetch Somfy data."""
        if not self.site_ids:
            try:
                sites = await self.hass.async_add_executor_job(self.client.get_sites)
            except HTTPError:
                sites = []
            self.site_ids = [site.id for site in sites]
            if not self.site_ids:
                raise UpdateFailed("Somfy did not returned any site id.")

        try:
            devices = await self.hass.async_add_executor_job(
                self.client.get_devices, self._site_id
            )
        except HTTPError:
            devices = []

        previous_devices = self.data
        # Sometimes Somfy returns an empty list.
        if not devices and previous_devices:
            self.logger.debug(
                "No devices returned. Assuming the previous ones are still valid"
            )
            return previous_devices

        return {dev.id: dev for dev in devices}

    @property
    def _site_id(self):
        """Return the next site id to retrieve.

        This tweak is required as Somfy does not allow to call the /site entrypoint more than once per minute.
        """
        self.last_site_index = (self.last_site_index + 1) % len(self.site_ids)
        return self.site_ids[self.last_site_index]
