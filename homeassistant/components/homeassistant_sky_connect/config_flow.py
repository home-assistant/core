"""Config flow for the Home Assistant SkyConnect integration."""

from __future__ import annotations

from abc import ABC, abstractmethod
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
    is_hassio,
)
from homeassistant.components.homeassistant_hardware import silabs_multiprotocol_addon
from homeassistant.components.zha.repairs.wrong_silabs_firmware import (
    probe_silabs_firmware_type,
)
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryBaseFlow,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
    OptionsFlowWithConfigEntry,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import AbortFlow

from .const import DOCS_WEB_FLASHER_URL, DOMAIN, ZHA_DOMAIN, HardwareVariant
from .util import (
    get_hardware_variant,
    get_otbr_addon_manager,
    get_usb_service_info,
    get_zha_device_path,
    get_zigbee_flasher_addon_manager,
)

_LOGGER = logging.getLogger(__name__)

STEP_PICK_FIRMWARE_THREAD = "pick_firmware_thread"
STEP_PICK_FIRMWARE_ZIGBEE = "pick_firmware_zigbee"


class BaseFirmwareInstallFlow(ConfigEntryBaseFlow, ABC):
    """Base flow to install firmware."""

    _failed_addon_name: str
    _failed_addon_reason: str

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Instantiate base flow."""
        super().__init__(*args, **kwargs)

        self._usb_info: usb.UsbServiceInfo | None = None
        self._hw_variant: HardwareVariant | None = None
        self._probed_firmware_type: ApplicationType | None = None

        self.addon_install_task: asyncio.Task | None = None
        self.addon_start_task: asyncio.Task | None = None
        self.addon_uninstall_task: asyncio.Task | None = None

    def _get_translation_placeholders(self) -> dict[str, str]:
        """Shared translation placeholders."""
        placeholders = {
            "model": (
                self._hw_variant.full_name
                if self._hw_variant is not None
                else "unknown"
            ),
            "firmware_type": (
                self._probed_firmware_type.value
                if self._probed_firmware_type is not None
                else "unknown"
            ),
            "docs_web_flasher_url": DOCS_WEB_FLASHER_URL,
        }

        self.context["title_placeholders"] = placeholders

        return placeholders

    async def _async_set_addon_config(
        self, config: dict, addon_manager: AddonManager
    ) -> None:
        """Set add-on config."""
        try:
            await addon_manager.async_set_addon_options(config)
        except AddonError as err:
            _LOGGER.error(err)
            raise AbortFlow(
                "addon_set_config_failed",
                description_placeholders={
                    **self._get_translation_placeholders(),
                    "addon_name": addon_manager.addon_name,
                },
            ) from err

    async def _async_get_addon_info(self, addon_manager: AddonManager) -> AddonInfo:
        """Return add-on info."""
        try:
            addon_info = await addon_manager.async_get_addon_info()
        except AddonError as err:
            _LOGGER.error(err)
            raise AbortFlow(
                "addon_info_failed",
                description_placeholders={
                    **self._get_translation_placeholders(),
                    "addon_name": addon_manager.addon_name,
                },
            ) from err

        return addon_info

    async def async_step_pick_firmware(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick Thread or Zigbee firmware."""
        return self.async_show_menu(
            step_id="pick_firmware",
            menu_options=[
                STEP_PICK_FIRMWARE_ZIGBEE,
                STEP_PICK_FIRMWARE_THREAD,
            ],
            description_placeholders=self._get_translation_placeholders(),
        )

    async def _probe_firmware_type(self) -> bool:
        """Probe the firmware currently on the device."""
        assert self._usb_info is not None

        self._probed_firmware_type = await probe_silabs_firmware_type(
            self._usb_info.device,
            probe_methods=(
                # We probe in order of frequency: Zigbee, Thread, then multi-PAN
                ApplicationType.GECKO_BOOTLOADER,
                ApplicationType.EZSP,
                ApplicationType.SPINEL,
                ApplicationType.CPC,
            ),
        )

        return self._probed_firmware_type in (
            ApplicationType.EZSP,
            ApplicationType.SPINEL,
            ApplicationType.CPC,
        )

    async def async_step_pick_firmware_zigbee(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick Zigbee firmware."""
        if not await self._probe_firmware_type():
            return self.async_abort(
                reason="unsupported_firmware",
                description_placeholders=self._get_translation_placeholders(),
            )

        # Allow the stick to be used with ZHA without flashing
        if self._probed_firmware_type == ApplicationType.EZSP:
            return await self.async_step_confirm_zigbee()

        if not is_hassio(self.hass):
            return self.async_abort(
                reason="not_hassio",
                description_placeholders=self._get_translation_placeholders(),
            )

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
            description_placeholders={
                **self._get_translation_placeholders(),
                "addon_name": fw_flasher_manager.addon_name,
            },
        )

    async def async_step_install_zigbee_flasher_addon(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show progress dialog for installing the Zigbee flasher addon."""
        return await self._install_addon(
            get_zigbee_flasher_addon_manager(self.hass),
            "install_zigbee_flasher_addon",
            "run_zigbee_flasher_addon",
        )

    async def _install_addon(
        self,
        addon_manager: silabs_multiprotocol_addon.WaitingAddonManager,
        step_id: str,
        next_step_id: str,
    ) -> ConfigFlowResult:
        """Show progress dialog for installing an addon."""
        addon_info = await self._async_get_addon_info(addon_manager)

        _LOGGER.debug("Flasher addon state: %s", addon_info)

        if not self.addon_install_task:
            self.addon_install_task = self.hass.async_create_task(
                addon_manager.async_install_addon_waiting(),
                "Addon install",
            )

        if not self.addon_install_task.done():
            return self.async_show_progress(
                step_id=step_id,
                progress_action="install_addon",
                description_placeholders={
                    **self._get_translation_placeholders(),
                    "addon_name": addon_manager.addon_name,
                },
                progress_task=self.addon_install_task,
            )

        try:
            await self.addon_install_task
        except AddonError as err:
            _LOGGER.error(err)
            self._failed_addon_name = addon_manager.addon_name
            self._failed_addon_reason = "addon_install_failed"
            return self.async_show_progress_done(next_step_id="addon_operation_failed")
        finally:
            self.addon_install_task = None

        return self.async_show_progress_done(next_step_id=next_step_id)

    async def async_step_addon_operation_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Abort when add-on installation or start failed."""
        return self.async_abort(
            reason=self._failed_addon_reason,
            description_placeholders={
                **self._get_translation_placeholders(),
                "addon_name": self._failed_addon_name,
            },
        )

    async def async_step_run_zigbee_flasher_addon(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure the flasher addon to point to the SkyConnect and run it."""
        fw_flasher_manager = get_zigbee_flasher_addon_manager(self.hass)
        addon_info = await self._async_get_addon_info(fw_flasher_manager)

        assert self._usb_info is not None
        new_addon_config = {
            **addon_info.options,
            "device": self._usb_info.device,
            "baudrate": 115200,
            "bootloader_baudrate": 115200,
            "flow_control": True,
        }

        _LOGGER.debug("Reconfiguring flasher addon with %s", new_addon_config)
        await self._async_set_addon_config(new_addon_config, fw_flasher_manager)

        if not self.addon_start_task:

            async def start_and_wait_until_done() -> None:
                await fw_flasher_manager.async_start_addon_waiting()
                # Now that the addon is running, wait for it to finish
                await fw_flasher_manager.async_wait_until_addon_state(
                    AddonState.NOT_RUNNING
                )

            self.addon_start_task = self.hass.async_create_task(
                start_and_wait_until_done()
            )

        if not self.addon_start_task.done():
            return self.async_show_progress(
                step_id="run_zigbee_flasher_addon",
                progress_action="run_zigbee_flasher_addon",
                description_placeholders={
                    **self._get_translation_placeholders(),
                    "addon_name": fw_flasher_manager.addon_name,
                },
                progress_task=self.addon_start_task,
            )

        try:
            await self.addon_start_task
        except (AddonError, AbortFlow) as err:
            _LOGGER.error(err)
            self._failed_addon_name = fw_flasher_manager.addon_name
            self._failed_addon_reason = "addon_start_failed"
            return self.async_show_progress_done(next_step_id="addon_operation_failed")
        finally:
            self.addon_start_task = None

        return self.async_show_progress_done(
            next_step_id="uninstall_zigbee_flasher_addon"
        )

    async def async_step_uninstall_zigbee_flasher_addon(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Uninstall the flasher addon."""
        fw_flasher_manager = get_zigbee_flasher_addon_manager(self.hass)

        if not self.addon_uninstall_task:
            _LOGGER.debug("Uninstalling flasher addon")
            self.addon_uninstall_task = self.hass.async_create_task(
                fw_flasher_manager.async_uninstall_addon_waiting()
            )

        if not self.addon_uninstall_task.done():
            return self.async_show_progress(
                step_id="uninstall_zigbee_flasher_addon",
                progress_action="uninstall_zigbee_flasher_addon",
                description_placeholders={
                    **self._get_translation_placeholders(),
                    "addon_name": fw_flasher_manager.addon_name,
                },
                progress_task=self.addon_uninstall_task,
            )

        try:
            await self.addon_uninstall_task
        except (AddonError, AbortFlow) as err:
            _LOGGER.error(err)
            # The uninstall failing isn't critical so we can just continue
        finally:
            self.addon_uninstall_task = None

        return self.async_show_progress_done(next_step_id="confirm_zigbee")

    async def async_step_confirm_zigbee(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm Zigbee setup."""
        assert self._usb_info is not None
        assert self._hw_variant is not None
        self._probed_firmware_type = ApplicationType.EZSP

        if user_input is not None:
            await self.hass.config_entries.flow.async_init(
                ZHA_DOMAIN,
                context={"source": "hardware"},
                data={
                    "name": self._hw_variant.full_name,
                    "port": {
                        "path": self._usb_info.device,
                        "baudrate": 115200,
                        "flow_control": "hardware",
                    },
                    "radio_type": "ezsp",
                },
            )

            return self._async_flow_finished()

        return self.async_show_form(
            step_id="confirm_zigbee",
            description_placeholders=self._get_translation_placeholders(),
        )

    async def async_step_pick_firmware_thread(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick Thread firmware."""
        if not await self._probe_firmware_type():
            return self.async_abort(
                reason="unsupported_firmware",
                description_placeholders=self._get_translation_placeholders(),
            )

        # We install the OTBR addon no matter what, since it is required to use Thread
        if not is_hassio(self.hass):
            return self.async_abort(
                reason="not_hassio_thread",
                description_placeholders=self._get_translation_placeholders(),
            )

        otbr_manager = get_otbr_addon_manager(self.hass)
        addon_info = await self._async_get_addon_info(otbr_manager)

        if addon_info.state == AddonState.NOT_INSTALLED:
            return await self.async_step_install_otbr_addon()

        if addon_info.state == AddonState.NOT_RUNNING:
            return await self.async_step_start_otbr_addon()

        # If the addon is already installed and running, fail
        return self.async_abort(
            reason="otbr_addon_already_running",
            description_placeholders={
                **self._get_translation_placeholders(),
                "addon_name": otbr_manager.addon_name,
            },
        )

    async def async_step_install_otbr_addon(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show progress dialog for installing the OTBR addon."""
        return await self._install_addon(
            get_otbr_addon_manager(self.hass), "install_otbr_addon", "start_otbr_addon"
        )

    async def async_step_start_otbr_addon(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure OTBR to point to the SkyConnect and run the addon."""
        otbr_manager = get_otbr_addon_manager(self.hass)
        addon_info = await self._async_get_addon_info(otbr_manager)

        assert self._usb_info is not None
        new_addon_config = {
            **addon_info.options,
            "device": self._usb_info.device,
            "baudrate": 460800,
            "flow_control": True,
            "autoflash_firmware": True,
        }

        _LOGGER.debug("Reconfiguring OTBR addon with %s", new_addon_config)
        await self._async_set_addon_config(new_addon_config, otbr_manager)

        if not self.addon_start_task:
            self.addon_start_task = self.hass.async_create_task(
                otbr_manager.async_start_addon_waiting()
            )

        if not self.addon_start_task.done():
            return self.async_show_progress(
                step_id="start_otbr_addon",
                progress_action="start_otbr_addon",
                description_placeholders={
                    **self._get_translation_placeholders(),
                    "addon_name": otbr_manager.addon_name,
                },
                progress_task=self.addon_start_task,
            )

        try:
            await self.addon_start_task
        except (AddonError, AbortFlow) as err:
            _LOGGER.error(err)
            self._failed_addon_name = otbr_manager.addon_name
            self._failed_addon_reason = "addon_start_failed"
            return self.async_show_progress_done(next_step_id="addon_operation_failed")
        finally:
            self.addon_start_task = None

        return self.async_show_progress_done(next_step_id="confirm_otbr")

    async def async_step_confirm_otbr(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm OTBR setup."""
        assert self._usb_info is not None
        assert self._hw_variant is not None

        self._probed_firmware_type = ApplicationType.SPINEL

        if user_input is not None:
            # OTBR discovery is done automatically via hassio
            return self._async_flow_finished()

        return self.async_show_form(
            step_id="confirm_otbr",
            description_placeholders=self._get_translation_placeholders(),
        )

    @abstractmethod
    def _async_flow_finished(self) -> ConfigFlowResult:
        """Finish the flow."""
        # This should be implemented by a subclass
        raise NotImplementedError


class HomeAssistantSkyConnectConfigFlow(
    BaseFirmwareInstallFlow, ConfigFlow, domain=DOMAIN
):
    """Handle a config flow for Home Assistant SkyConnect."""

    VERSION = 1
    MINOR_VERSION = 2

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Return the options flow."""
        firmware_type = ApplicationType(config_entry.data["firmware"])

        if firmware_type is ApplicationType.CPC:
            return HomeAssistantSkyConnectMultiPanOptionsFlowHandler(config_entry)

        return HomeAssistantSkyConnectOptionsFlowHandler(config_entry)

    async def async_step_usb(
        self, discovery_info: usb.UsbServiceInfo
    ) -> ConfigFlowResult:
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

        assert description is not None
        self._hw_variant = HardwareVariant.from_usb_product_name(description)

        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm a discovery."""
        return await self.async_step_pick_firmware()

    def _async_flow_finished(self) -> ConfigFlowResult:
        """Create the config entry."""
        assert self._usb_info is not None
        assert self._hw_variant is not None
        assert self._probed_firmware_type is not None

        return self.async_create_entry(
            title=self._hw_variant.full_name,
            data={
                "vid": self._usb_info.vid,
                "pid": self._usb_info.pid,
                "serial_number": self._usb_info.serial_number,
                "manufacturer": self._usb_info.manufacturer,
                "description": self._usb_info.description,  # For backwards compatibility
                "product": self._usb_info.description,
                "device": self._usb_info.device,
                "firmware": self._probed_firmware_type.value,
            },
        )


class HomeAssistantSkyConnectMultiPanOptionsFlowHandler(
    silabs_multiprotocol_addon.OptionsFlowHandler
):
    """Multi-PAN options flow for Home Assistant SkyConnect."""

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

    @property
    def _hw_variant(self) -> HardwareVariant:
        """Return the hardware variant."""
        return get_hardware_variant(self.config_entry)

    def _zha_name(self) -> str:
        """Return the ZHA name."""
        return f"{self._hw_variant.short_name} Multiprotocol"

    def _hardware_name(self) -> str:
        """Return the name of the hardware."""
        return self._hw_variant.full_name

    async def async_step_flashing_complete(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Finish flashing and update the config entry."""
        self.hass.config_entries.async_update_entry(
            entry=self.config_entry,
            data={
                **self.config_entry.data,
                "firmware": ApplicationType.EZSP.value,
            },
            options=self.config_entry.options,
        )

        return await super().async_step_flashing_complete(user_input)


class HomeAssistantSkyConnectOptionsFlowHandler(
    BaseFirmwareInstallFlow, OptionsFlowWithConfigEntry
):
    """Zigbee and Thread options flow handlers."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Instantiate options flow."""
        super().__init__(*args, **kwargs)

        self._usb_info = get_usb_service_info(self.config_entry)
        self._probed_firmware_type = ApplicationType(self.config_entry.data["firmware"])
        self._hw_variant = HardwareVariant.from_usb_product_name(
            self.config_entry.data["product"]
        )

        # Make `context` a regular dictionary
        self.context = {}

        # Regenerate the translation placeholders
        self._get_translation_placeholders()

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options flow."""
        return await self.async_step_pick_firmware()

    async def async_step_pick_firmware_zigbee(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick Zigbee firmware."""
        assert self._usb_info is not None

        if is_hassio(self.hass):
            otbr_manager = get_otbr_addon_manager(self.hass)
            otbr_addon_info = await self._async_get_addon_info(otbr_manager)

            if (
                otbr_addon_info.state != AddonState.NOT_INSTALLED
                and otbr_addon_info.options.get("device") == self._usb_info.device
            ):
                raise AbortFlow(
                    "otbr_still_using_stick",
                    description_placeholders=self._get_translation_placeholders(),
                )

        return await super().async_step_pick_firmware_zigbee(user_input)

    async def async_step_pick_firmware_thread(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick Thread firmware."""
        assert self._usb_info is not None

        for zha_entry in self.hass.config_entries.async_entries(
            ZHA_DOMAIN,
            include_ignore=False,
            include_disabled=True,
        ):
            if get_zha_device_path(zha_entry) == self._usb_info.device:
                raise AbortFlow(
                    "zha_still_using_stick",
                    description_placeholders=self._get_translation_placeholders(),
                )

        return await super().async_step_pick_firmware_thread(user_input)

    def _async_flow_finished(self) -> ConfigFlowResult:
        """Create the config entry."""
        assert self._usb_info is not None
        assert self._hw_variant is not None
        assert self._probed_firmware_type is not None

        self.hass.config_entries.async_update_entry(
            entry=self.config_entry,
            data={
                **self.config_entry.data,
                "firmware": self._probed_firmware_type.value,
            },
            options=self.config_entry.options,
        )

        return self.async_create_entry(title="", data={})
