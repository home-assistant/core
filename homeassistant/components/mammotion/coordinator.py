"""Provides the mammotion DataUpdateCoordinator."""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import timedelta
from typing import TYPE_CHECKING, Any

import betterproto
from pymammotion.aliyun.cloud_gateway import (
    DeviceOfflineException,
    GatewayTimeoutException,
)
from pymammotion.aliyun.model.dev_by_account_response import Device
from pymammotion.data.model import GenerateRouteInformation, HashList
from pymammotion.data.model.device import MowerInfo, MowingDevice
from pymammotion.data.model.device_config import OperationSettings, create_path_order
from pymammotion.data.model.report_info import Maintain
from pymammotion.mammotion.devices.mammotion import ConnectionPreference, Mammotion
from pymammotion.proto.mctrl_sys import RptAct, RptInfoType
from pymammotion.utility.constant import WorkMode
from pymammotion.utility.device_type import DeviceType

from homeassistant.components import bluetooth
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from ...helpers.storage import Store
from .const import (
    COMMAND_EXCEPTIONS,
    CONF_ACCOUNTNAME,
    CONF_AEP_DATA,
    CONF_AUTH_DATA,
    CONF_CONNECT_DATA,
    CONF_DEVICE_DATA,
    CONF_MAMMOTION_DATA,
    CONF_REGION_DATA,
    CONF_SESSION_DATA,
    DOMAIN,
    EXPIRED_CREDENTIAL_EXCEPTIONS,
    LOGGER,
)

if TYPE_CHECKING:
    from . import MammotionConfigEntry


MAINTENENCE_INTERVAL = timedelta(minutes=60)
DEFAULT_INTERVAL = timedelta(minutes=1)
WORKING_INTERVAL = timedelta(seconds=5)
REPORT_INTERVAL = timedelta(minutes=1)
DEVICE_VERSION_INTERVAL = timedelta(days=1)
MAP_INTERVAL = timedelta(minutes=30)


