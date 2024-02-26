"""DataUpdateCoordinator for motion blinds integration."""
import asyncio
from datetime import timedelta
import logging
from typing import Any

from motionblinds import DEVICE_TYPES_WIFI, ParseException

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    ATTR_AVAILABLE,
    CONF_WAIT_FOR_PUSH,
    KEY_API_LOCK,
    KEY_GATEWAY,
    UPDATE_INTERVAL,
    UPDATE_INTERVAL_FAST,
)

_LOGGER = logging.getLogger(__name__)


class DataUpdateCoordinatorMotionBlinds(DataUpdateCoordinator):
    """Class to manage fetching data from single endpoint."""

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        coordinator_info: dict[str, Any],
        *,
        name: str,
        update_interval: timedelta,
    ) -> None:
        """Initialize global data updater."""
        super().__init__(
            hass,
            logger,
            name=name,
            update_interval=update_interval,
        )

        self.api_lock = coordinator_info[KEY_API_LOCK]
        self._gateway = coordinator_info[KEY_GATEWAY]
        self._wait_for_push = coordinator_info[CONF_WAIT_FOR_PUSH]

    def update_gateway(self):
        """Fetch data from gateway."""
        try:
            self._gateway.Update()
        except (TimeoutError, ParseException):
            # let the error be logged and handled by the motionblinds library
            return {ATTR_AVAILABLE: False}

        return {ATTR_AVAILABLE: True}

    def update_blind(self, blind):
        """Fetch data from a blind."""
        try:
            if blind.device_type in DEVICE_TYPES_WIFI:
                blind.Update_from_cache()
            elif self._wait_for_push:
                blind.Update()
            else:
                blind.Update_trigger()
        except (TimeoutError, ParseException):
            # let the error be logged and handled by the motionblinds library
            return {ATTR_AVAILABLE: False}

        return {ATTR_AVAILABLE: True}

    async def _async_update_data(self):
        """Fetch the latest data from the gateway and blinds."""
        data = {}

        async with self.api_lock:
            data[KEY_GATEWAY] = await self.hass.async_add_executor_job(
                self.update_gateway
            )

        for blind in self._gateway.device_list.values():
            await asyncio.sleep(1.5)
            async with self.api_lock:
                data[blind.mac] = await self.hass.async_add_executor_job(
                    self.update_blind, blind
                )

        all_available = all(device[ATTR_AVAILABLE] for device in data.values())
        if all_available:
            self.update_interval = timedelta(seconds=UPDATE_INTERVAL)
        else:
            self.update_interval = timedelta(seconds=UPDATE_INTERVAL_FAST)

        return data
