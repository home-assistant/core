"""YoLink DataUpdateCoordinator."""

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import logging
from typing import Any

from yolink.client_request import ClientRequest
from yolink.const import ATTR_DEVICE_SPRINKLER_V2
from yolink.device import YoLinkDevice
from yolink.exception import YoLinkAuthFailError, YoLinkClientError
from yolink.home_manager import YoLinkHome
from yolink.model import BRDP

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import ATTR_DEVICE_STATE, ATTR_LORA_INFO, DOMAIN, YOLINK_OFFLINE_TIME

_LOGGER = logging.getLogger(__name__)

SPRINKLER_ACTIVE_INTERVAL = timedelta(seconds=30)
SPRINKLER_IDLE_INTERVAL = timedelta(minutes=30)


@dataclass
class YoLinkHomeStore:
    """YoLink home store."""

    home_instance: YoLinkHome
    device_coordinators: dict[str, YoLinkCoordinator]


type YoLinkConfigEntry = ConfigEntry[YoLinkHomeStore]


class YoLinkCoordinator(DataUpdateCoordinator[dict]):
    """YoLink DataUpdateCoordinator."""

    config_entry: YoLinkConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: YoLinkConfigEntry,
        device: YoLinkDevice,
        paired_device: YoLinkDevice | None = None,
    ) -> None:
        """Init YoLink DataUpdateCoordinator.

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
        self.dev_online = True
        self.dev_net_type = None

    async def _async_update_data(self) -> dict:
        """Fetch device state."""
        try:
            async with asyncio.timeout(10):
                if self.device.device_type == ATTR_DEVICE_SPRINKLER_V2:
                    device_state_resp = await self._fetch_sprinkler_v2()
                else:
                    device_state_resp = await self.device.fetch_state()
                device_state = device_state_resp.data.get(ATTR_DEVICE_STATE)
                device_reporttime = device_state_resp.data.get("reportAt")
                if device_reporttime is not None:
                    rpt_time_delta = (
                        datetime.now(tz=UTC).replace(tzinfo=None)
                        - datetime.strptime(device_reporttime, "%Y-%m-%dT%H:%M:%S.%fZ")
                    ).total_seconds()
                    self.dev_online = rpt_time_delta < YOLINK_OFFLINE_TIME
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
            if self.device.device_type == ATTR_DEVICE_SPRINKLER_V2 and self.data:
                _LOGGER.debug(
                    "SprinklerV2 %s poll failed (%s), keeping previous data",
                    self.device.device_id,
                    yl_client_err,
                )
                return self.data
            _LOGGER.error(
                "Failed to obtain device status, device: %s, error: %s ",
                self.device.device_id,
                yl_client_err,
            )
            raise UpdateFailed from yl_client_err
        if device_state is not None:
            if self.device.device_type == ATTR_DEVICE_SPRINKLER_V2:
                # SprinklerV2 returns the full API response (not just the
                # "state" sub-dict) because progress, target, and attributes
                # live at the top level alongside "state". Note the key
                # collision: data["state"]["running"] is a bool (valve open),
                # while data["running"] is a dict (progress/target info).
                # Sensor value lambdas for SprinklerV2 must account for this
                # different shape vs other device types.
                full_data = device_state_resp.data
                dev_lora_info = full_data.get(ATTR_LORA_INFO)
                if dev_lora_info is not None:
                    self.dev_net_type = dev_lora_info.get("devNetType")
                if (
                    self.data
                    and "attributes" not in full_data
                    and "attributes" in self.data
                ):
                    full_data["attributes"] = self.data["attributes"]
                self.adjust_sprinkler_interval(full_data)
                return full_data
            dev_lora_info = device_state.get(ATTR_LORA_INFO)
            if dev_lora_info is not None:
                self.dev_net_type = dev_lora_info.get("devNetType")
            self.adjust_sprinkler_interval(device_state)
            return device_state
        return {}

    async def _fetch_sprinkler_v2(self) -> BRDP:
        """Fetch SprinklerV2 state: getState for live data, fetchState as fallback.

        Uses self.device.call_device (returns BRDP), not the coordinator's
        self.call_device wrapper (returns dict).
        """
        try:
            return await self.device.call_device(ClientRequest("getState", {}))
        except YoLinkClientError as err:
            _LOGGER.debug(
                "SprinklerV2 %s getState failed (%s), falling back to fetchState",
                self.device.device_id,
                err,
            )
            return await self.device.fetch_state()

    def adjust_sprinkler_interval(self, device_state: dict) -> None:
        """Speed up polling while SprinklerV2 valve is running."""
        if self.device.device_type != ATTR_DEVICE_SPRINKLER_V2:
            return
        is_running = (
            state.get("running")
            if (state := device_state.get("state")) is not None
            else False
        )
        new_interval = (
            SPRINKLER_ACTIVE_INTERVAL if is_running else SPRINKLER_IDLE_INTERVAL
        )
        if self.update_interval != new_interval:
            self.update_interval = new_interval
            self._schedule_refresh()
            _LOGGER.debug(
                "SprinklerV2 %s poll interval -> %s",
                self.device.device_id,
                new_interval,
            )

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