class MammotionBaseUpdateCoordinator[_DataT](DataUpdateCoordinator[_DataT]):
    """Mammotion DataUpdateCoordinator."""

    manager: Mammotion = None
    device: Device | None = None
    updated_once: bool

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: MammotionConfigEntry,
        device: Device,
        mammotion: Mammotion,
        update_interval: timedelta,
    ) -> None:
        """Initialize global mammotion data updater."""
        super().__init__(
            hass=hass,
            logger=LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )
        assert config_entry.unique_id
        self.config_entry = config_entry
        self.device = device
        self.device_name = device.deviceName
        self.manager = mammotion
        self._operation_settings = OperationSettings()
        self.update_failures = 0
        self.enabled = True
        self.updated_once = False

    async def set_scheduled_updates(self, enabled: bool) -> None:
        self.enabled = enabled
        device = self.manager.get_device_by_name(self.device_name)
        if self.enabled:
            if device.has_cloud():
                await device.cloud().start()
        else:
            if device.has_cloud():
                await device.cloud().stop()
                device.cloud().mqtt.disconnect()
            if device.has_ble():
                await device.ble().stop()

    async def async_login(self) -> None:
        """Login to cloud servers."""
        if (
            self.manager.get_device_by_name(self.device_name)
            and self.manager.get_device_by_name(self.device_name).has_cloud()
        ):
            await self.hass.async_add_executor_job(
                self.manager.get_device_by_name(self.device_name)
                .cloud()
                .mqtt.disconnect
            )

        account = self.config_entry.data.get(CONF_ACCOUNTNAME)
        password = self.config_entry.data.get(CONF_PASSWORD)
        await self.manager.login_and_initiate_cloud(account, password, True)
        self.store_cloud_credentials()

    def store_cloud_credentials(self) -> None:
        """Store cloud credentials in config entry."""
        # config_updates = {}
        mammotion_cloud = self.manager.mqtt_list.get(
            self.config_entry.data.get(CONF_ACCOUNTNAME, "")
        )
        cloud_client = mammotion_cloud.cloud_client if mammotion_cloud else None

        if cloud_client is not None:
            config_updates = {
                **self.config_entry.data,
                CONF_CONNECT_DATA: cloud_client.connect_response,
                CONF_AUTH_DATA: cloud_client.login_by_oauth_response,
                CONF_REGION_DATA: cloud_client.region_response,
                CONF_AEP_DATA: cloud_client.aep_response,
                CONF_SESSION_DATA: cloud_client.session_by_authcode_response,
                CONF_DEVICE_DATA: cloud_client.devices_by_account_response,
                CONF_MAMMOTION_DATA: cloud_client.mammotion_http.response,
            }
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=config_updates
            )

    async def async_send_command(self, command: str, **kwargs: Any) -> bool:
        """Send command."""
        if not self.manager.get_device_by_name(self.device_name).mower_state.online:
            return False

        try:
            await self.manager.send_command_with_args(
                self.device.deviceName, command, **kwargs
            )
            self.update_failures = 0
            return True
        except EXPIRED_CREDENTIAL_EXCEPTIONS:
            self.update_failures += 1
            await self.async_login()
            return False
        except GatewayTimeoutException as exc:
            self.update_failures += 1
            if self.update_failures > 5:
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="command_failed"
                ) from exc
            await self.async_send_command(command, **kwargs)
        except DeviceOfflineException:
            """Device is offline try bluetooth if we have it."""
            try:
                if device := self.manager.get_device_by_name(self.device_name):
                    if device.has_ble():
                        # if we don't do this it will stay connected and no longer update over wifi
                        device.ble().set_disconnect_strategy(True)
                        await (
                            self.manager.get_device_by_name(self.device_name)
                            .ble()
                            .queue_command(command, **kwargs)
                        )
                        return True
                    raise DeviceOfflineException()
            except COMMAND_EXCEPTIONS as exc:
                raise HomeAssistantError(
                    translation_domain=DOMAIN, translation_key="command_failed"
                ) from exc

    async def check_firmware_version(self) -> None:
        """Check if firmware version is updated."""
        mower = self.manager.mower(self.device_name)
        device_registry = dr.async_get(self.hass)
        device_entry = device_registry.async_get_device(
            identifiers={(DOMAIN, self.device_name)}
        )
        if device_entry is None:
            return

        new_swversion = mower.mower_state.swversion

        if new_swversion is not None or new_swversion != device_entry.sw_version:
            device_registry.async_update_device(
                device_entry.id, sw_version=new_swversion
            )

        if model_id := mower.mower_state.model_id:
            if model_id is not None or model_id != device_entry.model_id:
                device_registry.async_update_device(device_entry.id, model_id=model_id)

    # async def async_setup(self) -> None:
    #     """Set coordinator up."""
    #
    #     preference = (
    #         ConnectionPreference.WIFI
    #         if self.config_entry.data.get(CONF_USE_WIFI, False)
    #         else ConnectionPreference.BLUETOOTH
    #     )
    #     address = self.config_entry.data.get(CONF_ADDRESS)
    #     stay_connected_ble = self.config_entry.options.get(
    #         CONF_STAY_CONNECTED_BLUETOOTH, False
    #     )
    #
    #
    #
    #             # address previous bugs
    #     if address is None and preference == ConnectionPreference.BLUETOOTH:
    #         preference = ConnectionPreference.WIFI
    #
    #     if address:
    #         ble_device = bluetooth.async_ble_device_from_address(self.hass, address)
    #         if not ble_device and credentials is None:
    #             raise ConfigEntryNotReady(
    #                 f"Could not find Mammotion lawn mower with address {address}"
    #             )
    #         if ble_device is not None:
    #             self.device_name = ble_device.name or "Unknown"
    #             self.manager.add_ble_device(ble_device, preference)
    #
    #
    #     if ble_device and device:
    #         device.ble().set_disconnect_strategy(not stay_connected_ble)
    #
    #     # await self.async_restore_data()
    #
    #     try:
    #         if preference is ConnectionPreference.WIFI and device.has_cloud():
    #             self.store_cloud_credentials()
    #             if mqtt_client := self.manager.mqtt_list.get(account):
    #                 device.mower_state.error_codes = await mqtt_client.cloud_client.mammotion_http.get_all_error_codes()
    #             device.cloud().set_notification_callback(
    #                 self._async_update_notification
    #             )
    #             await device.cloud().start_sync(0)
    #         elif device.has_ble():
    #             device.ble().set_notification_callback(self._async_update_notification)
    #             await device.ble().start_sync(0)
    #         else:
    #             raise ConfigEntryNotReady(
    #                 "No configuration available to setup Mammotion lawn mower"
    #             )
    #
    #     except COMMAND_EXCEPTIONS as exc:
    #         raise ConfigEntryNotReady("Unable to setup Mammotion device") from exc

    async def async_sync_maps(self) -> None:
        """Get map data from the device."""
        await self.manager.start_map_sync(self.device_name)

    async def async_start_stop_blades(self, start_stop: bool) -> None:
        """Start stop blades."""
        if DeviceType.is_luba1(self.device_name):
            if start_stop:
                await self.async_send_command("set_blade_control", on_off=1)
            else:
                await self.async_send_command("set_blade_control", on_off=0)
        elif start_stop:
            await self.async_send_command(
                "operate_on_device",
                main_ctrl=1,
                cut_knife_ctrl=1,
                cut_knife_height=60,
                max_run_speed=1.2,
            )
        else:
            await self.async_send_command(
                "operate_on_device",
                main_ctrl=0,
                cut_knife_ctrl=0,
                cut_knife_height=60,
                max_run_speed=1.2,
            )

    async def async_set_sidelight(self, on_off: int) -> None:
        """Set Sidelight."""
        await self.async_send_command(
            "read_and_set_sidelight", is_sidelight=bool(on_off), operate=0
        )

    async def async_read_sidelight(self) -> None:
        """Set Sidelight."""
        await self.async_send_command(
            "read_and_set_sidelight", is_sidelight=False, operate=1
        )

    async def set_traversal_mode(self, id: int) -> None:
        """Set traversal mode."""
        await self.async_send_command("traverse_mode", id=id)

    async def async_blade_height(self, height: int) -> int:
        """Set blade height."""
        await self.send_command_and_update("set_blade_height", height=float(height))
        return height

    async def async_leave_dock(self) -> None:
        """Leave dock."""
        await self.send_command_and_update("leave_dock")

    async def async_cancel_task(self) -> None:
        """Cancel task."""
        await self.send_command_and_update("cancel_job")

    async def async_move_forward(self, speed: float) -> None:
        """Move forward."""
        await self.send_command_and_update("move_forward", linear=speed)

    async def async_move_left(self, speed: float) -> None:
        """Move left."""
        await self.send_command_and_update("move_left", angular=speed)

    async def async_move_right(self, speed: float) -> None:
        """Move right."""
        await self.send_command_and_update("move_right", angular=speed)

    async def async_move_back(self, speed: float) -> None:
        """Move back."""
        await self.send_command_and_update("move_back", linear=speed)

    async def async_rtk_dock_location(self) -> None:
        """RTK and dock location."""
        await self.async_send_command("allpowerfull_rw", id=5, rw=1, context=1)

    async def send_command_and_update(self, command_str: str, **kwargs: Any) -> None:
        await self.async_send_command(command_str, **kwargs)
        await self.async_request_iot_sync()

    async def async_request_iot_sync(self, stop: bool = False) -> None:
        """Sync specific info from device."""
        await self.async_send_command(
            "request_iot_sys",
            rpt_act=RptAct.RPT_STOP if stop else RptAct.RPT_START,
            rpt_info_type=[
                RptInfoType.RIT_DEV_STA,
                RptInfoType.RIT_DEV_LOCAL,
                RptInfoType.RIT_WORK,
                RptInfoType.RIT_MAINTAIN,
                RptInfoType.RIT_BASESTATION_INFO,
                RptInfoType.RIT_FW_INFO,
            ],
            timeout=10000,
            period=3000,
            no_change_period=4000,
            count=0,
        )

    async def async_plan_route(self, operation_settings: OperationSettings) -> bool:
        """Plan mow."""

        if self.data.report_data.dev:
            dev = self.data.report_data.dev
            if dev.collector_status.collector_installation_status == 0:
                operation_settings.is_dump = False

        if DeviceType.is_yuka(self.device_name):
            operation_settings.blade_height = -10

        route_information = GenerateRouteInformation(
            one_hashs=operation_settings.areas,
            rain_tactics=operation_settings.rain_tactics,
            speed=operation_settings.speed,
            ultra_wave=operation_settings.ultra_wave,  # touch no touch etc
            toward=operation_settings.toward,  # is just angle
            toward_included_angle=operation_settings.toward_included_angle
            if operation_settings.channel_mode == 1
            else 0,  # crossing angle relative to grid
            toward_mode=operation_settings.toward_mode,
            blade_height=operation_settings.blade_height,
            channel_mode=operation_settings.channel_mode,  # single, double, segment or none
            channel_width=operation_settings.channel_width,
            job_mode=operation_settings.job_mode,  # taskMode grid or border first
            edge_mode=operation_settings.mowing_laps,  # perimeter laps
            path_order=create_path_order(operation_settings, self.device_name),
            obstacle_laps=operation_settings.obstacle_laps,
        )

        if DeviceType.is_luba1(self.device_name):
            route_information.toward_mode = 0
            route_information.toward_included_angle = 0

        return await self.async_send_command(
            "generate_route_information", generate_route_information=route_information
        )

    async def clear_all_maps(self) -> None:
        """Clear all map data stored."""
        data = self.manager.get_device_by_name(self.device_name).mower_state
        data.map = HashList()

    def clear_update_failures(self) -> None:
        self.update_failures = 0

    @property
    def operation_settings(self) -> OperationSettings:
        """Return operation settings for planning."""
        return self._operation_settings

    async def async_restore_data(self) -> None:
        """Restore saved data."""
        store = Store(self.hass, version=1, key=self.device_name)
        restored_data = await store.async_load()
        try:
            if restored_data:
                mower_state = MowingDevice().from_dict(restored_data)
                self.manager.get_device_by_name(
                    self.device_name
                ).mower_state = mower_state
        except InvalidFieldValue:
            """invalid"""
            self.data = MowingDevice()
            self.manager.get_device_by_name(self.device_name).mower_state = self.data

    async def async_save_data(self, data: MowingDevice) -> None:
        """Get map data from the device."""
        store = Store(self.hass, version=1, key=self.device_name)
        stored_data = asdict(data)
        await store.async_save(stored_data)

    async def _async_update_data(self):
        device = self.manager.get_device_by_name(self.device_name)

        if not self.enabled or not device.mower_state.online:
            return self.data

        if self.update_failures > 3 and device.preference is ConnectionPreference.WIFI:
            """Don't hammer the mammotion/ali servers"""
            loop = asyncio.get_running_loop()
            loop.call_later(600, self.clear_update_failures)

            return self.data


