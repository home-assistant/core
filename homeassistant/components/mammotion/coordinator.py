"""Provides the mammotion DataUpdateCoordinator."""

from __future__ import annotations

from abc import abstractmethod
import asyncio
from collections.abc import Mapping
import datetime
from datetime import timedelta
import json
import time
from typing import TYPE_CHECKING, Any

import betterproto
from mashumaro.exceptions import InvalidFieldValue
from pymammotion.aliyun.cloud_gateway import (
    DeviceOfflineException,
    FailedRequestException,
    GatewayTimeoutException,
    NoConnectionException,
)
from pymammotion.aliyun.model.dev_by_account_response import Device
from pymammotion.data.model.device import MowerInfo, MowingDevice
from pymammotion.data.model.report_info import Maintain
from pymammotion.data.mqtt.event import DeviceNotificationEventParams, ThingEventMessage
from pymammotion.data.mqtt.properties import OTAProgressItems, ThingPropertiesMessage
from pymammotion.data.mqtt.status import ThingStatusMessage
from pymammotion.http.model.http import ErrorInfo
from pymammotion.mammotion.devices.mammotion import (
    ConnectionPreference,
    Mammotion,
    MammotionMixedDeviceManager,
)
from pymammotion.proto import RptAct, RptInfoType, SystemUpdateBufMsg
from pymammotion.utility.constant import WorkMode
from pymammotion.utility.device_type import DeviceType

