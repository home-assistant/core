"""Provides the mammotion DataUpdateCoordinator."""

from datetime import timedelta
from typing import TYPE_CHECKING, Any, override

from mashumaro.exceptions import InvalidFieldValue
from pymammotion.aliyun.exceptions import DeviceOfflineException
from pymammotion.aliyun.model.dev_by_account_response import Device
from pymammotion.data.model.device import MowingDevice
from pymammotion.homeassistant import HomeAssistantMowerApi
from pymammotion.transport import NoTransportAvailableError
from pymammotion.transport.base import AuthError

from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .config import MammotionConfigStore
from .const import CONF_ACCOUNTNAME, DOMAIN, LOGGER
from .exceptions import CommandFailedError

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

    async def async_send_command(self, command: str, **kwargs: Any) -> None:
        """Send command via api."""
        if not await self.api.async_send_command(self.device_name, command, **kwargs):
            raise CommandFailedError(f"Command {command} failed for {self.device_name}")


class MammotionMowerUpdateCoordinator(MammotionBaseUpdateCoordinator):
    """Class to manage fetching mammotion report data."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: MammotionConfigEntry,
        device: Device,
        api: HomeAssistantMowerApi,
        store: MammotionConfigStore,
    ) -> None:
        """Initialize mammotion data updater."""
        super().__init__(
            hass=hass,
            config_entry=config_entry,
            device=device,
            api=api,
            update_interval=DEFAULT_INTERVAL,
        )
        self.store = store

    @callback
    def restore_data(self) -> None:
        """Restore saved data."""
        mower_state = MowingDevice()
        if mower_data := self.store.mower_data.get(self.device_name):
            try:
                mower_state = MowingDevice().from_dict(mower_data)
            except InvalidFieldValue:
                mower_state = MowingDevice()

        self.data = mower_state
        if handle := self.api.mammotion.mower(self.device_name):
            handle.restore_device(mower_state)

    @override
    async def _async_update_data(self) -> MowingDevice:
        """Get data from the device."""
        try:
            data = await self.api.update(self.device_name)
        except DeviceOfflineException, NoTransportAvailableError:
            return self.data
        except AuthError as err:
            raise ConfigEntryAuthFailed(err) from err

        if data is None:
            raise UpdateFailed(f"No data returned for {self.device_name}")
        self.store.async_update_mower_data(self.device_name, data.to_dict())

        return data