class MammotionReportUpdateCoordinator(MammotionBaseUpdateCoordinator[MowingDevice]):
    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: MammotionConfigEntry,
        device: Device,
        mammotion: Mammotion,
    ) -> None:
        """Initialize global mammotion data updater."""
        super().__init__(
            hass=hass,
            config_entry=config_entry,
            device=device,
            mammotion=mammotion,
            update_interval=REPORT_INTERVAL,
        )

    def clear_update_failures(self) -> None:
        self.update_failures = 0

    async def _async_update_data(self) -> MowingDevice:
        """Get data from the device."""
        await super()._async_update_data()

        device = self.manager.get_device_by_name(self.device_name)

        if device.has_ble() and device.preference is ConnectionPreference.BLUETOOTH:
            if ble_device := bluetooth.async_ble_device_from_address(
                self.hass, device.ble().get_address(), True
            ):
                device.ble().update_device(ble_device)
        try:
            await self.async_send_command("get_report_cfg")

        except DeviceOfflineException:
            """Device is offline try bluetooth if we have it."""
            device = self.manager.get_device_by_name(self.device_name)
            device.mower_state.online = False
            data = device.mower_state
            return data

        LOGGER.debug("Updated Mammotion device %s", self.device_name)
        LOGGER.debug("================= Debug Log =================")
        LOGGER.debug(
            "Mammotion device data: %s",
            asdict(self.manager.get_device_by_name(self.device_name).mower_state),
        )
        LOGGER.debug("==================================")

        self.update_failures = 0
        data = self.manager.get_device_by_name(self.device_name).mower_state
        await self.async_save_data(data)

        if data.report_data.dev.sys_status is WorkMode.MODE_WORKING:
            self.update_interval = WORKING_INTERVAL
        else:
            self.update_interval = DEFAULT_INTERVAL

        self.updated_once = True

        return data

    async def _async_update_notification(self, res: tuple[str, Any | None]) -> None:
        """Update data from incoming messages."""
        if res[0] == "sys" and res[1] is not None:
            sys_msg = betterproto.which_one_of(res[1], "SubSysMsg")
            if sys_msg[0] == "toapp_report_data":
                mower = self.manager.mower(self.device_name)
                self.async_set_updated_data(mower)

    async def _async_setup(self) -> None:
        device = self.manager.get_device_by_name(self.device_name)

        if device.has_cloud():
            device.cloud().set_notification_callback(self._async_update_notification)
        elif device.has_ble():
            device.ble().set_notification_callback(self._async_update_notification)


