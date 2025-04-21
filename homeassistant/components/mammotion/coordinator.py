"""Provides the mammotion DataUpdateCoordinator."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import TYPE_CHECKING, Any

import betterproto
from mashumaro.exceptions import InvalidFieldValue
from pymammotion.aliyun.cloud_gateway import (
    DeviceOfflineException,
    GatewayTimeoutException,
    NoConnectionException,
)
from pymammotion.aliyun.model.dev_by_account_response import Device
from pymammotion.data.model import GenerateRouteInformation, HashList
from pymammotion.data.model.device import MowerInfo, MowingDevice
from pymammotion.data.model.device_config import OperationSettings, create_path_order
from pymammotion.data.model.report_info import Maintain
from pymammotion.mammotion.devices.mammotion import (
    ConnectionPreference,
    Mammotion,
    MammotionMixedDeviceManager,
)
from pymammotion.proto import RptAct, RptInfoType
from pymammotion.utility.constant import WorkMode
from pymammotion.utility.device_type import DeviceType

from homeassistant.components import bluetooth
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

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
    NO_REQUEST_MODES,
)

if TYPE_CHECKING:
    from . import MammotionConfigEntry


MAINTENANCE_INTERVAL = timedelta(minutes=60)
DEFAULT_INTERVAL = timedelta(minutes=1)
WORKING_INTERVAL = timedelta(seconds=5)
REPORT_INTERVAL = timedelta(minutes=1)
DEVICE_VERSION_INTERVAL = timedelta(days=1)
MAP_INTERVAL = timedelta(minutes=30)


class MammotionBaseUpdateCoordinator[_DataT](DataUpdateCoordinator[_DataT]):
    """Mammotion DataUpdateCoordinator."""

    manager: Mammotion | None = None
    device: Device | None = None

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

    async def set_scheduled_updates(self, enabled: bool) -> None:
        """Set scheduled updates."""
        device = self.manager.get_device_by_name(self.device_name)
        device.mower_state.enabled = enabled
        if device.mower_state.enabled:
            self.update_failures = 0
            if not device.mower_state.online:
                device.mower_state.online = True
            if device.has_cloud() and device.cloud().stopped:
                await device.cloud().start()
        else:
            if device.has_cloud():
                await device.cloud().stop()
                device.cloud().mqtt.disconnect()
            if device.has_ble():
                await device.ble().stop()

    async def async_refresh_login(self) -> None:
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
        await self.manager.refresh_login(account, password)
        self.store_cloud_credentials()

    async def device_offline(self, device: MammotionMixedDeviceManager) -> None:
        """Device is offline."""
        device.mower_state.online = False
        if device.has_cloud():
            await device.cloud().stop()

        loop = asyncio.get_running_loop()
        loop.call_later(900, lambda: asyncio.create_task(self.clear_update_failures()))

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

    async def async_send_command(self, command: str, **kwargs: Any) -> bool | None:
        """Send command."""
        if not self.manager.get_device_by_name(self.device_name).mower_state.online:
            return False

        device = self.manager.get_device_by_name(self.device_name)

        try:
            await self.manager.send_command_with_args(
                self.device_name, command, **kwargs
            )
            self.update_failures = 0
            return True
        except EXPIRED_CREDENTIAL_EXCEPTIONS:
            self.update_failures += 1
            await self.async_refresh_login()
            if self.update_failures < 5:
                await self.async_send_command(command, **kwargs)
            return False
        except GatewayTimeoutException as ex:
            LOGGER.error(f"Gateway timeout exception: {ex.iot_id}")
            self.update_failures = 0
            return False
        except (DeviceOfflineException, NoConnectionException) as ex:
            """Device is offline try bluetooth if we have it."""
            try:
                if device.has_ble():
                    # if we don't do this it will stay connected and no longer update over wifi
                    device.ble().set_disconnect_strategy(True)
                    await (
                        self.manager.get_device_by_name(self.device_name)
                        .ble()
                        .queue_command(command, **kwargs)
                    )
                    return True
                raise DeviceOfflineException(ex.args[0], self.device.iotId)
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

        new_swversion = mower.device_firmwares.device_version

        if new_swversion is not None or new_swversion != device_entry.sw_version:
            device_registry.async_update_device(
                device_entry.id, sw_version=new_swversion
            )

        if model_id := mower.mower_state.model_id:
            if model_id is not None or model_id != device_entry.model_id:
                device_registry.async_update_device(device_entry.id, model_id=model_id)

    async def async_sync_maps(self) -> None:
        """Get map data from the device."""
        try:
            await self.manager.start_map_sync(self.device_name)
        except EXPIRED_CREDENTIAL_EXCEPTIONS:
            self.update_failures += 1
            await self.async_refresh_login()
            if self.update_failures < 5:
                await self.async_sync_maps()

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

    async def set_traversal_mode(self, context: int) -> None:
        """Set traversal mode."""
        await self.async_send_command("traverse_mode", context=context)

    async def set_turning_mode(self, context: int) -> None:
        """Set turning mode."""
        await self.async_send_command("turning_mode", context=context)

    async def async_blade_height(self, height: int) -> int:
        """Set blade height."""
        await self.async_send_command("set_blade_height", height=height)
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
        await self.async_send_command("allpowerfull_rw", rw_id=5, rw=1, context=1)

    async def async_get_area_list(self) -> None:
        """Mowing area List."""
        await self.async_send_command("get_area_name_list", device_id=self.device.iotId)

    async def send_command_and_update(self, command_str: str, **kwargs: Any) -> None:
        """Send command and update."""
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
                RptInfoType.RIT_VIO,
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
            toward=operation_settings.toward,  # is just angle (route angle)
            toward_included_angle=operation_settings.toward_included_angle  # demond_angle
            if operation_settings.channel_mode == 1
            else 0,  # crossing angle relative to grid
            toward_mode=operation_settings.toward_mode,
            blade_height=operation_settings.blade_height,
            channel_mode=operation_settings.channel_mode,  # single, double, segment or none (route mode)
            channel_width=operation_settings.channel_width,  # path space
            job_mode=operation_settings.job_mode,  # taskMode grid or border first
            edge_mode=operation_settings.mowing_laps,  # perimeter/mowing laps
            path_order=create_path_order(operation_settings, self.device_name),
            obstacle_laps=operation_settings.obstacle_laps,
        )

        if DeviceType.is_luba1(self.device_name):
            route_information.toward_mode = 0
            route_information.toward_included_angle = 0

        # not sure if this is artificial limit
        # if (
        #     DeviceType.is_mini_or_x_series(self.device_name)
        #     and route_information.toward_mode == 0
        # ):
        #     route_information.toward = 0

        return await self.async_send_command(
            "generate_route_information", generate_route_information=route_information
        )

    async def clear_all_maps(self) -> None:
        """Clear all map data stored."""
        data = self.manager.get_device_by_name(self.device_name).mower_state
        data.map = HashList()

    async def clear_update_failures(self) -> None:
        """Clear update failures."""
        self.update_failures = 0
        device = self.manager.get_device_by_name(self.device_name)
        if not device.mower_state.online:
            device.mower_state.online = True
        if device.has_cloud() and device.cloud().stopped:
            await device.cloud().start()

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
        await store.async_save(data.to_dict())

    async def _async_update_data(self) -> _DataT | None:
        device = self.manager.get_device_by_name(self.device_name)

        if not device.mower_state.enabled or not device.mower_state.online:
            return self.data

        # don't query the mower while users are doing map changes or its updating.
        if device.mower_state.report_data.dev.sys_status in NO_REQUEST_MODES:
            return self.data

        if self.update_failures > 5 and device.preference is ConnectionPreference.WIFI:
            """Don't hammer the mammotion/ali servers"""
            loop = asyncio.get_running_loop()
            loop.call_later(
                60, lambda: asyncio.create_task(self.clear_update_failures())
            )

            return self.data

        if device.has_ble() and device.preference is ConnectionPreference.BLUETOOTH:
            if ble_device := bluetooth.async_ble_device_from_address(
                self.hass, device.ble().get_address(), True
            ):
                device.ble().update_device(ble_device)
        return None

    async def find_entity_by_attribute_in_registry(
        self, attribute_name, attribute_value
    ):
        """Find an entity using the entity registry based on attributes."""
        entity_registry = await self.hass.helpers.entity_registry.async_get_registry()

        for entity_id, entity_entry in entity_registry.entities.items():
            entity_state = self.hass.states.get(entity_id)
            if (
                entity_state
                and entity_state.attributes.get(attribute_name) == attribute_value
            ):
                return entity_id, entity_entry

        return None, None

    def get_area_entity_name(self, area_hash: int) -> str:
        """Get string name of area hash."""
        try:
            area = next(
                item for item in self.data.map.area_name if item.hash == area_hash
            )
            if area.name != "":
                return area.name
            return f"area {area_hash}"
        except StopIteration:
            return None