from homeassistant.components import bluetooth
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .config import MammotionConfigStore
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
        self.device: Device = device
        self.device_name = device.deviceName
        self.manager: Mammotion = mammotion
        self.update_failures = 0

    @abstractmethod
    def get_coordinator_data(self, device: MammotionMixedDeviceManager) -> _DataT:
        """Get coordinator data."""

    async def async_refresh_login(self) -> None:
        """Refresh login credentials asynchronously."""
        account = self.config_entry.data.get(CONF_ACCOUNTNAME)
        password = self.config_entry.data.get(CONF_PASSWORD)
        await self.manager.refresh_login(account, password)
        self.store_cloud_credentials()

    async def device_offline(self, device: MammotionMixedDeviceManager) -> None:
        device.state.online = False
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
        if not self.manager.get_device_by_name(self.device_name).state.online:
            return False

        device = self.manager.get_device_by_name(self.device_name)

        try:
            await self.manager.send_command_with_args(
                self.device_name, command, **kwargs
            )
            self.update_failures = 0
            return True
        except FailedRequestException:
            self.update_failures += 1
            if self.update_failures < 5:
                return await self.async_send_command(command, **kwargs)
            return False
        except EXPIRED_CREDENTIAL_EXCEPTIONS:
            self.update_failures += 1
            await self.async_refresh_login()
            if self.update_failures < 5:
                return await self.async_send_command(command, **kwargs)
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
        if mower := self.manager.mower(self.device_name):
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
                    device_registry.async_update_device(
                        device_entry.id, model_id=model_id
                    )

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

    async def clear_update_failures(self) -> None:
        self.update_failures = 0
        device = self.manager.get_device_by_name(self.device_name)
        if not device.state.online:
            device.state.online = True
        if device.has_cloud() and device.cloud().stopped:
            await device.cloud().start()

    async def async_restore_data(self) -> None:
        """Restore saved data."""
        store = MammotionConfigStore(self.hass, version=1, minor_version=1, key=DOMAIN)
        restored_data: Mapping[str, Any] | None = await store.async_load()

        try:
            if mower_data := restored_data.get(self.device_name):
                mower_state = MowingDevice().from_dict(mower_data)
                if device := self.manager.get_device_by_name(self.device_name):
                    device.state = mower_state
        except InvalidFieldValue:
            """invalid"""
            self.data = MowingDevice()
            self.manager.get_device_by_name(self.device_name).state = self.data

    async def async_save_data(self, data: MowingDevice) -> None:
        """Get map data from the device."""
        store = MammotionConfigStore(self.hass, version=1, minor_version=1, key=DOMAIN)
        current_store = await store.async_load()
        current_store[self.device_name] = data.to_dict()
        await store.async_save(current_store)

    async def _async_update_data(self) -> _DataT | None:
        if device := self.manager.get_device_by_name(self.device_name):
            if not device.state.enabled or (
                not device.state.online
                and device.preference is ConnectionPreference.WIFI
            ):
                if (
                    not device.state.enabled
                    and device.has_cloud()
                    and device.cloud().mqtt.is_connected()
                ):
                    device.cloud().mqtt.disconnect()
                if not device.state.enabled and device.has_ble():
                    if (
                        device.ble().client is not None
                        and device.ble().client.is_connected
                    ):
                        await device.ble().client.disconnect()
                return self.get_coordinator_data(device)

            if (
                device.state.mower_state.ble_mac != ""
                and device.preference is ConnectionPreference.BLUETOOTH
            ):
                if ble_device := bluetooth.async_ble_device_from_address(
                    self.hass, device.state.mower_state.ble_mac.upper(), True
                ):
                    if not device.has_ble():
                        device.add_ble(ble_device)
                    else:
                        device.ble().update_device(ble_device)

            # don't query the mower while users are doing map changes or its updating.
            if device.state.report_data.dev.sys_status in NO_REQUEST_MODES:
                # MQTT we are likely to get an update, BLE we are not
                if device.preference is ConnectionPreference.BLUETOOTH:
                    loop = asyncio.get_running_loop()
                    loop.call_later(
                        300,
                        lambda: asyncio.create_task(
                            self.async_send_command("get_report_cfg")
                        ),
                    )
                return self.get_coordinator_data(device)

            if (
                self.update_failures > 5
                and device.preference is ConnectionPreference.WIFI
            ):
                """Don't hammer the mammotion/ali servers"""
                loop = asyncio.get_running_loop()
                loop.call_later(
                    60, lambda: asyncio.create_task(self.clear_update_failures())
                )

                return self.get_coordinator_data(device)
            return None
        return None

    async def _async_update_notification(self, res: tuple[str, Any | None]) -> None:
        """Update data from incoming messages."""

    async def _async_update_properties(
        self, properties: ThingPropertiesMessage
    ) -> None:
        """Update data from incoming properties messages."""

    async def _async_update_status(self, status: ThingStatusMessage) -> None:
        """Update data from incoming status messages."""

    async def _async_update_event_message(self, event: ThingEventMessage) -> None:
        """Update data from incoming event messages."""

    async def _async_setup(self) -> None:
        device = self.manager.get_device_by_name(self.device_name)

        if self.data is None:
            self.data = device.state
        if device.has_cloud():
            device.cloud().set_notification_callback(self._async_update_notification)
        elif device.has_ble():
            device.ble().set_notification_callback(self._async_update_notification)

        device.state_manager.properties_callback.add_subscribers(
            self._async_update_properties
        )
        device.state_manager.status_callback.add_subscribers(self._async_update_status)

        device.state_manager.device_event_callback.add_subscribers(
            self._async_update_event_message
        )


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

    def get_coordinator_data(self, device: MammotionMixedDeviceManager) -> MowingDevice:
        return device.state

    async def _async_update_data(self) -> MowingDevice:
        """Get data from the device."""
        if data := await super()._async_update_data():
            return data

        device = self.manager.get_device_by_name(self.device_name)
        if device is None:
            LOGGER.debug("device not found")
            return data

        try:
            last_sent_time = 0
            if device.cloud():
                last_sent_time = device.cloud().command_sent_time
            elif device.ble():
                last_sent_time = device.ble().command_sent_time

            if (
                self.update_interval
                and last_sent_time < time.time() - self.update_interval.seconds
            ):
                await self.async_send_command("get_report_cfg")

        except DeviceOfflineException as ex:
            """Device is offline."""
            if ex.iot_id == self.device.iotId:
                device = self.manager.get_device_by_name(self.device_name)
                await self.device_offline(device)
                return device.state

        LOGGER.debug("Updated Mammotion device %s", self.device_name)
        LOGGER.debug("================= Debug Log =================")
        if device.preference is ConnectionPreference.BLUETOOTH:
            if device.ble():
                LOGGER.debug(
                    "Mammotion device data: %s",
                    device.ble()._raw_data,
                )
        if device.preference is ConnectionPreference.WIFI:
            if device.cloud():
                LOGGER.debug(
                    "Mammotion device data: %s",
                    device.cloud()._raw_data,
                )
        LOGGER.debug("==================================")

        self.update_failures = 0
        data = self.manager.get_device_by_name(self.device_name).state
        await self.async_save_data(data)

        if data.report_data.dev.sys_status in (
            WorkMode.MODE_WORKING,
            WorkMode.MODE_RETURNING,
            WorkMode.MODE_PAUSE,
        ):
            self.update_interval = WORKING_INTERVAL
        else:
            self.update_interval = DEFAULT_INTERVAL

        return data

    async def _async_update_notification(self, res: tuple[str, Any | None]) -> None:
        """Update data from incoming messages."""
        if res[0] == "sys" and res[1] is not None:
            sys_msg = betterproto.which_one_of(res[1], "SubSysMsg")
            if sys_msg[0] == "toapp_report_data":
                if mower := self.manager.mower(self.device_name):
                    self.async_set_updated_data(mower)


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

    def get_coordinator_data(self, device: MammotionMixedDeviceManager) -> Maintain:
        return device.state.report_data.maintenance

    async def _async_update_data(self) -> Maintain:
        """Get data from the device."""
        if data := await super()._async_update_data():
            return data

        try:
            await self.async_send_command("get_maintenance")

        except DeviceOfflineException as ex:
            """Device is offline."""
            if ex.iot_id == self.device.iotId:
                device = self.manager.get_device_by_name(self.device_name)
                await self.device_offline(device)
                return device.state
        except GatewayTimeoutException:
            """Gateway is timing out again."""

        return self.manager.get_device_by_name(
            self.device.deviceName
        ).state.report_data.maintenance

    async def _async_setup(self) -> None:
        """Setup maintenance coordinator."""
        await super()._async_setup()
        device = self.manager.get_device_by_name(self.device_name)
        if self.data is None:
            self.data = device.state.report_data.maintenance


