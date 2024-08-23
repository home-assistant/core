"""Provides the mammotion DataUpdateCoordinator."""

from __future__ import annotations

from dataclasses import asdict
from datetime import timedelta
from typing import TYPE_CHECKING

from pymammotion.data.model.account import Credentials
from pymammotion.data.model.device import MowingDevice
from pymammotion.mammotion.devices.mammotion import (
    ConnectionPreference,
    Mammotion,
    create_devices,
)
from pymammotion.proto.mctrl_sys import RptAct, RptInfoType
from pymammotion.utility.constant import WorkMode

from homeassistant.components import bluetooth
from homeassistant.const import CONF_ADDRESS, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    COMMAND_EXCEPTIONS,
    CONF_ACCOUNTNAME,
    CONF_DEVICE_NAME,
    DOMAIN,
    LOGGER,
)

if TYPE_CHECKING:
    from . import MammotionConfigEntry

SCAN_INTERVAL = timedelta(minutes=1)


class MammotionDataUpdateCoordinator(DataUpdateCoordinator[MowingDevice]):
    """Class to manage fetching mammotion data."""

    address: str
    config_entry: MammotionConfigEntry
    device_name: str
    devices: Mammotion

    def __init__(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Initialize global mammotion data updater."""
        super().__init__(
            hass=hass,
            logger=LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.update_failures = 0

    async def async_setup(self) -> None:
        """Set coordinator up."""
        ble_device = None
        credentials = Credentials()
        preference = ConnectionPreference.BLUETOOTH
        address = self.config_entry.data.get(CONF_ADDRESS)
        name = self.config_entry.data.get(CONF_DEVICE_NAME)

        if address:
            ble_device = bluetooth.async_ble_device_from_address(self.hass, address)
            if not ble_device:
                raise ConfigEntryNotReady(
                    f"Could not find Mammotion lawn mower with address {address}"
                )

            self.device_name = ble_device.name or "Unknown"
            self.address = ble_device.address

        account = self.config_entry.data.get(CONF_ACCOUNTNAME)
        password = self.config_entry.data.get(CONF_PASSWORD)
        if account and password:
            if name:
                self.device_name = name
            preference = ConnectionPreference.WIFI
            credentials.email = account
            credentials.password = password

        self.devices = await create_devices(ble_device, credentials, preference)
        print("creating devices")
        try:
            if preference is not ConnectionPreference.WIFI:
                await self.devices.start_sync(self.device_name, 0)

        except COMMAND_EXCEPTIONS as exc:
            raise ConfigEntryNotReady("Unable to setup Mammotion device") from exc

    async def async_sync_maps(self) -> None:
        """Get map data from the device."""
        await self.devices.start_map_sync(self.device_name)

    async def async_start_stop_blades(self, start_stop: bool) -> None:
        if start_stop:
            await self.async_send_command("set_blade_control", on_off=1)
        else:
            await self.async_send_command("set_blade_control", on_off=0)

    async def async_blade_height(self, height: int) -> None:
        await self.async_send_command("set_blade_height", height=height)

    async def async_rtk_dock_location(self):
        """RTK and dock location."""
        await self.async_send_command("allpowerfull_rw", id=5, rw=1, context=1)

    async def async_request_iot_sync(self) -> None:
        await self.async_send_command(
            "request_iot_sys",
            rpt_act=RptAct.RPT_START,
            rpt_info_type=[
                RptInfoType.RIT_CONNECT,
                RptInfoType.RIT_DEV_STA,
                RptInfoType.RIT_DEV_LOCAL,
                RptInfoType.RIT_RTK,
                RptInfoType.RIT_WORK,
            ],
            timeout=1000,
            period=3000,
            no_change_period=4000,
            count=0,
        )

    async def async_send_command(self, command: str, **kwargs: any) -> None:
        try:
            await self.devices.send_command_with_args(
                self.device_name, command, **kwargs
            )
        except COMMAND_EXCEPTIONS as exc:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="command_failed"
            ) from exc

    async def _async_update_data(self) -> MowingDevice:
        """Get data from the device."""
        device = self.devices.get_device_by_name(self.device_name)
        if not (
            ble_device := bluetooth.async_ble_device_from_address(
                self.hass, self.address
            )
        ):
            self.update_failures += 1
            raise UpdateFailed("Could not find device")

        device.ble().update_device(ble_device)
        try:
            if len(device.mower_state().net.toapp_devinfo_resp.resp_ids) == 0:
                await self.devices.start_sync(self.device_name, 0)
            if device.mower_state().report_data.dev.sys_status != WorkMode.MODE_WORKING:
                await self.async_send_command("get_report_cfg")

            else:
                await self.async_request_iot_sync()

        except COMMAND_EXCEPTIONS as exc:
            self.update_failures += 1
            raise UpdateFailed(f"Updating Mammotion device failed: {exc}") from exc

        LOGGER.debug("Updated Mammotion device %s", self.device_name)
        LOGGER.debug("================= Debug Log =================")
        LOGGER.debug(
            "Mammotion device data: %s",
            asdict(self.devices.get_device_by_name(self.device_name).mower_state()),
        )
        LOGGER.debug("==================================")

        self.update_failures = 0
        return self.devices.get_device_by_name(self.device_name).mower_state()

    # TODO when submitting to HA use this 2024.8 and up
    # async def _async_setup(self) -> None:
    #     try:
    #         await self.async_setup()
    #     except COMMAND_EXCEPTIONS as exc:
    #         raise UpdateFailed(f"Setting up Mammotion device failed: {exc}") from exc