class MammotionReportUpdateCoordinator(MammotionBaseUpdateCoordinator[MowingDevice]):
    """Mammotion report update coordinator."""

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

    async def _async_update_data(self) -> MowingDevice:
        """Get data from the device."""
        if data := await super()._async_update_data():
            return data

        device = self.manager.get_device_by_name(self.device_name)

        try:
            await self.async_send_command("get_report_cfg")

        except DeviceOfflineException as ex:
            """Device is offline try bluetooth if we have it."""
            if ex.iot_id == self.device.iotId:
                device = self.manager.get_device_by_name(self.device_name)
                await self.device_offline(device)
                return device.mower_state

        LOGGER.debug("Updated Mammotion device %s", self.device_name)
        LOGGER.debug("================= Debug Log =================")
        if device.preference is ConnectionPreference.BLUETOOTH:
            LOGGER.debug(
                "Mammotion device data: %s",
                self.manager.get_device_by_name(self.device_name).ble()._raw_data,
            )
        if device.preference is ConnectionPreference.WIFI:
            LOGGER.debug(
                "Mammotion device data: %s",
                self.manager.get_device_by_name(self.device_name).cloud()._raw_data,
            )
        LOGGER.debug("==================================")

        self.update_failures = 0
        data = self.manager.get_device_by_name(self.device_name).mower_state
        await self.async_save_data(data)

        if data.report_data.dev.sys_status is WorkMode.MODE_WORKING:
            self.update_interval = WORKING_INTERVAL
        else:
            self.update_interval = DEFAULT_INTERVAL

        return data

    async def _async_update_notification(self, res: tuple[str, Any | None]) -> None:
        """Update data from incoming messages."""
        if res[0] == "sys" and res[1] is not None:
            sys_msg = betterproto.which_one_of(res[1], "SubSysMsg")
            if sys_msg[0] == "toapp_report_data":
                mower = self.manager.mower(self.device_name)
                self.async_set_updated_data(mower)

    async def _async_setup(self) -> None:
        """Set up Mammotion report coordinator."""
        device = self.manager.get_device_by_name(self.device_name)

        if self.data is None:
            self.data = device.mower_state

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
            update_interval=MAINTENANCE_INTERVAL,
        )

    async def _async_update_data(self) -> Maintain:
        """Get data from the device."""
        if data := await super()._async_update_data():
            return data

        try:
            await self.async_send_command("get_maintenance")

        except DeviceOfflineException as ex:
            """Device is offline try bluetooth if we have it."""
            if ex.iot_id == self.device.iotId:
                device = self.manager.get_device_by_name(self.device_name)
                await self.device_offline(device)
                return device.mower_state.report_data.maintenance
        except GatewayTimeoutException:
            """Gateway is timing out again."""

        return self.manager.get_device_by_name(
            self.device.deviceName
        ).mower_state.report_data.maintenance

    async def _async_setup(self) -> None:
        """Set up Mammotion maintenance coordinator."""
        device = self.manager.get_device_by_name(self.device_name)
        if self.data is None:
            self.data = device.mower_state.report_data.maintenance


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
            update_interval=DEFAULT_INTERVAL,
        )

    async def _async_update_data(self):
        """Get data from the device."""
        if data := await super()._async_update_data():
            return data
        command_list = [
            "get_device_version_main",
            "get_device_version_info",
            "get_device_base_info",
            "get_device_product_model",
        ]
        for command in command_list:
            try:
                await self.async_send_command(command)

            except DeviceOfflineException as ex:
                """Device is offline bluetooth has been attempted."""
                if ex.iot_id == self.device.iotId:
                    device = self.manager.get_device_by_name(self.device_name)
                    await self.device_offline(device)
                    return device.mower_state.mower_state
            except GatewayTimeoutException:
                """Gateway is timing out again."""

        data = self.manager.get_device_by_name(self.device_name).mower_state.mower_state
        await self.check_firmware_version()

        if data.model_id:
            self.update_interval = DEVICE_VERSION_INTERVAL

        return data

    async def _async_setup(self) -> None:
        device = self.manager.get_device_by_name(self.device_name)
        if self.data is None:
            self.data = device.mower_state.mower_state

        try:
            await self.async_send_command("get_device_product_model")
        except DeviceOfflineException:
            """Device is offline bluetooth has been attempted."""


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
        if data := await super()._async_update_data():
            return data
        device = self.manager.get_device_by_name(self.device_name)

        try:
            if (
                len(device.mower_state.map.hashlist) == 0
                or len(device.mower_state.map.missing_hashlist()) > 0
            ):
                await self.manager.start_map_sync(self.device_name)

        except DeviceOfflineException as ex:
            """Device is offline try bluetooth if we have it."""
            if ex.iot_id == self.device.iotId:
                await self.device_offline(device)
                return device.mower_state.mower_state
        except GatewayTimeoutException:
            """Gateway is timing out again."""

        return self.manager.get_device_by_name(self.device_name).mower_state.mower_state

    async def _async_setup(self) -> None:
        """Set up coordinator with initial call to get map data."""
        device = self.manager.get_device_by_name(self.device_name)
        if self.data is None:
            self.data = device.mower_state.mower_state

        if not device.mower_state.enabled or not device.mower_state.online:
            return
        try:
            await self.async_rtk_dock_location()
            if not DeviceType.is_luba1(self.device_name):
                await self.async_get_area_list()
        except DeviceOfflineException as ex:
            """Device is offline try bluetooth if we have it."""
            if ex.iot_id == self.device.iotId:
                await self.device_offline(device)
        except GatewayTimeoutException:
            """Gateway is timing out again."""
