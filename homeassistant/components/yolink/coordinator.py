"""YoLink DataUpdateCoordinator."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

import async_timeout
from yolink.client import YoLinkClient
from yolink.device import YoLinkDevice
from yolink.exception import YoLinkAuthFailError, YoLinkClientError
from yolink.model import BRDP
from yolink.mqtt_client import MqttClient

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import ATTR_DEVICE, ATTR_DEVICE_STATE, DOMAIN

_LOGGER = logging.getLogger(__name__)


class YoLinkCoordinator(DataUpdateCoordinator[dict]):
    """YoLink DataUpdateCoordinator."""

    def __init__(
        self, hass: HomeAssistant, yl_client: YoLinkClient, yl_mqtt_client: MqttClient
    ) -> None:
        """Init YoLink DataUpdateCoordinator.

        fetch state every 30 minutes base on yolink device heartbeat interval
        data is None before the first successful update, but we need to use data at first update
        """
        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=timedelta(minutes=30)
        )
        self._client = yl_client
        self._mqtt_client = yl_mqtt_client
        self.yl_devices: list[YoLinkDevice] = []
        self.data = {}

    def on_message_callback(self, message: tuple[str, BRDP]):
        """On message callback."""
        data = message[1]
        if data.event is None:
            return
        event_param = data.event.split(".")
        event_type = event_param[len(event_param) - 1]
        if event_type not in (
            "Report",
            "Alert",
            "StatusChange",
            "getState",
        ):
            return
        resolved_state = data.data
        if resolved_state is None:
            return
        self.data[message[0]] = resolved_state
        self.async_set_updated_data(self.data)

    async def init_coordinator(self):
        """Init coordinator."""
        try:
            async with async_timeout.timeout(10):
                home_info = await self._client.get_general_info()
                await self._mqtt_client.init_home_connection(
                    home_info.data["id"], self.on_message_callback
                )
            async with async_timeout.timeout(10):
                device_response = await self._client.get_auth_devices()

        except YoLinkAuthFailError as yl_auth_err:
            raise ConfigEntryAuthFailed from yl_auth_err

        except (YoLinkClientError, asyncio.TimeoutError) as err:
            raise ConfigEntryNotReady from err

        yl_devices: list[YoLinkDevice] = []

        for device_info in device_response.data[ATTR_DEVICE]:
            yl_devices.append(YoLinkDevice(device_info, self._client))

        self.yl_devices = yl_devices

    async def fetch_device_state(self, device: YoLinkDevice):
        """Fetch Device State."""
        try:
            async with async_timeout.timeout(10):
                device_state_resp = await device.fetch_state_with_api()
                if ATTR_DEVICE_STATE in device_state_resp.data:
                    self.data[device.device_id] = device_state_resp.data[
                        ATTR_DEVICE_STATE
                    ]
                else:
                    self.data[device.device_id] = {"state": None}
        except YoLinkAuthFailError as yl_auth_err:
            raise ConfigEntryAuthFailed from yl_auth_err
        except YoLinkClientError:
            # Current device unknown state.
            _LOGGER.error("Error Fetching device: %s state", device.device_id)
            self.data[device.device_id] = {"state": None}

    async def _async_update_data(self) -> dict:
        fetch_tasks = []
        for yl_device in self.yl_devices:
            fetch_tasks.append(self.fetch_device_state(yl_device))
        if fetch_tasks:
            await asyncio.gather(*fetch_tasks)
        return self.data
