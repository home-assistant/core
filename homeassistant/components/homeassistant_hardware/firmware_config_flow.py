"""Config flow for the Home Assistant SkyConnect integration."""

from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
import logging
from typing import Any

from homeassistant.components.hassio import (
    AddonError,
    AddonInfo,
    AddonManager,
    AddonState,
)
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryBaseFlow,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.helpers.hassio import is_hassio

from .const import OTBR_DOMAIN, ZHA_DOMAIN
from .util import (
    ApplicationType,
    FirmwareInfo,
    OwningAddon,
    OwningIntegration,
    get_otbr_addon_manager,
    guess_firmware_info,
    guess_hardware_owners,
    probe_silabs_firmware_info,
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

        self._probed_firmware_info: FirmwareInfo | None = None
        self._device: str | None = None  # To be set in a subclass
        self._hardware_name: str = "unknown"  # To be set in a subclass

        self.addon_install_task: asyncio.Task | None = None
        self.addon_start_task: asyncio.Task | None = None
        self.addon_uninstall_task: asyncio.Task | None = None

    def _get_translation_placeholders(self) -> dict[str, str]:
        """Shared translation placeholders."""
        placeholders = {
            "firmware_type": (
                self._probed_firmware_info.firmware_type.value
                if self._probed_firmware_info is not None
                else "unknown"
            ),
            "model": self._hardware_name,
        }

        self.context["title_placeholders"] = placeholders

        return placeholders

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

    async def _probe_firmware_info(
        self,
        probe_methods: tuple[ApplicationType, ...] = (
            # We probe in order of frequency: Zigbee, Thread, then multi-PAN
            ApplicationType.GECKO_BOOTLOADER,
            ApplicationType.EZSP,
            ApplicationType.SPINEL,
            ApplicationType.CPC,
        ),
    ) -> bool:
        """Probe the firmware currently on the device."""
        assert self._device is not None

        self._probed_firmware_info = await probe_silabs_firmware_info(
            self._device,
            probe_methods=probe_methods,
        )

        return (
            self._probed_firmware_info is not None
            and self._probed_firmware_info.firmware_type
            in (
                ApplicationType.EZSP,
                ApplicationType.SPINEL,
                ApplicationType.CPC,
            )
        )

    async def async_step_pick_firmware_zigbee(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick Zigbee firmware."""
        if not await self._probe_firmware_info():
            return self.async_abort(
                reason="unsupported_firmware",
                description_placeholders=self._get_translation_placeholders(),
            )

        # Allow the stick to be used with ZHA without flashing
        if (
            self._probed_firmware_info is not None
            and self._probed_firmware_info.firmware_type == ApplicationType.EZSP
        ):
            return await self.async_step_confirm_zigbee()

        return await self.async_step_install_zigbee_firmware()

    async def async_step_install_zigbee_firmware(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Install Zigbee firmware."""
        raise NotImplementedError

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

    async def async_step_confirm_zigbee(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm Zigbee setup."""
        assert self._device is not None
        assert self._hardware_name is not None

        if not await self._probe_firmware_info(probe_methods=(ApplicationType.EZSP,)):
            return self.async_abort(
                reason="unsupported_firmware",
                description_placeholders=self._get_translation_placeholders(),
            )

        if user_input is not None:
            await self.hass.config_entries.flow.async_init(
                ZHA_DOMAIN,
                context={"source": "hardware"},
                data={
                    "name": self._hardware_name,
                    "port": {
                        "path": self._device,
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
        if not await self._probe_firmware_info():
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

        if addon_info.state == AddonState.RUNNING:
            # We only fail setup if we have an instance of OTBR running *and* it's
            # pointing to different hardware
            if addon_info.options["device"] != self._device:
                return self.async_abort(
                    reason="otbr_addon_already_running",
                    description_placeholders={
                        **self._get_translation_placeholders(),
                        "addon_name": otbr_manager.addon_name,
                    },
                )

            # Otherwise, stop the addon before continuing to flash firmware
            await otbr_manager.async_stop_addon()

        return await self.async_step_install_thread_firmware()

    async def async_step_install_thread_firmware(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Install Thread firmware."""
        raise NotImplementedError

    async def async_step_install_otbr_addon(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show progress dialog for installing the OTBR addon."""
        addon_manager = get_otbr_addon_manager(self.hass)
        addon_info = await self._async_get_addon_info(addon_manager)

        _LOGGER.debug("OTBR addon info: %s", addon_info)

        if not self.addon_install_task:
            self.addon_install_task = self.hass.async_create_task(
                addon_manager.async_install_addon_waiting(),
                "OTBR addon install",
            )

        if not self.addon_install_task.done():
            return self.async_show_progress(
                step_id="install_otbr_addon",
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

        return self.async_show_progress_done(next_step_id="pick_firmware_thread")

    async def async_step_start_otbr_addon(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure OTBR to point to the SkyConnect and run the addon."""
        otbr_manager = get_otbr_addon_manager(self.hass)
        addon_info = await self._async_get_addon_info(otbr_manager)

        assert self._device is not None
        new_addon_config = {
            **addon_info.options,
            "device": self._device,
            "baudrate": 460800,
            "flow_control": True,
            "autoflash_firmware": False,
        }

        _LOGGER.debug("Reconfiguring OTBR addon with %s", new_addon_config)

        try:
            await otbr_manager.async_set_addon_options(new_addon_config)
        except AddonError as err:
            _LOGGER.error(err)
            raise AbortFlow(
                "addon_set_config_failed",
                description_placeholders={
                    **self._get_translation_placeholders(),
                    "addon_name": otbr_manager.addon_name,
                },
            ) from err

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
        assert self._device is not None

        if not await self._probe_firmware_info(probe_methods=(ApplicationType.SPINEL,)):
            return self.async_abort(
                reason="unsupported_firmware",
                description_placeholders=self._get_translation_placeholders(),
            )

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
        raise NotImplementedError


class BaseFirmwareConfigFlow(BaseFirmwareInstallFlow, ConfigFlow):
    """Base config flow for installing firmware."""

    @staticmethod
    @callback
    @abstractmethod
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Return the options flow."""
        raise NotImplementedError

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm a discovery."""
        assert self._device is not None
        fw_info = await guess_firmware_info(self.hass, self._device)

        # If our guess for the firmware type is actually running, we can save the user
        # an unnecessary confirmation and silently confirm the flow
        for owner in fw_info.owners:
            if await owner.is_running(self.hass):
                self._probed_firmware_info = fw_info
                return self._async_flow_finished()

        return await self.async_step_pick_firmware()


class BaseFirmwareOptionsFlow(BaseFirmwareInstallFlow, OptionsFlow):
    """Zigbee and Thread options flow handlers."""

    _probed_firmware_info: FirmwareInfo

    def __init__(self, config_entry: ConfigEntry, *args: Any, **kwargs: Any) -> None:
        """Instantiate options flow."""
        super().__init__(*args, **kwargs)

        self._config_entry = config_entry

        # Make `context` a regular dictionary
        self.context = {}

        # Subclasses are expected to override `_device` and `_hardware_name`

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options flow."""
        return await self.async_step_pick_firmware()

    async def async_step_pick_firmware_zigbee(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick Zigbee firmware."""
        assert self._device is not None
        owners = await guess_hardware_owners(self.hass, self._device)

        for info in owners:
            for owner in info.owners:
                if info.source == OTBR_DOMAIN and isinstance(owner, OwningAddon):
                    raise AbortFlow(
                        "otbr_still_using_stick",
                        description_placeholders=self._get_translation_placeholders(),
                    )

        return await super().async_step_pick_firmware_zigbee(user_input)

    async def async_step_pick_firmware_thread(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick Thread firmware."""
        assert self._device is not None

        owners = await guess_hardware_owners(self.hass, self._device)

        for info in owners:
            for owner in info.owners:
                if info.source == ZHA_DOMAIN and isinstance(owner, OwningIntegration):
                    raise AbortFlow(
                        "zha_still_using_stick",
                        description_placeholders=self._get_translation_placeholders(),
                    )

        return await super().async_step_pick_firmware_thread(user_input)
