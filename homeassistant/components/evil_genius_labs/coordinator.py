"""Coordinator for the Evil Genius Labs integration."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import cast

from aiohttp import ContentTypeError
import pyevilgenius

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

UPDATE_INTERVAL = 10


class EvilGeniusUpdateCoordinator(DataUpdateCoordinator[dict]):
    """Update coordinator for Evil Genius data."""

    info: dict

    product: dict | None

    def __init__(
        self, hass: HomeAssistant, name: str, client: pyevilgenius.EvilGeniusDevice
    ) -> None:
        """Initialize the data update coordinator."""
        self.client = client
        super().__init__(
            hass,
            logging.getLogger(__name__),
            name=name,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )

    @property
    def device_name(self) -> str:
        """Return the device name."""
        return cast(str, self.data["name"]["value"])

    @property
    def product_name(self) -> str | None:
        """Return the product name."""
        if self.product is None:
            return None

        return cast(str, self.product["productName"])

    async def _async_update_data(self) -> dict:
        """Update Evil Genius data."""
        if not hasattr(self, "info"):
            async with asyncio.timeout(5):
                self.info = await self.client.get_info()

        if not hasattr(self, "product"):
            async with asyncio.timeout(5):
                try:
                    self.product = await self.client.get_product()
                except ContentTypeError:
                    # Older versions of the API don't support this
                    self.product = None

        async with asyncio.timeout(5):
            return cast(dict, await self.client.get_all())