class MammotionMaintenanceUpdateCoordinator(MammotionBaseUpdateCoordinator[Maintain]):
    """Class to manage fetching mammotion data."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: MammotionConfigEntry,
        device: Device,
        mammotion: Mammotion,
    ) -> None:
        """Initialize global mammotion data updater."""
        super().__init__(
            hass=hass,
            config_entry=config_entry,
            device=device,
            mammotion=mammotion,
            update_interval=MAINTENENCE_INTERVAL,
        )

    async def _async_update_data(self) -> Maintain:
        """Get data from the device."""
        await super()._async_update_data()

        try:
            await self.async_send_command("get_maintenance")

        except DeviceOfflineException:
            """Device is offline try bluetooth if we have it."""
            device = self.manager.get_device_by_name(self.device_name)
            device.mower_state.online = False
            data = device.mower_state
            return data

        self.updated_once = True

        return self.manager.get_device_by_name(
            self.device.deviceName
        ).mower_state.report_data.maintenance


class MammotionDeviceVersionUpdateCoordinator(
    MammotionBaseUpdateCoordinator[MowerInfo]
):
    """Class to manage fetching mammotion data."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: MammotionConfigEntry,
        device: Device,
        mammotion: Mammotion,
    ) -> None:
        """Initialize global mammotion data updater."""
        super().__init__(
            hass=hass,
            config_entry=config_entry,
            device=device,
            mammotion=mammotion,
            update_interval=DEVICE_VERSION_INTERVAL,
        )

    async def _async_update_data(self):
        """Get data from the device."""
        await super()._async_update_data()

        try:
            await self.async_send_command("get_device_version_main")
            await self.async_send_command("get_device_version_info")

            await self.check_firmware_version()
        except DeviceOfflineException:
            """Device is offline try bluetooth if we have it."""
            device = self.manager.get_device_by_name(self.device_name)
            device.mower_state.online = False
            data = device.mower_state.mower_state
            return data

        data = self.manager.get_device_by_name(self.device_name).mower_state.mower_state
        self.updated_once = True

        return data


