"""YoLink DataUpdateCoordinator."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging
from typing import Any

from yolink.client_request import ClientRequest
from yolink.device import YoLinkDevice
from yolink.exception import YoLinkAuthFailError, YoLinkClientError
from yolink.model import BRDP

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import ATTR_DEVICE_STATE, ATTR_REPORT_AT, DOMAIN

_LOGGER = logging.getLogger(__name__)


class YoLinkLocalCoordinator(DataUpdateCoordinator[dict[str, Any] | None]):
    """YoLink Local DataUpdateCoordinator."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        device: YoLinkDevice,
        paired_device: YoLinkDevice | None = None,
    ) -> None:
        """Init YoLink Local DataUpdateCoordinator.

        fetch state every 30 minutes base on yolink device heartbeat interval
        data is None before the first successful update, but we need to use
        data at first update
        """
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=30),
        )
        self.device = device
        self.paired_device = paired_device
        self.last_report_at: float | None = None

    async def _async_exchange_state_with_paired_device(
        self,
        device_state_data,
    ) -> None:
        """Exchange state with paired device."""
        if self.paired_device is not None and device_state_data is not None:
            paired_device_ret = await self.paired_device.fetch_state()
            if paired_device_ret.data is None:
                return
            paired_device_state_data = paired_device_ret.data.get(ATTR_DEVICE_STATE)
            # exchange state field
            if (
                paired_device_state_data is not None
                and ATTR_DEVICE_STATE in paired_device_state_data
            ):
                device_state_data[ATTR_DEVICE_STATE] = paired_device_state_data[
                    ATTR_DEVICE_STATE
                ]

    @property
    def is_device_online(self) -> bool:
        """Determine if the device is online based on last report time."""
        if self.last_report_at is None:
            return False
        now_timestamp = datetime.now().timestamp()
        keepalive_time = self.device.keepalive_time
        return now_timestamp - self.last_report_at < keepalive_time

    async def _async_update_data(self) -> dict[str, Any] | None:
        """Fetch device state."""
        try:
            async with asyncio.timeout(10):
                device_state_ret = await self.device.fetch_state()
                if device_state_ret.data is None:
                    return None
                device_state_data = (
                    device_state_ret.data
                    if self.device.is_hub
                    else device_state_ret.data.get(ATTR_DEVICE_STATE)
                )
                if (
                    last_report_str := device_state_ret.data.get(ATTR_REPORT_AT)
                ) is not None:
                    self.last_report_at = datetime.fromisoformat(
                        last_report_str
                    ).timestamp()
                await self._async_exchange_state_with_paired_device(device_state_data)
                return device_state_data
        except YoLinkAuthFailError as yl_auth_err:
            raise ConfigEntryAuthFailed from yl_auth_err
        except YoLinkClientError as yl_client_err:
            raise UpdateFailed(
                f"Failed to obtain device status, device: {self.device.device_id}, error: {yl_client_err}"
            ) from yl_client_err

    async def call_device(self, request: ClientRequest) -> dict[str, Any]:
        """Call device api."""
        try:
            # call_device will check result, fail by raise YoLinkClientError
            resp: BRDP = await self.device.call_device(request)
        except YoLinkAuthFailError as yl_auth_err:
            self.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(yl_auth_err) from yl_auth_err
        except YoLinkClientError as yl_client_err:
            raise HomeAssistantError(yl_client_err) from yl_client_err
        else:
            return resp.data