class MammotionDeviceVersionUpdateCoordinator(
    MammotionBaseUpdateCoordinator[MowingDevice]
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

    def get_coordinator_data(self, device: MammotionMixedDeviceManager) -> MowingDevice:
        return device.state

    async def _async_update_properties(
        self, properties: ThingPropertiesMessage
    ) -> None:
        """Update data from incoming properties messages."""
        if ota_progress := properties.params.items.otaProgress:
            ota_progress.value = OTAProgressItems.from_dict(ota_progress.value)
            self.data.update_check.progress = ota_progress.value.progress
            self.data.update_check.isupgrading = True
            if ota_progress.value.progress == 100:
                self.data.update_check.isupgrading = False
                self.data.update_check.upgradeable = False
                self.data.device_firmwares.device_version = ota_progress.value.version
            self.async_set_updated_data(self.data)

    async def _async_update_data(self):
        """Get data from the device."""
        if data := await super()._async_update_data():
            return data
        device = self.manager.get_device_by_name(self.device_name)
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
                    await self.device_offline(device)
                    return device.state
            except GatewayTimeoutException:
                """Gateway is timing out again."""

        data = self.manager.get_device_by_name(self.device_name).state
        await self.check_firmware_version()

        ota_info = await device.mammotion_http.get_device_ota_firmware([device.iot_id])
        if check_versions := ota_info.data:
            for check_version in check_versions:
                if check_version.device_id == device.iot_id:
                    device.state.update_check = check_version

        if data.mower_state.model_id != "":
            self.update_interval = DEVICE_VERSION_INTERVAL

        return data

    async def _async_setup(self) -> None:
        """Setup device version coordinator."""
        await super()._async_setup()
        device = self.manager.get_device_by_name(self.device_name)
        if self.data is None:
            self.data = device.state

        try:
            if device.state.mower_state.model_id == "":
                await self.async_send_command("get_device_product_model")
            if device.state.mower_state.wifi_mac == "":
                await self.async_send_command("get_device_network_info")

            ota_info = await device.mammotion_http.get_device_ota_firmware(
                [device.iot_id]
            )
            if check_versions := ota_info.data:
                for check_version in check_versions:
                    if check_version.device_id == device.iot_id:
                        device.state.update_check = check_version

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

    def get_coordinator_data(self, device: MammotionMixedDeviceManager) -> MowerInfo:
        return device.state.mower_state

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
                round(device.state.location.RTK.latitude, 0) == 0
                or round(device.state.location.dock.latitude, 0) == 0
            ):
                await self.async_rtk_dock_location()

            if (
                len(device.state.map.hashlist) == 0
                or len(device.state.map.missing_hashlist()) > 0
                or len(device.state.map.plan) == 0
            ):
                await self.manager.start_map_sync(self.device_name)

        except DeviceOfflineException as ex:
            """Device is offline try bluetooth if we have it."""
            if ex.iot_id == self.device.iotId:
                await self.device_offline(device)
                return device.state.mower_state
        except GatewayTimeoutException:
            """Gateway is timing out again."""

        return self.manager.get_device_by_name(self.device_name).state.mower_state

    async def _async_setup(self) -> None:
        """Setup coordinator with initial call to get map data."""
        await super()._async_setup()
        device = self.manager.get_device_by_name(self.device_name)
        if self.data is None:
            self.data = device.state.mower_state

        if not device.state.enabled or not device.state.online:
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


