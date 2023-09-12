"""YoLink DataUpdateCoordinator."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from yolink.device import YoLinkDevice
from yolink.exception import YoLinkAuthFailError, YoLinkClientError

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import ATTR_DEVICE_STATE, DOMAIN

_LOGGER = logging.getLogger(__name__)


class YoLinkCoordinator(DataUpdateCoordinator[dict]):
    """YoLink DataUpdateCoordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        device: YoLinkDevice,
        paired_device: YoLinkDevice | None = None,
    ) -> None:
        """Init YoLink DataUpdateCoordinator.

        fetch state every 30 minutes base on yolink device heartbeat interval
        data is None before the first successful update, but we need to use
        data at first update
        """
        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=timedelta(minutes=30)
        )
        self.device = device
        self.paired_device = paired_device

    async def _async_update_data(self) -> dict:
        """Fetch device state."""
        try:
            async with asyncio.timeout(10):
                device_state_resp = await self.device.fetch_state()
                device_state = device_state_resp.data.get(ATTR_DEVICE_STATE)
                if self.paired_device is not None and device_state is not None:
                    paried_device_state_resp = await self.paired_device.fetch_state()
                    paried_device_state = paried_device_state_resp.data.get(
                        ATTR_DEVICE_STATE
                    )
                    if (
                        paried_device_state is not None
                        and ATTR_DEVICE_STATE in paried_device_state
                    ):
                        device_state[ATTR_DEVICE_STATE] = paried_device_state[
                            ATTR_DEVICE_STATE
                        ]
        except YoLinkAuthFailError as yl_auth_err:
            raise ConfigEntryAuthFailed from yl_auth_err
        except YoLinkClientError as yl_client_err:
            raise UpdateFailed from yl_client_err
        if device_state is not None:
            return device_state
        return {}
