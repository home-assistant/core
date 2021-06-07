"""Helpers to help coordinate updated."""

from datetime import timedelta
import logging
from typing import Dict, Optional

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
        update_interval: Optional[timedelta] = None,
    ):
        """Initialize global data updater."""
        super().__init__(
            hass,
            logger,
            name=name,
            update_interval=update_interval,
        )

        self.data = {}
        self.client = client

    async def _async_update_data(self) -> Dict[str, Device]:
        """Fetch Somfy data."""
        devices = await self.hass.async_add_executor_job(self.client.get_devices)
        previous_devices = self.data
        # Sometimes Somfy returns an empty list.
        if not devices and previous_devices:
            self.logger.debug(
                "No devices returned. Assuming the previous ones are still valid"
            )
            return previous_devices
        return {dev.id: dev for dev in devices}