class MammotionDeviceErrorUpdateCoordinator(
    MammotionBaseUpdateCoordinator[MowingDevice]
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

    def get_coordinator_data(self, device: MammotionMixedDeviceManager) -> MowingDevice:
        return device.state

    async def _async_update_event_message(self, event: ThingEventMessage) -> None:
        if event.params.identifier == "device_warning_code_event":
            event: DeviceNotificationEventParams = event.params
            # '[{"c":-2801,"ct":1,"ft":1731493734000},{"c":-1008,"ct":1,"ft":1731493734000}]'
            try:
                warning_event = json.loads(event.value.data)
                LOGGER.debug("warning event %s", warning_event)
                await self._async_update_data()
                if mower := self.manager.mower(self.device_name):
                    self.async_set_updated_data(mower)
            except json.JSONDecodeError:
                """Failed to parse warning event."""

    async def _async_update_notification(self, res: tuple[str, Any | None]) -> None:
        """Update data from incoming notifications messages."""
        if res[0] == "sys" and res[1] is not None:
            sys_msg = betterproto.which_one_of(res[1], "SubSysMsg")
            if sys_msg[0] == "system_update_buf" and sys_msg[1] is not None:
                buffer_list: SystemUpdateBufMsg = sys_msg[1]
                if buffer_list.update_buf_data[0] == 2:
                    if mower := self.manager.mower(self.device_name):
                        self.async_set_updated_data(mower)

    def get_error_message(self, number: int) -> str:
        """Return error message."""
        try:
            error_code: int = next(iter(self.data.errors.err_code_list))
            error_time = next(iter(self.data.errors.err_code_list_time))

            error_datetime = datetime.datetime.fromtimestamp(error_time, datetime.UTC)
            current_time_utc = datetime.datetime.now(datetime.UTC)

            error_time_passed = current_time_utc - error_datetime

            if error_time_passed.total_seconds() > 3600 * 24:
                return ""

            error_code = abs(error_code)
            error_info: ErrorInfo = self.data.errors.error_codes.get(
                f"{error_code}", None
            )

            implication = (
                getattr(error_info, f"{self.hass.config.language}_implication")
                if hasattr(error_info, f"{self.hass.config.language}_implication")
                else error_info.en_implication
            )
            solution = (
                getattr(error_info, f"{self.hass.config.language}_solution")
                if hasattr(error_info, f"{self.hass.config.language}_solution")
                else error_info.en_solution
            )

            if implication == "":
                implication = error_info.en_implication

            if solution == "":
                solution = error_info.en_solution

            return f"{error_code} {error_info.module} {implication} {solution} {error_time_passed.total_seconds() / 60} minutes ago"

        except StopIteration:
            """Failed to get error code."""
            return ""

    async def _async_update_data(self):
        """Get data from the device."""
        if data := await super()._async_update_data():
            return data
        device = self.manager.get_device_by_name(self.device_name)

        try:
            await self.async_send_command("allpowerfull_rw", rw_id=5, rw=1, context=2)
            await self.async_send_command("allpowerfull_rw", rw_id=5, rw=1, context=3)
            if not device.state.errors.error_codes:
                device.state.errors.error_codes = (
                    await device.mammotion_http.get_all_error_codes()
                )
        except DeviceOfflineException as ex:
            """Device is offline bluetooth has been attempted."""
            if ex.iot_id == self.device.iotId:
                await self.device_offline(device)
                return device.state
        except GatewayTimeoutException:
            """Gateway is timing out again."""

        return data

    async def _async_setup(self) -> None:
        """Setup device version coordinator."""
        await super()._async_setup()
        device = self.manager.get_device_by_name(self.device_name)
        if self.data is None:
            self.data = device.state

        try:
            # get current errors
            await self.async_send_command("allpowerfull_rw", rw_id=5, rw=1, context=2)
            await self.async_send_command("allpowerfull_rw", rw_id=5, rw=1, context=3)
            if not device.state.errors.error_codes:
                device.state.errors.error_codes = (
                    await device.mammotion_http.get_all_error_codes()
                )
        except DeviceOfflineException:
            """Device is offline bluetooth has been attempted."""
