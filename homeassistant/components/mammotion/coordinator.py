"""Provides the mammotion DataUpdateCoordinator."""

from datetime import timedelta
from typing import TYPE_CHECKING, Any, cast, override

from mashumaro.exceptions import InvalidFieldValue
from pymammotion.aliyun.exceptions import DeviceOfflineException
from pymammotion.aliyun.model.dev_by_account_response import Device
from pymammotion.data.model.device import MowingDevice
from pymammotion.homeassistant import HomeAssistantMowerApi
from pymammotion.messaging.command_queue import Priority
from pymammotion.state.device_state import DeviceSnapshot
from pymammotion.transport import NoTransportAvailableError
from pymammotion.transport.base import AuthError, Subscription
from pymammotion.utility.constant.device_constant import WorkMode

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .config import MammotionConfigStore
from .const import DOMAIN, LOGGER
from .exceptions import CommandFailedError

if TYPE_CHECKING:
    from . import MammotionConfigEntry

MODE_WAIT_TIMEOUT = 30


class MammotionBaseUpdateCoordinator(DataUpdateCoordinator[MowingDevice]):
    """Mammotion DataUpdateCoordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: MammotionConfigEntry,
        device: Device,
        api: HomeAssistantMowerApi,
        update_interval: timedelta | None,
    ) -> None:
        """Initialize global mammotion data updater."""
        super().__init__(
            hass=hass,
            logger=LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
            config_entry=config_entry,
        )
        self.device: Device = device
        self.device_name = device.device_name
        self.api: HomeAssistantMowerApi = api

    def is_online(self) -> bool:
        """Check if device is online."""
        return self.api.is_online(self.device_name)

    async def async_send_command(self, command: str, **kwargs: Any) -> None:
        """Send a user command now; raise if it did not reach the mower."""
        try:
            await self.api.mammotion.send_command_with_args(
                self.device_name, command, priority=Priority.USER, **kwargs
            )
        except KeyError as err:
            raise CommandFailedError(f"{self.device_name} is not registered") from err

    async def async_wait_for_mode(self, *modes: WorkMode) -> WorkMode:
        """Return the first of the modes the mower reports."""
        try:
            device = await self.api.mammotion.wait_for(
                self.device_name,
                lambda device: (
                    isinstance(device, MowingDevice)
                    and device.report_data.dev.sys_status in modes
                ),
                timeout=MODE_WAIT_TIMEOUT,
            )
        except KeyError as err:
            raise CommandFailedError(f"{self.device_name} is not registered") from err
        return WorkMode(cast(MowingDevice, device).report_data.dev.sys_status)

    async def async_request_report(self) -> None:
        """Ask the mower for a fresh report in the background."""
        await self.api.mammotion.request_report_snapshot(self.device_name)


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
            # The library's own keep-alive asks for reports; they arrive by push.
            update_interval=None,
        )
        self.store = store
        self._state_subscription: Subscription | None = None

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
    async def _async_setup(self) -> None:
        """Subscribe to the state the mower pushes."""
        if (handle := self.api.mammotion.mower(self.device_name)) is None:
            raise UpdateFailed(f"{self.device_name} is not registered")
        self._state_subscription = handle.subscribe_state_changed(
            self._async_handle_state_changed
        )

    async def _async_handle_state_changed(self, snapshot: DeviceSnapshot) -> None:
        """Push the mower's new state to the entities."""
        data = cast(MowingDevice, snapshot.raw)
        self.store.async_update_mower_data(self.device_name, data)
        self.async_set_updated_data(data)

    @override
    async def async_shutdown(self) -> None:
        """Stop listening to the mower."""
        if self._state_subscription is not None:
            self._state_subscription.cancel()
            self._state_subscription = None
        await super().async_shutdown()

    @override
    async def _async_update_data(self) -> MowingDevice:
        """Get data from the device."""
        try:
            data = await self.api.update(self.device_name)
        except (DeviceOfflineException, NoTransportAvailableError) as err:
            LOGGER.debug("Keeping last state of %s: %s", self.device_name, err)
            return self.data
        except AuthError as err:
            raise ConfigEntryAuthFailed(err) from err

        if data is None:
            raise UpdateFailed(f"No data returned for {self.device_name}")
        self.store.async_update_mower_data(self.device_name, data)

        return data
