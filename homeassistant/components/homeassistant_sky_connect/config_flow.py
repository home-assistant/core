"""Config flow for the Home Assistant SkyConnect integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from universal_silabs_flasher.const import ApplicationType

from homeassistant.components import usb
from homeassistant.components.hassio import (
    AddonError,
    AddonInfo,
    AddonManager,
    AddonState,
)
from homeassistant.components.homeassistant_hardware import silabs_multiprotocol_addon
from homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon import (
    WaitingAddonManager,
)
from homeassistant.components.zha import DOMAIN as ZHA_DOMAIN
from homeassistant.components.zha.repairs.wrong_silabs_firmware import (
    probe_silabs_firmware_type,
)
from homeassistant.config_entries import ConfigEntry, ConfigFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import AbortFlow, FlowResult
from homeassistant.helpers.singleton import singleton

from .const import DOMAIN
from .util import get_usb_service_info

_LOGGER = logging.getLogger(__name__)

DATA_OTBR_ADDON_MANAGER = "openthread_border_router"
DATA_ZIGBEE_FLASHER_ADDON_MANAGER = "silabs_flasher"

OTBR_ADDON_SLUG = "core_openthread_border_router"
ZIGBEE_FLASHER_ADDON_SLUG = "core_silabs_flasher"

STEP_PICK_FIRMWARE_THREAD = "pick_firmware_thread"
STEP_PICK_FIRMWARE_ZIGBEE = "pick_firmware_zigbee"


@singleton(DATA_OTBR_ADDON_MANAGER)
@callback
def get_otbr_addon_manager(hass: HomeAssistant) -> WaitingAddonManager:
    """Get the OTBR add-on manager."""
    return WaitingAddonManager(
        hass,
        _LOGGER,
        "OpenThread Border Router",
        OTBR_ADDON_SLUG,
    )


@singleton(DATA_ZIGBEE_FLASHER_ADDON_MANAGER)
@callback
def get_zigbee_flasher_addon_manager(hass: HomeAssistant) -> WaitingAddonManager:
    """Get the flasher add-on manager."""
    return WaitingAddonManager(
        hass,
        _LOGGER,
        "Silicon Labs Flasher",
        ZIGBEE_FLASHER_ADDON_SLUG,
    )


class HomeAssistantSkyConnectConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Home Assistant SkyConnect."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow instance."""
        super().__init__()

        self._hass = None
        self._current_firmware_type: ApplicationType | None = None
        self._usb_info: usb.UsbServiceInfo | None = None

        self.install_task: asyncio.Task | None = None
        self.start_task: asyncio.Task | None = None
        self.stop_task: asyncio.Task | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> HomeAssistantSkyConnectOptionsFlow:
        """Return the options flow."""
        return HomeAssistantSkyConnectOptionsFlow(config_entry)

    async def _async_set_addon_config(
        self, config: dict, addon_manager: AddonManager
    ) -> None:
        """Set add-on config."""
        try:
            await addon_manager.async_set_addon_options(config)
        except AddonError as err:
            _LOGGER.error(err)
            raise AbortFlow("addon_set_config_failed") from err

    async def _async_get_addon_info(self, addon_manager: AddonManager) -> AddonInfo:
        """Return add-on info."""
        try:
            addon_info: AddonInfo = await addon_manager.async_get_addon_info()
        except AddonError as err:
            _LOGGER.error(err)
            raise AbortFlow(
                "addon_info_failed",
                description_placeholders={"addon_name": addon_manager.addon_name},
            ) from err

        return addon_info

    async def async_step_usb(self, discovery_info: usb.UsbServiceInfo) -> FlowResult:
        """Handle usb discovery."""
        device = discovery_info.device
        vid = discovery_info.vid
        pid = discovery_info.pid
        serial_number = discovery_info.serial_number
        manufacturer = discovery_info.manufacturer
        description = discovery_info.description
        unique_id = f"{vid}:{pid}_{serial_number}_{manufacturer}_{description}"

        if await self.async_set_unique_id(unique_id):
            self._abort_if_unique_id_configured(updates={"device": device})

        discovery_info.device = await self.hass.async_add_executor_job(
            usb.get_serial_by_id, discovery_info.device
        )

        self._usb_info = discovery_info

        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm a discovery."""
        self._set_confirm_only()

        # Don't permit discovery if we are already set up
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        # Without confirmation, discovery can automatically progress into parts of the
        # config flow logic that interacts with hardware.
        if user_input is not None:
            return await self.async_step_pick_firmware()

        return self.async_show_form(step_id="confirm")

    async def async_step_pick_firmware(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Pick Thread or Zigbee firmware."""
        assert self._usb_info is not None
        assert self._current_firmware_type is not None

        self._current_firmware_type = await probe_silabs_firmware_type(
            self._usb_info.device,
            probe_order=(
                ApplicationType.GECKO_BOOTLOADER,
                ApplicationType.EZSP,
                ApplicationType.SPINEL,
                ApplicationType.CPC,
            ),
        )

        if self._current_firmware_type not in (
            ApplicationType.EZSP,
            ApplicationType.SPINEL,
        ):
            return self.async_abort(
                reason="unsupported_firmware",
                description_placeholders={"firmware_type": self._current_firmware_type},
            )

        return self.async_show_menu(
            step_id="pick_firmware",
            menu_options=[
                STEP_PICK_FIRMWARE_THREAD,
                STEP_PICK_FIRMWARE_ZIGBEE,
            ],
        )

    async def async_step_pick_firmware_thread(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Pick Thread firmware."""
        raise NotImplementedError()

    async def async_step_pick_firmware_zigbee(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Pick Zigbee firmware."""
        if self._current_firmware_type == ApplicationType.EZSP:
            return await self.async_step_confirm_zigbee()

        # Only flash new firmware if we need to
        fw_flasher_manager = get_zigbee_flasher_addon_manager(self.hass)
        addon_info = await self._async_get_addon_info(fw_flasher_manager)

        if addon_info.state == AddonState.NOT_INSTALLED:
            return await self.async_step_install_zigbee_flasher_addon()

        if addon_info.state == AddonState.NOT_RUNNING:
            return await self.async_step_run_zigbee_flasher_addon()

        # If the addon is already installed and running, fail
        return self.async_abort(
            reason="addon_already_running",
            description_placeholders={"addon_name": fw_flasher_manager.addon_name},
        )

    async def async_step_install_zigbee_flasher_addon(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show progress dialog for installing the Zigbee flasher addon."""
        fw_flasher_manager = get_zigbee_flasher_addon_manager(self.hass)
        addon_info = await self._async_get_addon_info(fw_flasher_manager)

        _LOGGER.debug("Flasher addon state: %s", addon_info)

        if not self.install_task:
            self.install_task = self.hass.async_create_task(
                fw_flasher_manager.async_install_addon_waiting(),
                "SiLabs Flasher addon install",
            )

        if not self.install_task.done():
            return self.async_show_progress(
                step_id="install_zigbee_flasher_addon",
                progress_action="install_addon",
                description_placeholders={"addon_name": fw_flasher_manager.addon_name},
                progress_task=self.install_task,
            )

        try:
            await self.install_task
        except AddonError as err:
            _LOGGER.error(err)
            return self.async_show_progress_done(next_step_id="install_failed")
        finally:
            self.install_task = None

        return self.async_show_progress_done(next_step_id="run_zigbee_flasher_addon")

    async def async_step_run_zigbee_flasher_addon(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure the flasher addon to point to the SkyConnect."""
        fw_flasher_manager = get_zigbee_flasher_addon_manager(self.hass)
        addon_info = await self._async_get_addon_info(fw_flasher_manager)

        assert self._usb_info is not None
        new_addon_config = {
            **addon_info.options,
            "device": self._usb_info.device,
            "baudrate": 115200,
            "flow_control": True,
        }

        _LOGGER.debug("Reconfiguring flasher addon with %s", new_addon_config)
        await self._async_set_addon_config(new_addon_config, fw_flasher_manager)

        if not self.start_task:

            async def start_and_wait_until_done() -> None:
                await fw_flasher_manager.async_start_addon_waiting()
                # Now that the addon is running, wait for it to finish
                await fw_flasher_manager.async_wait_until_addon_state(
                    AddonState.NOT_RUNNING
                )

            self.start_task = self.hass.async_create_task(start_and_wait_until_done())

        if not self.start_task.done():
            return self.async_show_progress(
                step_id="start_zigbee_flasher_addon",
                progress_action="start_zigbee_flasher_addon",
                description_placeholders={"addon_name": fw_flasher_manager.addon_name},
                progress_task=self.start_task,
            )

        try:
            await self.start_task
        except (AddonError, AbortFlow) as err:
            _LOGGER.error(err)
            return self.async_show_progress_done(next_step_id="zigbee_flasher_failed")
        finally:
            self.start_task = None

        return self.async_show_progress_done(next_step_id="zigbee_flashing_complete")

    async def async_step_zigbee_flasher_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Flasher add-on start failed."""
        fw_flasher_manager = get_zigbee_flasher_addon_manager(self.hass)
        return self.async_abort(
            reason="addon_start_failed",
            description_placeholders={"addon_name": fw_flasher_manager.addon_name},
        )

    async def async_step_zigbee_flashing_complete(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show completion dialog for flashing Zigbee firmware."""
        fw_flasher_manager = get_zigbee_flasher_addon_manager(self.hass)
        await fw_flasher_manager.async_uninstall_addon_waiting()

        return self.async_show_progress_done(next_step_id="step_confirm_zigbee")

    async def async_step_confirm_zigbee(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm a discovery."""
        self._set_confirm_only()
        assert self._usb_info is not None

        await self.hass.config_entries.flow.async_init(
            ZHA_DOMAIN,
            context={"source": "hardware"},
            data={
                "name": "SkyConnect",
                "port": {
                    "path": self._usb_info.device,
                    "baudrate": 115200,
                    "flow_control": "hardware",
                },
                "radio_type": "ezsp",
            },
        )

        return self.async_create_entry(
            title="SkyConnect",
            data={
                "vid": self._usb_info.vid,
                "pid": self._usb_info.pid,
                "serial_number": self._usb_info.serial_number,
                "manufacturer": self._usb_info.manufacturer,
                "description": self._usb_info.description,
                "device": self._usb_info.device,
            },
        )


class HomeAssistantSkyConnectOptionsFlow(silabs_multiprotocol_addon.OptionsFlowHandler):
    """Handle an option flow for Home Assistant SkyConnect."""

    async def _async_serial_port_settings(
        self,
    ) -> silabs_multiprotocol_addon.SerialPortSettings:
        """Return the radio serial port settings."""
        usb_dev = self.config_entry.data["device"]
        # The call to get_serial_by_id can be removed in HA Core 2024.1
        dev_path = await self.hass.async_add_executor_job(usb.get_serial_by_id, usb_dev)
        return silabs_multiprotocol_addon.SerialPortSettings(
            device=dev_path,
            baudrate="115200",
            flow_control=True,
        )

    async def _async_zha_physical_discovery(self) -> dict[str, Any]:
        """Return ZHA discovery data when multiprotocol FW is not used.

        Passed to ZHA do determine if the ZHA config entry is connected to the radio
        being migrated.
        """
        return {"usb": get_usb_service_info(self.config_entry)}

    def _zha_name(self) -> str:
        """Return the ZHA name."""
        return "SkyConnect Multiprotocol"

    def _hardware_name(self) -> str:
        """Return the name of the hardware."""
        return "Home Assistant SkyConnect"
