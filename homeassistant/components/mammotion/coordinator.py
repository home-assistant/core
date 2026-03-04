"""Provides the mammotion DataUpdateCoordinator."""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Mapping
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from mashumaro.exceptions import InvalidFieldValue
from pymammotion.aliyun.model.dev_by_account_response import Device
from pymammotion.data.model.device import MowingDevice
from pymammotion.homeassistant import HomeAssistantMowerApi
from pymammotion.mammotion.devices.mammotion import MammotionMowerDeviceManager

from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .config import MammotionConfigStore
from .const import (
    CONF_ACCOUNTNAME,
    CONF_AEP_DATA,
    CONF_AUTH_DATA,
    CONF_CONNECT_DATA,
    CONF_DEVICE_DATA,
    CONF_MAMMOTION_DATA,
    CONF_REGION_DATA,
    CONF_SESSION_DATA,
    DOMAIN,
    LOGGER,
)

if TYPE_CHECKING:
    from . import MammotionConfigEntry

DEFAULT_INTERVAL = timedelta(minutes=1)


class MammotionBaseUpdateCoordinator(DataUpdateCoordinator[MowingDevice]):
    """Mammotion DataUpdateCoordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: MammotionConfigEntry,
        device: Device,
        api: HomeAssistantMowerApi,
        update_interval: timedelta,
    ) -> None:
        """Initialize global mammotion data updater."""
        super().__init__(
            hass=hass,
            logger=LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
            config_entry=config_entry,
        )
        assert config_entry.unique_id
        self.device: Device = device
        self.device_name = device.device_name
        self.api: HomeAssistantMowerApi = api
        self.account = config_entry.data[CONF_ACCOUNTNAME]
        self.password = config_entry.data[CONF_PASSWORD]
        self.update_failures = 0

    def __del__(self) -> None:
        """Cleanup and store credentials."""
        self.store_cloud_credentials()

    @abstractmethod
    def get_coordinator_data(self, device: MammotionMowerDeviceManager) -> MowingDevice:
        """Get coordinator data."""

    async def async_refresh_login(self) -> None:
        """Refresh login credentials asynchronously."""
        await self.api.mammotion.refresh_login(self.account)
        self.store_cloud_credentials()

    def store_cloud_credentials(self) -> None:
        """Store cloud credentials in config entry."""
        # config_updates = {}
        if config_entry := self.config_entry:
            mammotion_cloud = self.api.mammotion.mqtt_list.get(
                config_entry.data.get(CONF_ACCOUNTNAME, "")
            )
            cloud_client = mammotion_cloud.cloud_client if mammotion_cloud else None

            if cloud_client is not None:
                config_updates = {
                    **config_entry.data,
                    CONF_CONNECT_DATA: cloud_client.connect_response,
                    CONF_AUTH_DATA: cloud_client.login_by_oauth_response,
                    CONF_REGION_DATA: cloud_client.region_response,
                    CONF_AEP_DATA: cloud_client.aep_response,
                    CONF_SESSION_DATA: cloud_client.session_by_authcode_response,
                    CONF_DEVICE_DATA: cloud_client.devices_by_account_response,
                    CONF_MAMMOTION_DATA: cloud_client.mammotion_http.response,
                }
                self.hass.config_entries.async_update_entry(
                    config_entry, data=config_updates
                )

    def is_online(self) -> bool:
        """Check if device is online."""
        if device := self.api.mammotion.get_device_by_name(self.device_name):
            return device.state.online or bool(
                device.ble and device.ble.client and device.ble.client.is_connected
            )
        return False

    async def async_send_command(self, command: str, **kwargs: Any) -> bool | None:
        """Send command via api."""
        return await self.api.async_send_command(self.device_name, command, **kwargs)


class MammotionMowerUpdateCoordinator(MammotionBaseUpdateCoordinator):
    """Class to manage fetching mammotion report data."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: MammotionConfigEntry,
        device: Device,
        api: HomeAssistantMowerApi,
    ) -> None:
        """Initialize mammotion data updater."""
        super().__init__(
            hass=hass,
            config_entry=config_entry,
            device=device,
            api=api,
            update_interval=DEFAULT_INTERVAL,
        )

    def get_coordinator_data(self, device: MammotionMowerDeviceManager) -> MowingDevice:
        """Get device state for the coordinator."""
        return device.state

    async def async_restore_data(self) -> None:
        """Restore saved data."""
        store = MammotionConfigStore(self.hass)
        restored_data: Mapping[str, Any] | None = await store.async_load()

        if restored_data is None:
            self.data = MowingDevice()
            self.api.mammotion.get_device_by_name(self.device_name).state = self.data
            return

        try:
            if mower_data := restored_data.get(self.device_name):
                mower_state = MowingDevice().from_dict(mower_data)
                if device := self.api.mammotion.get_device_by_name(self.device_name):
                    device.state = mower_state
        except InvalidFieldValue:
            self.data = MowingDevice()
            self.api.mammotion.get_device_by_name(self.device_name).state = self.data

    async def async_save_data(self, data: MowingDevice) -> None:
        """Get map data from the device."""
        store = MammotionConfigStore(self.hass)
        current_store: dict[str, Any] = await store.async_load() or {}
        current_store[self.device_name] = data.to_dict()
        await store.async_save(current_store)

    async def _async_update_data(self) -> MowingDevice:
        """Get data from the device."""
        data = await self.api.update(self.device_name)
        await self.async_save_data(data)

        return data