class MammotionMapUpdateCoordinator(MammotionBaseUpdateCoordinator[MowerInfo]):
    """Class to manage fetching mammotion data."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: MammotionConfigEntry,
        device: Device,
        mammotion: Mammotion,
    ) -> None:
        """Initialize global mammotion data updater."""
        super().__init__(
            hass=hass,
            config_entry=config_entry,
            device=device,
            mammotion=mammotion,
            update_interval=MAP_INTERVAL,
        )

    def _map_callback(self) -> None:
        """Trigger a resync when the bol hash changes."""
        # TODO setup callback to get bol hash data

    async def _async_update_data(self):
        """Get data from the device."""
        await super()._async_update_data()
        device = self.manager.get_device_by_name(self.device_name)

        try:
            if (
                len(device.mower_state.map.hashlist) == 0
                or len(device.mower_state.map.missing_hashlist) > 0
            ):
                await self.manager.start_map_sync(self.device_name)

        except DeviceOfflineException:
            """Device is offline try bluetooth if we have it."""
            device.mower_state.online = False
            data = device.mower_state.mower_state
            return data

        data = self.manager.get_device_by_name(self.device_name).mower_state.mower_state
        self.updated_once = True

        return data

    async def _async_setup(self) -> None:
        """Setup coordinator with initial calls to get map data."""
        device = self.manager.get_device_by_name(self.device_name)

        if not self.enabled or not device.mower_state.online:
            return
        try:
            await self.async_rtk_dock_location()
        except DeviceOfflineException:
            """Device is offline try bluetooth if we have it."""
            device.mower_state.online = False
