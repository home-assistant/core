"""Provides the mammotion DataUpdateCoordinator."""

from collections.abc import Mapping
from datetime import timedelta
from typing import TYPE_CHECKING, Any, override

from mashumaro.exceptions import InvalidFieldValue
from pymammotion.aliyun.model.dev_by_account_response import Device
from pymammotion.data.model.device import MowingDevice
from pymammotion.homeassistant import HomeAssistantMowerApi

from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .config import MammotionConfigStore
from .const import CONF_ACCOUNTNAME, DOMAIN, LOGGER

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

    async def async_refresh_login(self) -> None:
        """Refresh login credentials asynchronously."""
        await self.api.mammotion.refresh_login(self.account)
        self.store_cloud_credentials()

    def store_cloud_credentials(self) -> None:
        """Store cloud credentials in config entry."""
        if config_entry := self.config_entry:
            cache = self.api.mammotion.to_cache()
            if not cache:
                return
            self.hass.config_entries.async_update_entry(
                config_entry, data={**config_entry.data, **cache}
            )

    def is_online(self) -> bool:
        """Check if device is online."""
        return self.api.is_online(self.device_name)

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

    async def async_restore_data(self) -> None:
        """Restore saved data."""
        store = MammotionConfigStore(self.hass)
        restored_data: Mapping[str, Any] | None = await store.async_load()

        if restored_data is None:
            self.data = MowingDevice()
            if handle := self.api.mammotion.mower(self.device_name):
                handle.restore_device(self.data)
            return

        try:
            if mower_data := restored_data.get(self.device_name):
                mower_state = MowingDevice().from_dict(mower_data)
                if handle := self.api.mammotion.mower(self.device_name):
                    handle.restore_device(mower_state)
        except InvalidFieldValue:
            self.data = MowingDevice()
            if handle := self.api.mammotion.mower(self.device_name):
                handle.restore_device(self.data)

    async def async_save_data(self, data: MowingDevice) -> None:
        """Get map data from the device."""
        store = MammotionConfigStore(self.hass)
        current_store: dict[str, Any] = await store.async_load() or {}
        current_store[self.device_name] = data.to_dict()
        await store.async_save(current_store)

    @override
    async def _async_update_data(self) -> MowingDevice:
        """Get data from the device."""
        data = await self.api.update(self.device_name)
        if data is None:
            raise UpdateFailed(f"No data returned for {self.device_name}")
        await self.async_save_data(data)

        return data
